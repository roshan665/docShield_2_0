"""
Document Business Logic Service
Coordinates file validation, malware scanning, S3 storage, immutable versioning,
live integrity verification, and audit event emission.
"""

import hashlib
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    EntityNotFoundException,
    ValidationException,
)
from app.core.file_validation import (
    sanitize_filename,
    validate_file_content,
    validate_file_size,
)
from app.core.malware import scan_file_or_raise
from app.models.auth import User
from app.models.document import Document, DocumentVersion
from app.modules.audit.service import AuditService
from app.modules.auth.repository import SecurityEventRepository
from app.modules.cases.repository import CaseRepository
from app.modules.documents.repository import DocumentRepository
from app.schemas.document import (
    DocumentIntegrityResponse,
    DocumentResponse,
    DocumentVersionResponse,
)
from app.storage.s3 import S3StorageService
from app.storage.service import StorageService

logger = logging.getLogger(__name__)


class DocumentService:
    """Service governing Document operations and immutable version lifecycle."""

    def __init__(
        self,
        session: AsyncSession,
        storage: StorageService | None = None,
    ):
        self.session = session
        self.doc_repo = DocumentRepository(session)
        self.case_repo = CaseRepository(session)
        self.audit_service = AuditService(session)
        self.security_repo = SecurityEventRepository(session)
        self.storage = storage or S3StorageService()

    async def _verify_case_access(self, case_id: UUID, user: User) -> None:
        """
        Enforces zero-trust case membership.
        Non-members receive 404 Not Found to prevent case existence enumeration.
        """
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise EntityNotFoundException(detail="Case not found", error_code="CASE_001")

        membership = await self.case_repo.check_membership(case_id, user.id)
        if not membership:
            # 404 to mitigate IDOR/BOLA enumeration
            raise EntityNotFoundException(detail="Case not found", error_code="CASE_001")

    async def upload_document(
        self,
        case_id: UUID,
        title: str,
        document_type: str,
        upload_file: UploadFile,
        current_user: User,
        description: str | None = None,
        classification: str = "internal",
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> DocumentResponse:
        """
        Ingests a new legal document into a case.
        Validates membership, filename, size, magic-bytes, scans for malware,
        computes SHA-256, stores in MinIO/S3, and commits records with an audit event.
        """
        # 1. Zero-trust case membership verification
        await self._verify_case_access(case_id, current_user)

        # 2. Filename validation and sanitization
        raw_name = upload_file.filename or "uploaded_document"
        sanitized_name = sanitize_filename(raw_name)

        # 3. Read and validate file content
        content = await upload_file.read()
        validate_file_size(len(content))

        # 4. Content inspection / magic-bytes verification
        canonical_mime = validate_file_content(
            content=content,
            claimed_mime=upload_file.content_type,
            filename=sanitized_name,
        )

        # 5. Malware scanning hook (ClamAV / dev test signatures)
        scan_res = scan_file_or_raise(content)

        # 6. Authoritative server-side SHA-256 calculation
        file_hash = hashlib.sha256(content).hexdigest().lower()

        # 7. Generate deterministic, collision-free storage key
        doc_id = uuid4()
        ver_id = uuid4()
        storage_key = f"cases/{case_id}/documents/{doc_id}/versions/{ver_id}"
        storage_bucket = settings.S3_BUCKET_DOCUMENTS

        # 8. Upload to S3-compatible private object storage
        self.storage.ensure_bucket_exists(storage_bucket)
        self.storage.upload(
            file_data=content,
            key=storage_key,
            bucket=storage_bucket,
            content_type=canonical_mime,
            metadata={
                "sha256": file_hash,
                "original_filename": sanitized_name,
                "case_id": str(case_id),
                "uploader_id": str(current_user.id),
            },
        )

        # 9. Transactional database record creation
        doc = Document(
            id=doc_id,
            case_id=case_id,
            title=title.strip(),
            description=description.strip() if description else None,
            document_type=document_type,
            classification=classification,
            status="processed",
            original_filename=sanitized_name,
            mime_type=canonical_mime,
            file_size_bytes=len(content),
            uploaded_by=current_user.id,
            current_version_id=None,
        )
        await self.doc_repo.create_document(doc)

        version = DocumentVersion(
            id=ver_id,
            document_id=doc_id,
            version_number=1,
            storage_key=storage_key,
            storage_bucket=storage_bucket,
            file_hash_sha256=file_hash,
            file_size_bytes=len(content),
            mime_type=canonical_mime,
            original_filename=raw_name,
            sanitized_filename=sanitized_name,
            change_reason="Initial document upload",
            created_by=current_user.id,
            is_original=True,
            integrity_status="verified",
            last_verified_at=datetime.now(UTC),
        )
        await self.doc_repo.create_version(version)

        # Update circular pointer to version 1
        doc.current_version_id = ver_id
        await self.doc_repo.update(doc)

        # 10. Sequential hash-chained audit event emission
        await self.audit_service.record_event(
            actor_id=current_user.id,
            action="DOCUMENT_UPLOADED",
            resource_type="document",
            resource_id=doc_id,
            case_id=case_id,
            details={
                "title": doc.title,
                "document_type": doc.document_type,
                "version_number": 1,
                "file_hash_sha256": file_hash,
                "file_size_bytes": len(content),
                "mime_type": canonical_mime,
                "original_filename": sanitized_name,
                "malware_engine": scan_res.engine,
            },
            result="success",
            ip_address=client_ip,
        )

        await self.session.commit()
        self.session.expire_all()

        # Non-blocking async dispatch for AI Document Intelligence Pipeline
        try:
            from app.workers.tasks.ai_tasks import process_document_task

            process_document_task.delay(str(doc_id), str(current_user.id))
        except Exception as exc:
            logger.warning(f"Could not dispatch async Celery AI task: {exc}")

        loaded = await self.doc_repo.get_document_by_id(doc_id)
        return self._build_document_response(loaded)

    async def create_document_version(
        self,
        document_id: UUID,
        upload_file: UploadFile,
        current_user: User,
        change_reason: str | None = None,
        client_ip: str | None = None,
    ) -> DocumentResponse:
        """
        Appends an immutable new version to an existing document.
        Locks document row to guarantee sequential version numbering under concurrency.
        """
        # 1. Fetch document with row-level lock
        doc = await self.doc_repo.get_document_for_update(document_id)
        if not doc:
            raise EntityNotFoundException(detail="Document not found", error_code="DOC_001")

        # 2. Case membership authorization
        await self._verify_case_access(doc.case_id, current_user)

        # 3. Filename, size, content, and malware validation
        raw_name = upload_file.filename or doc.original_filename or "document"
        sanitized_name = sanitize_filename(raw_name)
        content = await upload_file.read()
        validate_file_size(len(content))
        canonical_mime = validate_file_content(content, upload_file.content_type, sanitized_name)
        scan_file_or_raise(content)

        file_hash = hashlib.sha256(content).hexdigest().lower()

        # 4. Determine sequential version number
        current_max = await self.doc_repo.get_latest_version_number(document_id)
        next_version = current_max + 1

        ver_id = uuid4()
        storage_key = f"cases/{doc.case_id}/documents/{document_id}/versions/{ver_id}"
        storage_bucket = settings.S3_BUCKET_DOCUMENTS

        # 5. Upload to S3 storage
        self.storage.ensure_bucket_exists(storage_bucket)
        self.storage.upload(
            file_data=content,
            key=storage_key,
            bucket=storage_bucket,
            content_type=canonical_mime,
            metadata={
                "sha256": file_hash,
                "original_filename": sanitized_name,
                "version_number": str(next_version),
            },
        )

        # 6. Create immutable version row
        version = DocumentVersion(
            id=ver_id,
            document_id=document_id,
            version_number=next_version,
            storage_key=storage_key,
            storage_bucket=storage_bucket,
            file_hash_sha256=file_hash,
            file_size_bytes=len(content),
            mime_type=canonical_mime,
            original_filename=raw_name,
            sanitized_filename=sanitized_name,
            change_reason=change_reason or f"Uploaded version {next_version}",
            created_by=current_user.id,
            is_original=False,
            integrity_status="verified",
            last_verified_at=datetime.now(UTC),
        )
        await self.doc_repo.create_version(version)

        # 7. Advance current_version pointer
        doc.current_version_id = ver_id
        doc.original_filename = sanitized_name
        doc.mime_type = canonical_mime
        doc.file_size_bytes = len(content)
        await self.doc_repo.update(doc)

        # 8. Audit logging
        await self.audit_service.record_event(
            actor_id=current_user.id,
            action="DOCUMENT_VERSION_CREATED",
            resource_type="document",
            resource_id=document_id,
            case_id=doc.case_id,
            details={
                "version_number": next_version,
                "change_reason": change_reason,
                "file_hash_sha256": file_hash,
                "file_size_bytes": len(content),
                "mime_type": canonical_mime,
            },
            result="success",
            ip_address=client_ip,
        )

        await self.session.commit()
        self.session.expire_all()

        # Non-blocking async dispatch for AI Document Intelligence Pipeline
        try:
            from app.workers.tasks.ai_tasks import process_document_task

            process_document_task.delay(str(document_id), str(current_user.id))
        except Exception as exc:
            logger.warning(f"Could not dispatch async Celery AI task: {exc}")

        loaded = await self.doc_repo.get_document_by_id(document_id)
        return self._build_document_response(loaded)

    async def get_document(self, document_id: UUID, current_user: User) -> DocumentResponse:
        """Retrieves document details and metadata for authorized case members."""
        doc = await self.doc_repo.get_document_by_id(document_id)
        if not doc:
            raise EntityNotFoundException(detail="Document not found", error_code="DOC_001")

        await self._verify_case_access(doc.case_id, current_user)
        return self._build_document_response(doc)

    async def list_documents_for_case(
        self,
        case_id: UUID,
        current_user: User,
        document_type: str | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[DocumentResponse]:
        """Lists documents for a case. Requires active case membership."""
        await self._verify_case_access(case_id, current_user)
        docs, _ = await self.doc_repo.list_documents_for_case(
            case_id=case_id,
            document_type=document_type,
            search=search,
            skip=skip,
            limit=limit,
        )
        return [self._build_document_response(d) for d in docs]

    async def list_documents_for_user(
        self,
        current_user: User,
        document_type: str | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[DocumentResponse]:
        """Lists documents across all cases where user is an active member."""
        docs, _ = await self.doc_repo.list_documents_for_user_cases(
            user_id=current_user.id,
            document_type=document_type,
            search=search,
            skip=skip,
            limit=limit,
        )
        return [self._build_document_response(d) for d in docs]

    async def list_document_versions(
        self,
        document_id: UUID,
        current_user: User,
    ) -> list[DocumentVersionResponse]:
        """Lists all immutable versions of a document."""
        doc = await self.doc_repo.get_document_by_id(document_id)
        if not doc:
            raise EntityNotFoundException(detail="Document not found", error_code="DOC_001")

        await self._verify_case_access(doc.case_id, current_user)
        versions = await self.doc_repo.list_versions_for_document(document_id)
        return [self._build_version_response(v) for v in versions]

    async def download_document(
        self,
        document_id: UUID,
        current_user: User,
        version_id: UUID | None = None,
        client_ip: str | None = None,
    ) -> tuple[bytes, str, str]:
        """
        Retrieves document bytes from S3, executes live SHA-256 integrity verification,
        audits the download, and returns (content, sanitized_filename, mime_type).
        """
        doc = await self.doc_repo.get_document_by_id(document_id)
        if not doc:
            raise EntityNotFoundException(detail="Document not found", error_code="DOC_001")

        await self._verify_case_access(doc.case_id, current_user)

        # Select target version
        if version_id:
            ver = await self.doc_repo.get_version_by_id(version_id)
            if not ver or ver.document_id != document_id:
                raise EntityNotFoundException(detail="Version not found", error_code="VER_001")
        else:
            ver = doc.current_version
            if not ver:
                raise EntityNotFoundException(detail="No active version available", error_code="VER_002")

        # 1. Retrieve raw bytes from object storage
        content = self.storage.download(ver.storage_key, ver.storage_bucket)

        # 2. Live Server-Side Cryptographic Integrity Check
        computed_hash = hashlib.sha256(content).hexdigest().lower()
        if computed_hash != ver.file_hash_sha256.lower():
            # Tamper or storage corruption detected!
            ver.integrity_status = "compromised"
            await self.session.commit()

            # Record critical security event
            await self.security_repo.record_event(
                event_type="document.integrity_mismatch",
                severity="CRITICAL",
                category="INTEGRITY",
                actor_id=current_user.id,
                case_id=doc.case_id,
                resource_type="document",
                resource_id=document_id,
                ip_address=client_ip,
                details={
                    "version_number": ver.version_number,
                    "expected_sha256": ver.file_hash_sha256,
                    "computed_sha256": computed_hash,
                    "storage_key": ver.storage_key,
                },
            )

            await self.audit_service.record_event(
                actor_id=current_user.id,
                action="INTEGRITY_MISMATCH",
                resource_type="document",
                resource_id=document_id,
                case_id=doc.case_id,
                details={
                    "version_number": ver.version_number,
                    "expected_sha256": ver.file_hash_sha256,
                    "computed_sha256": computed_hash,
                    "storage_key": ver.storage_key,
                },
                result="failure",
                ip_address=client_ip,
            )
            await self.session.commit()

            raise ValidationException(
                detail="Critical: Cryptographic integrity mismatch detected. Document has been altered or corrupted in storage. Download refused.",
                error_code="INTEGRITY_FAILED",
            )

        # Update last verified timestamp
        ver.last_verified_at = datetime.now(UTC)
        await self.session.commit()

        # Audit authorized download
        await self.audit_service.record_event(
            actor_id=current_user.id,
            action="DOCUMENT_DOWNLOADED",
            resource_type="document",
            resource_id=document_id,
            case_id=doc.case_id,
            details={
                "version_number": ver.version_number,
                "file_hash_sha256": ver.file_hash_sha256,
                "file_size_bytes": len(content),
            },
            result="success",
            ip_address=client_ip,
        )
        await self.session.commit()

        return content, ver.sanitized_filename, ver.mime_type

    async def verify_integrity(
        self,
        document_id: UUID,
        current_user: User,
        version_id: UUID | None = None,
        client_ip: str | None = None,
    ) -> DocumentIntegrityResponse:
        """Executes live cryptographic integrity verification against object storage."""
        doc = await self.doc_repo.get_document_by_id(document_id)
        if not doc:
            raise EntityNotFoundException(detail="Document not found", error_code="DOC_001")

        await self._verify_case_access(doc.case_id, current_user)

        if version_id:
            ver = await self.doc_repo.get_version_by_id(version_id)
            if not ver or ver.document_id != document_id:
                raise EntityNotFoundException(detail="Version not found", error_code="VER_001")
        else:
            ver = doc.current_version
            if not ver:
                raise EntityNotFoundException(detail="No active version available", error_code="VER_002")

        content = self.storage.download(ver.storage_key, ver.storage_bucket)
        computed_hash = hashlib.sha256(content).hexdigest().lower()
        is_match = computed_hash == ver.file_hash_sha256.lower()

        now = datetime.now(UTC)
        ver.last_verified_at = now
        ver.integrity_status = "verified" if is_match else "compromised"
        if not is_match:
            await self.security_repo.record_event(
                event_type="document.integrity_mismatch",
                severity="CRITICAL",
                category="INTEGRITY",
                actor_id=current_user.id,
                case_id=doc.case_id,
                resource_type="document",
                resource_id=document_id,
                ip_address=client_ip,
                details={
                    "version_number": ver.version_number,
                    "stored_hash": ver.file_hash_sha256,
                    "computed_hash": computed_hash,
                },
            )

        await self.audit_service.record_event(
            actor_id=current_user.id,
            action="INTEGRITY_VERIFIED" if is_match else "INTEGRITY_MISMATCH",
            resource_type="document",
            resource_id=document_id,
            case_id=doc.case_id,
            details={
                "version_number": ver.version_number,
                "stored_hash": ver.file_hash_sha256,
                "computed_hash": computed_hash,
                "match": is_match,
            },
            result="success" if is_match else "failure",
            ip_address=client_ip,
        )
        await self.session.commit()

        return DocumentIntegrityResponse(
            document_id=document_id,
            version_id=ver.id,
            version_number=ver.version_number,
            stored_hash=ver.file_hash_sha256,
            computed_hash=computed_hash,
            match=is_match,
            integrity_status=ver.integrity_status,
            verified_at=now,
        )

    def _build_document_response(self, doc: Document) -> DocumentResponse:
        """Serializes Document entity into Pydantic model."""
        cur_ver = None
        cur_hash = None
        if doc.current_version:
            cur_ver = self._build_version_response(doc.current_version)
            cur_hash = doc.current_version.file_hash_sha256

        uploader_name = doc.uploader.full_name if doc.uploader else None
        v_count = len(doc.versions) if doc.versions else 1

        return DocumentResponse(
            id=doc.id,
            case_id=doc.case_id,
            title=doc.title,
            description=doc.description,
            document_type=doc.document_type,
            classification=doc.classification,
            status=doc.status,
            current_version_id=doc.current_version_id,
            current_version=cur_ver,
            original_filename=doc.original_filename,
            mime_type=doc.mime_type,
            file_size_bytes=doc.file_size_bytes,
            file_hash_sha256=cur_hash,
            uploaded_by=doc.uploaded_by,
            uploaded_by_name=uploader_name,
            versions_count=v_count,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )

    def _build_version_response(self, ver: DocumentVersion) -> DocumentVersionResponse:
        """Serializes DocumentVersion entity into Pydantic model."""
        creator_name = ver.creator.full_name if ver.creator else None
        return DocumentVersionResponse(
            id=ver.id,
            document_id=ver.document_id,
            version_number=ver.version_number,
            file_hash_sha256=ver.file_hash_sha256,
            file_size_bytes=ver.file_size_bytes,
            mime_type=ver.mime_type,
            original_filename=ver.original_filename,
            sanitized_filename=ver.sanitized_filename,
            change_reason=ver.change_reason,
            created_by=ver.created_by,
            created_by_name=creator_name,
            is_original=ver.is_original,
            integrity_status=ver.integrity_status,
            created_at=ver.created_at,
            last_verified_at=ver.last_verified_at,
        )
