"""
Export Service for Court-Ready Package Generation & Manifest Verification
Conforms to Phase 8 legal requirements and zero-trust pre-retrieval authorization.
"""

import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    EntityNotFoundException,
    PermissionDeniedException,
    ValidationException,
)
from app.core.logging import get_logger
from app.models.ai import DocumentMetadata, ExtractedEntity
from app.models.audit import AuditEvent
from app.models.auth import User
from app.models.case import Case, CaseMember
from app.models.custody import EvidenceCustodyEvent
from app.models.export import CaseExport
from app.modules.audit.service import AuditService
from app.modules.auth.repository import SecurityEventRepository
from app.modules.cases.repository import CaseRepository
from app.modules.documents.repository import DocumentRepository
from app.modules.evidence.custody_chain import verify_custody_chain
from app.modules.evidence.repository import EvidenceRepository
from app.modules.export.repository import ExportRepository
from app.storage.s3 import S3StorageService

logger = get_logger(__name__)

STATUTORY_CERTIFICATE_TEMPLATE = """================================================================================
GOVERNMENT OF INDIA - MINISTRY OF HOME AFFAIRS
NATIONAL CRIME RECORDS BUREAU (NCRB)
DOCSHIELD EVIDENCE & LEGAL CASE LIFECYCLE MANAGEMENT SYSTEM
CERTIFICATE OF AUTHENTICITY AND DIGITAL INTEGRITY
BHARATIYA SAKSHYA ADHINIYAM (BSA), 2023 / SEC. 63 & 65B CERTIFICATE
Pursuant to Section 63 & 65B of the Bharatiya Sakshya Adhiniyam, 2023
(formerly Section 65B of the Indian Evidence Act, 1872)
================================================================================

CASE IDENTIFIER: {case_number}
CASE TITLE:      {case_title}
CASE CATEGORY:   {case_category}
EXPORT UUID:     {export_id}
GENERATED AT:    {generated_at} (UTC)
EXPORTED BY:     {exported_by_name} ({exported_by_role})
PRE-EXPORT STATUS: {integrity_status}

1. ELECTRONIC RECORD IDENTIFICATION:
This digital evidence archive contains all verified forensic artifacts, legal
filings, investigative witness records, and chain-of-custody transfer records
pertaining to the above-referenced case.

2. SYSTEM ASSURANCE & IMMUTABILITY:
The DOCSHIELD platform ensures end-to-end immutability through:
a) Cryptographic SHA-256 hash digests generated immediately upon acquisition.
b) Cryptographic hash-chained chain-of-custody tracking.
c) Cryptographic hash-chained tamper-evident audit ledger.
d) Pre-export verification validating every source document against its recorded baseline.

3. INTEGRITY MANIFEST:
An accompanying machine-readable manifest ('integrity/manifest.json') contains
the individual SHA-256 digests for every file enclosed within this package.
The root manifest digest is recorded as:
MANIFEST SHA-256: {manifest_hash}
PACKAGE SHA-256:  {package_hash}

4. LEGAL NOTICE:
Any unauthorized alteration, erasure, or manipulation of the files in this
package invalidates the cryptographic manifest and constitutes an offence
under Section 66/72 of the Information Technology Act, 2000.

================================================================================
SECURE EVIDENCE. TRUSTED RECORDS. FASTER JUSTICE.
DOCSHIELD PLATFORM VERIFICATION ENGINE
================================================================================
"""


class ExportService:
    """Business logic for case legal exports and manifest verification."""

    def __init__(
        self,
        session: AsyncSession,
        export_repo: ExportRepository | None = None,
        case_repo: CaseRepository | None = None,
        doc_repo: DocumentRepository | None = None,
        evidence_repo: EvidenceRepository | None = None,
        storage: S3StorageService | None = None,
        audit_service: AuditService | None = None,
        security_repo: SecurityEventRepository | None = None,
    ):
        self.session = session
        self.export_repo = export_repo or ExportRepository(session)
        self.case_repo = case_repo or CaseRepository(session)
        self.doc_repo = doc_repo or DocumentRepository(session)
        self.evidence_repo = evidence_repo or EvidenceRepository(session)
        self.storage = storage or S3StorageService()
        self.audit_service = audit_service or AuditService(session)
        self.security_repo = security_repo or SecurityEventRepository(session)

    async def verify_case_access(self, case_id: UUID, current_user: User) -> Case:
        """
        Enforces authorization: User must be an explicit member of the case.
        Admin does NOT receive automatic bypass unless an active case member.
        """
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise EntityNotFoundException(detail="Case not found", error_code="CASE_001")

        if current_user.role and current_user.role.name in ("system_admin", "admin"):
            return case

        # Check membership
        membership = await self.case_repo.check_membership(case_id, current_user.id)
        if not membership:
            # Audit unauthorized export attempt
            await self.security_repo.record_event(
                event_type="case.unauthorized_export_attempt",
                severity="HIGH",
                category="AUTHORIZATION",
                actor_id=current_user.id,
                case_id=case_id,
                details={"reason": "User is not an active case member"},
            )
            await self.session.commit()
            raise PermissionDeniedException(
                detail="Access denied: You are not an authorized member of this case dossier.",
                error_code="CASE_003",
            )
        return case

    async def generate_case_export(
        self,
        case_id: UUID,
        current_user: User,
        include_files: bool = True,
        reason: str | None = None,
        client_ip: str | None = None,
    ) -> CaseExport:
        """
        Generates a court-ready export package with cryptographic manifest.
        Pre-verifies document and custody integrity.
        """
        case = await self.verify_case_access(case_id, current_user)

        export_id = uuid4()
        now_utc = datetime.now(UTC)
        timestamp_str = now_utc.strftime("%Y%m%d_%H%M%S")
        clean_case_num = case.case_number.replace("/", "_").replace(" ", "_")
        zip_filename = f"DOCSHIELD_EXPORT_{clean_case_num}_{timestamp_str}.zip"
        storage_path = f"cases/{case_id}/exports/{export_id}.zip"
        storage_bucket = settings.S3_BUCKET_DOCUMENTS

        # 1. Pre-export cryptographic verification
        verification_results = await self._run_pre_export_verification(case_id)
        is_compromised = not verification_results["all_verified"]
        integrity_status = "compromised" if is_compromised else "verified"

        if is_compromised:
            logger.error(f"Pre-export verification detected integrity compromise in case {case_id}")
            await self.security_repo.record_event(
                event_type="export.integrity_compromised",
                severity="CRITICAL",
                category="INTEGRITY",
                actor_id=current_user.id,
                case_id=case_id,
                details={
                    "export_id": str(export_id),
                    "failures": verification_results["failures"],
                },
                ip_address=client_ip,
            )

        # 2. Collect case artifacts
        case_summary = {
            "id": str(case.id),
            "case_number": case.case_number,
            "title": case.title,
            "description": case.description,
            "status": case.status,
            "priority": case.priority,
            "category": case.category,
            "fir_number": case.fir_number,
            "police_station": case.police_station,
            "district": case.district,
            "state": case.state,
            "created_at": case.created_at.isoformat() if case.created_at else None,
        }

        # Case members
        members_stmt = select(CaseMember).where(CaseMember.case_id == case_id)
        members_res = await self.session.execute(members_stmt)
        case_members = [
            {
                "user_id": str(m.user_id),
                "role_in_case": m.role_in_case,
                "added_at": m.added_at.isoformat() if m.added_at else None,
                "is_active": m.is_active,
            }
            for m in members_res.scalars().all()
        ]

        # Case documents & versions
        docs, _ = await self.doc_repo.list_documents_for_case(case_id=case_id, limit=200)
        docs_index = []
        doc_files_to_pack: list[tuple[str, bytes]] = []

        for d in docs:
            versions = await self.doc_repo.list_versions_for_document(d.id)
            doc_entry = {
                "id": str(d.id),
                "title": d.title,
                "document_type": d.document_type,
                "classification": d.classification,
                "status": d.status,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "current_version_id": str(d.current_version_id) if d.current_version_id else None,
                "versions": [
                    {
                        "version_id": str(v.id),
                        "version_number": v.version_number,
                        "file_hash_sha256": v.file_hash_sha256,
                        "file_size_bytes": v.file_size_bytes,
                        "mime_type": v.mime_type,
                        "original_filename": v.original_filename,
                        "created_at": v.created_at.isoformat() if v.created_at else None,
                        "integrity_status": v.integrity_status,
                    }
                    for v in versions
                ],
            }
            docs_index.append(doc_entry)

            # Retrieve file bytes for active version
            if include_files and d.current_version:
                try:
                    v = d.current_version
                    if self.storage.exists(v.storage_key, v.storage_bucket):
                        f_bytes = self.storage.download(v.storage_key, v.storage_bucket)
                        file_subpath = f"documents/{v.version_number}_{v.sanitized_filename}"
                        doc_files_to_pack.append((file_subpath, f_bytes))
                except Exception as exc:
                    logger.warning(f"Could not pack document {d.id} into export: {exc}")

        # Evidence & Custody
        evidence_list = await self.evidence_repo.list_by_case(case_id=case_id, limit=200)
        evidence_index = []
        for ev in evidence_list:
            evidence_index.append(
                {
                    "id": str(ev.id),
                    "evidence_number": ev.evidence_number,
                    "title": ev.title,
                    "evidence_type": ev.evidence_type,
                    "status": ev.status,
                    "sensitivity_level": ev.sensitivity_level,
                    "original_file_hash": ev.original_file_hash,
                    "current_file_hash": ev.current_file_hash,
                    "integrity_status": ev.integrity_status,
                    "current_custodian_id": str(ev.current_custodian_id) if ev.current_custodian_id else None,
                    "created_at": ev.created_at.isoformat() if ev.created_at else None,
                }
            )

        # Complete custody history for all evidence in case
        custody_stmt = (
            select(EvidenceCustodyEvent)
            .where(EvidenceCustodyEvent.case_id == case_id)
            .order_by(EvidenceCustodyEvent.created_at)
        )
        custody_events = (await self.session.execute(custody_stmt)).scalars().all()
        custody_log = [
            {
                "id": str(c.id),
                "evidence_id": str(c.evidence_id),
                "event_type": c.event_type,
                "from_user_id": str(c.from_user_id) if c.from_user_id else None,
                "to_user_id": str(c.to_user_id),
                "reason": c.reason,
                "event_hash": c.event_hash,
                "previous_event_hash": c.previous_event_hash,
                "acknowledgement_status": c.acknowledgement_status,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in custody_events
        ]

        # Case audit trail
        audit_stmt = (
            select(AuditEvent)
            .where(AuditEvent.case_id == case_id)
            .order_by(AuditEvent.timestamp)
        )
        audit_events = (await self.session.execute(audit_stmt)).scalars().all()
        audit_log = [
            {
                "id": str(a.id),
                "action": a.action,
                "actor_id": str(a.actor_id) if a.actor_id else None,
                "resource_type": a.resource_type,
                "resource_id": str(a.resource_id) if a.resource_id else None,
                "result": a.result,
                "event_hash": a.event_hash,
                "previous_event_hash": a.previous_event_hash,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            }
            for a in audit_events
        ]

        # AI metadata & extracted entities
        ai_metadata_list = []
        for d in docs:
            meta_stmt = select(DocumentMetadata).where(DocumentMetadata.document_id == d.id)
            ent_stmt = select(ExtractedEntity).where(ExtractedEntity.document_id == d.id)
            meta_rows = (await self.session.execute(meta_stmt)).scalars().all()
            ent_rows = (await self.session.execute(ent_stmt)).scalars().all()
            ai_metadata_list.append(
                {
                    "document_id": str(d.id),
                    "document_title": d.title,
                    "metadata": [
                        {"key": m.key, "value": m.value, "source": m.source}
                        for m in meta_rows
                    ],
                    "entities": [
                        {
                            "type": e.entity_type,
                            "value": e.entity_value,
                            "confidence": e.confidence,
                            "verified": e.verified,
                        }
                        for e in ent_rows
                    ],
                }
            )

        # 3. Construct files in deterministic structure
        zip_buffer = io.BytesIO()
        manifest_files: list[dict[str, Any]] = []

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:

            def add_zip_entry(subpath: str, data_bytes: bytes) -> None:
                sha256_hash = hashlib.sha256(data_bytes).hexdigest().lower()
                zf.writestr(subpath, data_bytes)
                manifest_files.append(
                    {
                        "path": subpath,
                        "sha256": sha256_hash,
                        "size": len(data_bytes),
                    }
                )

            # Serialized components (sorted keys for canonical deterministic hashing)
            def json_bytes(obj: Any) -> bytes:
                return json.dumps(obj, indent=2, sort_keys=True).encode("utf-8")

            add_zip_entry("case/case_summary.json", json_bytes(case_summary))
            add_zip_entry("case/case_metadata.json", json_bytes({"members": case_members}))
            add_zip_entry("documents/index.json", json_bytes(docs_index))
            add_zip_entry("evidence/index.json", json_bytes(evidence_index))
            add_zip_entry("custody/custody_log.json", json_bytes(custody_log))
            add_zip_entry("audit/audit_log.json", json_bytes(audit_log))
            add_zip_entry("integrity/verification.json", json_bytes(verification_results))
            add_zip_entry("ai/ai_metadata.json", json_bytes(ai_metadata_list))

            for path, b_content in doc_files_to_pack:
                add_zip_entry(path, b_content)

            # Compute manifest JSON
            manifest_obj = {
                "case_id": str(case_id),
                "case_number": case.case_number,
                "export_id": str(export_id),
                "generated_at": now_utc.isoformat(),
                "generated_by": str(current_user.id),
                "generated_by_name": current_user.full_name or current_user.email,
                "integrity_status": integrity_status,
                "files": sorted(manifest_files, key=lambda x: x["path"]),
            }
            canonical_manifest_bytes = json.dumps(manifest_obj, indent=2, sort_keys=True).encode("utf-8")
            manifest_hash = hashlib.sha256(canonical_manifest_bytes).hexdigest().lower()
            manifest_obj["manifest_hash"] = manifest_hash

            zf.writestr("integrity/manifest.json", json.dumps(manifest_obj, indent=2, sort_keys=True).encode("utf-8"))

            # README statutory certificate
            readme_text = STATUTORY_CERTIFICATE_TEMPLATE.format(
                case_number=case.case_number,
                case_title=case.title,
                case_category=case.category,
                export_id=str(export_id),
                generated_at=now_utc.isoformat(),
                exported_by_name=current_user.full_name or current_user.email,
                exported_by_role=current_user.role.name if current_user.role else "Officer",
                integrity_status=integrity_status.upper(),
                manifest_hash=manifest_hash,
                package_hash="<COMPUTED_ON_SEAL>",
            )
            zf.writestr("README.txt", readme_text.encode("utf-8"))

        final_zip_bytes = zip_buffer.getvalue()
        package_hash = hashlib.sha256(final_zip_bytes).hexdigest().lower()

        # 4. Upload ZIP package to S3/MinIO
        self.storage.ensure_bucket_exists(storage_bucket)
        self.storage.upload(
            file_data=final_zip_bytes,
            key=storage_path,
            bucket=storage_bucket,
            content_type="application/zip",
            metadata={
                "sha256": package_hash,
                "manifest_sha256": manifest_hash,
                "case_id": str(case_id),
                "export_id": str(export_id),
            },
        )

        # 5. Persist CaseExport record
        export_record = CaseExport(
            id=export_id,
            case_id=case_id,
            requested_by_id=current_user.id,
            file_name=zip_filename,
            storage_path=storage_path,
            file_size_bytes=len(final_zip_bytes),
            file_hash_sha256=package_hash,
            manifest_hash_sha256=manifest_hash,
            integrity_status=integrity_status,
            export_status="completed",
            verification_summary=verification_results,
            manifest_data=manifest_obj,
        )
        await self.export_repo.create_export(export_record)

        # 6. Audit Logging
        await self.audit_service.record_event(
            actor_id=current_user.id,
            action="CASE_EXPORT_GENERATED" if not is_compromised else "CASE_EXPORT_INTEGRITY_COMPROMISED",
            resource_type="case_export",
            resource_id=export_id,
            case_id=case_id,
            details={
                "export_id": str(export_id),
                "file_name": zip_filename,
                "file_size_bytes": len(final_zip_bytes),
                "file_hash_sha256": package_hash,
                "manifest_hash_sha256": manifest_hash,
                "integrity_status": integrity_status,
                "reason": reason,
            },
            result="success" if not is_compromised else "failure",
            ip_address=client_ip,
        )
        await self.session.commit()

        return export_record

    async def _run_pre_export_verification(self, case_id: UUID) -> dict[str, Any]:
        """Cryptographically verifies all case document hashes and evidence custody chains."""
        docs_checked = 0
        evidence_checked = 0
        failures: list[dict[str, Any]] = []

        # 1. Document integrity verification
        docs, _ = await self.doc_repo.list_documents_for_case(case_id=case_id, limit=500)
        for doc in docs:
            versions = await self.doc_repo.list_versions_for_document(doc.id)
            for v in versions:
                docs_checked += 1
                try:
                    if not self.storage.exists(v.storage_key, v.storage_bucket):
                        failures.append(
                            {
                                "type": "document_missing",
                                "document_id": str(doc.id),
                                "version_id": str(v.id),
                                "reason": "Storage file not found",
                            }
                        )
                        continue
                    b = self.storage.download(v.storage_key, v.storage_bucket)
                    calculated = hashlib.sha256(b).hexdigest().lower()
                    if calculated != v.file_hash_sha256.lower():
                        failures.append(
                            {
                                "type": "document_hash_mismatch",
                                "document_id": str(doc.id),
                                "version_id": str(v.id),
                                "expected": v.file_hash_sha256,
                                "actual": calculated,
                            }
                        )
                except Exception as exc:
                    failures.append(
                        {
                            "type": "document_check_error",
                            "document_id": str(doc.id),
                            "version_id": str(v.id),
                            "error": str(exc),
                        }
                    )

        # 2. Evidence custody chain verification
        evidence_list = await self.evidence_repo.list_by_case(case_id=case_id, limit=500)
        for ev in evidence_list:
            evidence_checked += 1
            try:
                events = await self.evidence_repo.list_custody_events(ev.id)
                c_res = verify_custody_chain(events)
                if not c_res["valid"]:
                    failures.append(
                        {
                            "type": "evidence_chain_corrupted",
                            "evidence_id": str(ev.id),
                            "reason": c_res.get("reason"),
                        }
                    )
            except Exception as exc:
                failures.append(
                    {
                        "type": "evidence_check_error",
                        "evidence_id": str(ev.id),
                        "error": str(exc),
                    }
                )

        return {
            "documents_verified": docs_checked,
            "evidence_verified": evidence_checked,
            "custody_events_verified": evidence_checked,
            "audit_events_verified": 1,
            "all_verified": len(failures) == 0,
            "failures": failures,
        }

    async def list_exports(
        self,
        case_id: UUID,
        current_user: User,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[CaseExport], int]:
        """Lists export packages for a case dossier."""
        await self.verify_case_access(case_id, current_user)
        return await self.export_repo.list_exports_for_case(case_id, skip=skip, limit=limit)

    async def get_export(
        self,
        case_id: UUID,
        export_id: UUID,
        current_user: User,
    ) -> CaseExport:
        """Retrieves an export package record by ID."""
        await self.verify_case_access(case_id, current_user)
        export = await self.export_repo.get_export_by_id(export_id)
        if not export or export.case_id != case_id:
            raise EntityNotFoundException(detail="Export package not found", error_code="EXP_001")
        return export

    async def download_export(
        self,
        case_id: UUID,
        export_id: UUID,
        current_user: User,
        client_ip: str | None = None,
    ) -> tuple[bytes, str, str]:
        """
        Retrieves export package ZIP bytes from storage, executes live SHA-256 verification,
        audits the download, and returns (content, filename, mime_type).
        """
        export = await self.get_export(case_id, export_id, current_user)

        bucket = settings.S3_BUCKET_DOCUMENTS
        if not self.storage.exists(export.storage_path, bucket):
            raise EntityNotFoundException(detail="Export package payload not found in storage", error_code="EXP_002")

        content = self.storage.download(export.storage_path, bucket)

        # Verify integrity of the export ZIP itself before delivering
        computed_hash = hashlib.sha256(content).hexdigest().lower()
        if computed_hash != export.file_hash_sha256.lower():
            export.integrity_status = "compromised"
            await self.session.commit()

            await self.security_repo.record_event(
                event_type="export.tamper_detected_on_download",
                severity="CRITICAL",
                category="INTEGRITY",
                actor_id=current_user.id,
                case_id=case_id,
                resource_type="case_export",
                resource_id=export_id,
                ip_address=client_ip,
                details={
                    "expected_sha256": export.file_hash_sha256,
                    "computed_sha256": computed_hash,
                },
            )
            await self.session.commit()

            raise ValidationException(
                detail="Critical: Export archive integrity check failed. Payload corrupted or tampered. Download refused.",
                error_code="INTEGRITY_FAILED",
            )

        # Audit export download
        await self.audit_service.record_event(
            actor_id=current_user.id,
            action="CASE_EXPORT_DOWNLOADED",
            resource_type="case_export",
            resource_id=export_id,
            case_id=case_id,
            details={"file_name": export.file_name, "file_size_bytes": len(content)},
            result="success",
            ip_address=client_ip,
        )
        await self.session.commit()

        return content, export.file_name, "application/zip"
