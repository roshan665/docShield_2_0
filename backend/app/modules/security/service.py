"""
Security Service for Monitoring, Anomaly Detection & Tamper Simulation
Conforms to Phase 8 requirements and system invariants.
"""

import hashlib
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import EntityNotFoundException, ValidationException
from app.core.logging import get_logger
from app.models.auth import SecurityEvent, User
from app.modules.audit.service import AuditService
from app.modules.auth.repository import SecurityEventRepository
from app.modules.documents.repository import DocumentRepository
from app.modules.evidence.repository import EvidenceRepository
from app.storage.s3 import S3StorageService

logger = get_logger(__name__)


class SecurityService:
    """Business logic for security event auditing, metrics, and tamper detection."""

    def __init__(
        self,
        session: AsyncSession,
        security_repo: SecurityEventRepository | None = None,
        doc_repo: DocumentRepository | None = None,
        evidence_repo: EvidenceRepository | None = None,
        storage: S3StorageService | None = None,
        audit_service: AuditService | None = None,
    ):
        self.session = session
        self.security_repo = security_repo or SecurityEventRepository(session)
        self.doc_repo = doc_repo or DocumentRepository(session)
        self.evidence_repo = evidence_repo or EvidenceRepository(session)
        self.storage = storage or S3StorageService()
        self.audit_service = audit_service or AuditService(session)

    async def record_event(
        self,
        event_type: str,
        severity: str,
        actor_id: UUID | None = None,
        ip_address: str | None = None,
        details: dict[str, Any] | None = None,
        category: str | None = None,
        case_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
    ) -> SecurityEvent:
        """Records a security anomaly or compliance event."""
        logger.warning(
            f"Security Event: type={event_type} severity={severity} category={category} actor={actor_id}"
        )
        return await self.security_repo.record_event(
            event_type=event_type,
            severity=severity,
            actor_id=actor_id,
            ip_address=ip_address,
            details=details,
            category=category,
            case_id=case_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )

    async def list_events(
        self,
        skip: int = 0,
        limit: int = 50,
        severity: str | None = None,
        category: str | None = None,
        event_type: str | None = None,
        case_id: UUID | None = None,
        actor_id: UUID | None = None,
        resolved: bool | None = None,
    ) -> tuple[list[SecurityEvent], int]:
        """Lists security events with administrative filtering."""
        return await self.security_repo.list_events(
            skip=skip,
            limit=limit,
            severity=severity,
            category=category,
            event_type=event_type,
            case_id=case_id,
            actor_id=actor_id,
            resolved=resolved,
        )

    async def get_event_by_id(self, event_id: UUID) -> SecurityEvent:
        """Retrieves a single security event."""
        event = await self.security_repo.get_event_by_id(event_id)
        if not event:
            raise EntityNotFoundException(detail="Security event not found", error_code="SEC_001")
        return event

    async def resolve_event(self, event_id: UUID, current_user: User) -> SecurityEvent:
        """Marks a security incident as resolved by an administrator."""
        event = await self.security_repo.resolve_event(event_id, current_user.id)
        if not event:
            raise EntityNotFoundException(detail="Security event not found", error_code="SEC_001")

        await self.audit_service.record_event(
            actor_id=current_user.id,
            action="SECURITY_EVENT_RESOLVED",
            resource_type="security_event",
            resource_id=event_id,
            details={"resolved_by": str(current_user.id), "event_type": event.event_type},
            result="success",
        )
        await self.session.commit()
        return event

    async def get_metrics(self) -> dict[str, Any]:
        """Calculates security monitoring metrics for the administrative overview."""
        return await self.security_repo.get_metrics()

    async def simulate_tamper(
        self,
        target_type: str,
        target_id: UUID,
        current_user: User,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        Controlled tamper simulation for SIH presentation demonstration.
        Safely modifies stored object bytes in MinIO without mutating authoritative database hashes.
        Subsequent downloads or verifications will immediately detect the cryptographic mismatch.
        """
        target_type = target_type.lower()
        if target_type not in ["document", "evidence"]:
            raise ValidationException(
                detail="Target type must be 'document' or 'evidence'",
                error_code="SEC_002",
            )

        if target_type == "document":
            doc = await self.doc_repo.get_document_by_id(target_id)
            if not doc or not doc.current_version:
                raise EntityNotFoundException(detail="Target document not found", error_code="DOC_001")

            ver = doc.current_version
            prev_hash = ver.file_hash_sha256

            # Retrieve real storage payload
            current_bytes = self.storage.download(ver.storage_key, ver.storage_bucket)

            # Inject simulated tampering prefix
            tampered_bytes = b"[TAMPERED_FOR_DEMO_EVALUATION] " + current_bytes
            tampered_hash = hashlib.sha256(tampered_bytes).hexdigest().lower()

            # Overwrite MinIO object ONLY (authoritative DB hash is strictly preserved!)
            self.storage.upload(
                file_data=tampered_bytes,
                key=ver.storage_key,
                bucket=ver.storage_bucket,
                content_type=ver.mime_type or "application/octet-stream",
            )

            # Record security anomaly event
            sec_event = await self.record_event(
                event_type="document.tamper_simulated",
                severity="HIGH",
                category="INTEGRITY",
                actor_id=current_user.id,
                case_id=doc.case_id,
                resource_type="document",
                resource_id=target_id,
                ip_address=client_ip,
                details={
                    "previous_sha256": prev_hash,
                    "tampered_sha256": tampered_hash,
                    "storage_key": ver.storage_key,
                    "note": "Simulated tamper for SIH evaluation demonstration.",
                },
            )

            # Record audit event
            await self.audit_service.record_event(
                actor_id=current_user.id,
                action="DOCUMENT_TAMPER_SIMULATED",
                resource_type="document",
                resource_id=target_id,
                case_id=doc.case_id,
                details={"version_id": str(ver.id), "tampered_hash": tampered_hash},
                result="failure",
                ip_address=client_ip,
            )
            await self.session.commit()

            return {
                "message": "Document storage payload tampered successfully. Verification will now detect cryptographic failure.",
                "target_type": "document",
                "target_id": target_id,
                "previous_hash": prev_hash,
                "tampered_payload_hash": tampered_hash,
                "security_event_id": sec_event.id,
            }

        else:
            # Evidence tampering simulation
            evidence = await self.evidence_repo.get_by_id(target_id)
            if not evidence:
                raise EntityNotFoundException(detail="Target evidence not found", error_code="EVD_001")

            prev_hash = evidence.original_file_hash or evidence.current_file_hash or "none"
            bucket = evidence.storage_bucket or settings.S3_BUCKET_EVIDENCE
            key = evidence.storage_key or f"cases/{evidence.case_id}/evidence/{evidence.id}"

            current_bytes = b""
            if self.storage.exists(key, bucket):
                current_bytes = self.storage.download(key, bucket)
            else:
                current_bytes = b"EVIDENCE_DUMMY_PAYLOAD_FOR_DEMO"

            tampered_bytes = b"[TAMPERED_FOR_DEMO_EVALUATION] " + current_bytes
            tampered_hash = hashlib.sha256(tampered_bytes).hexdigest().lower()

            self.storage.ensure_bucket_exists(bucket)
            self.storage.upload(
                file_data=tampered_bytes,
                key=key,
                bucket=bucket,
                content_type=evidence.mime_type or "application/octet-stream",
            )

            sec_event = await self.record_event(
                event_type="evidence.tamper_simulated",
                severity="HIGH",
                category="INTEGRITY",
                actor_id=current_user.id,
                case_id=evidence.case_id,
                resource_type="evidence",
                resource_id=target_id,
                ip_address=client_ip,
                details={
                    "previous_sha256": prev_hash,
                    "tampered_sha256": tampered_hash,
                    "storage_key": key,
                    "note": "Simulated tamper for SIH evaluation demonstration.",
                },
            )

            await self.audit_service.record_event(
                actor_id=current_user.id,
                action="EVIDENCE_TAMPER_SIMULATED",
                resource_type="evidence",
                resource_id=target_id,
                case_id=evidence.case_id,
                details={"tampered_hash": tampered_hash},
                result="failure",
                ip_address=client_ip,
            )
            await self.session.commit()

            return {
                "message": "Evidence storage payload tampered successfully. Chain of custody verification will now detect cryptographic failure.",
                "target_type": "evidence",
                "target_id": target_id,
                "previous_hash": prev_hash,
                "tampered_payload_hash": tampered_hash,
                "security_event_id": sec_event.id,
            }
