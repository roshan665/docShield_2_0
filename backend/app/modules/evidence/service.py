"""
Evidence & Chain of Custody Business Logic Service
Coordinates evidence intake, two-phase custody transfers, state machine enforcement,
cryptographic hash chaining, and audit event recording.
"""

import hashlib
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    EntityNotFoundException,
    PermissionDeniedException,
    ValidationException,
)
from app.models.auth import User
from app.models.case import CaseMember
from app.models.custody import EvidenceCustodyEvent
from app.models.document import Document
from app.models.evidence import (
    EVIDENCE_SENSITIVITY,
    EVIDENCE_TYPES,
    Evidence,
)
from app.modules.audit.service import AuditService
from app.modules.cases.repository import CaseRepository
from app.modules.evidence.custody_chain import (
    GENESIS_HASH,
    canonicalize_custody_event,
    compute_custody_event_hash,
    verify_custody_chain,
)
from app.modules.evidence.repository import EvidenceRepository
from app.schemas.evidence import (
    CustodyChainVerificationResponse,
    CustodyEventResponse,
    EvidenceCustodyAcknowledgeRequest,
    EvidenceCustodyTransferRequest,
    EvidenceIntegrityResponse,
    EvidenceRegisterRequest,
    EvidenceResponse,
    EvidenceStatusTransitionRequest,
    EvidenceUpdateRequest,
)
from app.storage.s3 import S3StorageService
from app.storage.service import StorageService

# Strict Lifecycle State Machine Transitions
VALID_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "registered": ["in_custody"],
    "in_custody": ["in_analysis", "submitted_to_court"],
    "in_analysis": ["analyzed", "in_custody"],
    "analyzed": ["in_custody", "submitted_to_court"],
    "submitted_to_court": ["archived"],
    "archived": [],
}


class EvidenceService:
    """Service governing Evidence lifecycle, custody handover, and hash chain verification."""

    def __init__(
        self,
        session: AsyncSession,
        storage: StorageService | None = None,
    ):
        self.session = session
        self.repo = EvidenceRepository(session)
        self.case_repo = CaseRepository(session)
        self.audit_service = AuditService(session)
        self.storage = storage or S3StorageService()

    async def _verify_case_access(self, case_id: UUID, user: User) -> None:
        """
        Enforces zero-trust case membership.
        Non-members receive 404 Not Found to prevent case existence enumeration and IDOR.
        """
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise EntityNotFoundException(detail="Case not found", error_code="CASE_001")

        membership = await self.case_repo.check_membership(case_id, user.id)
        if not membership:
            raise EntityNotFoundException(detail="Case not found", error_code="CASE_001")

    async def _get_allowed_case_ids_for_user(self, user: User) -> list[UUID]:
        """Returns IDs of all cases where the user has active membership."""
        query = select(CaseMember.case_id).where(
            (CaseMember.user_id == user.id) & (CaseMember.is_active == True)  # noqa: E712
        )
        res = await self.session.execute(query)
        return list(res.scalars().all())

    def _to_response(self, ev: Evidence, event_count: int = 0) -> EvidenceResponse:
        """Maps Evidence model to Pydantic response."""
        return EvidenceResponse(
            id=ev.id,
            case_id=ev.case_id,
            document_id=ev.document_id,
            evidence_number=ev.evidence_number,
            title=ev.title,
            description=ev.description,
            evidence_type=ev.evidence_type,
            status=ev.status,
            sensitivity_level=ev.sensitivity_level,
            original_file_hash=ev.original_file_hash,
            current_file_hash=ev.current_file_hash,
            integrity_status=ev.integrity_status,
            current_custodian_id=ev.current_custodian_id,
            current_custodian_name=ev.current_custodian.full_name if ev.current_custodian else None,
            pending_custodian_id=ev.pending_custodian_id,
            pending_custodian_name=ev.pending_custodian.full_name if ev.pending_custodian else None,
            transfer_pending=ev.transfer_pending,
            transfer_reason=ev.transfer_reason,
            storage_key=ev.storage_key,
            storage_bucket=ev.storage_bucket,
            mime_type=ev.mime_type,
            file_size_bytes=ev.file_size_bytes,
            collection_date=ev.collection_date,
            collection_location=ev.collection_location,
            source=ev.source,
            registered_by_id=ev.registered_by_id,
            registered_by_name=ev.registered_by.full_name if ev.registered_by else None,
            created_at=ev.created_at,
            updated_at=ev.updated_at,
            archived_at=ev.archived_at,
            custody_events_count=event_count,
        )

    def _to_custody_response(self, evt: EvidenceCustodyEvent) -> CustodyEventResponse:
        """Maps EvidenceCustodyEvent model to Pydantic response."""
        return CustodyEventResponse(
            id=evt.id,
            evidence_id=evt.evidence_id,
            case_id=evt.case_id,
            event_type=evt.event_type,
            from_user_id=evt.from_user_id,
            to_user_id=evt.to_user_id,
            from_user_name=evt.from_user.full_name if evt.from_user else None,
            to_user_name=evt.to_user.full_name if evt.to_user else None,
            reason=evt.reason,
            location=evt.location,
            notes=evt.notes,
            file_hash_at_event=evt.file_hash_at_event,
            previous_event_hash=evt.previous_event_hash,
            event_hash=evt.event_hash,
            acknowledgement_status=evt.acknowledgement_status,
            acknowledged_at=evt.acknowledged_at,
            event_metadata=evt.event_metadata or {},
            created_at=evt.created_at,
        )

    async def register_evidence(
        self,
        case_id: UUID,
        req: EvidenceRegisterRequest,
        current_user: User,
    ) -> EvidenceResponse:
        """
        Registers a new evidence record in an authorized case context.
        Links document SHA-256 where applicable and establishes the genesis custody ledger event.
        """
        await self._verify_case_access(case_id, current_user)

        if req.evidence_type not in EVIDENCE_TYPES:
            raise ValidationException(detail=f"Invalid evidence type: '{req.evidence_type}'", error_code="EVID_001")

        if req.sensitivity_level not in EVIDENCE_SENSITIVITY:
            raise ValidationException(detail=f"Invalid sensitivity level: '{req.sensitivity_level}'", error_code="EVID_002")

        original_hash: str | None = None
        storage_key: str | None = None
        storage_bucket: str | None = None
        mime_type: str | None = None
        file_size_bytes: int | None = None

        # Digital Document Linkage
        if req.document_id:
            doc_stmt = (
                select(Document)
                .options(selectinload(Document.current_version))
                .where((Document.id == req.document_id) & (Document.case_id == case_id))
            )
            doc_res = await self.session.execute(doc_stmt)
            document = doc_res.scalar_one_or_none()
            if not document:
                raise ValidationException(
                    detail="Associated document not found in this case",
                    error_code="EVID_003",
                )
            if document.current_version:
                original_hash = document.current_version.file_hash_sha256
                mime_type = document.current_version.mime_type
                file_size_bytes = document.current_version.file_size_bytes
                storage_key = document.current_version.storage_key
                storage_bucket = document.current_version.storage_bucket
            else:
                original_hash = None
                mime_type = document.mime_type
                file_size_bytes = document.file_size_bytes
                storage_key = None
                storage_bucket = "sih190-documents"

        evidence_num = await self.repo.generate_evidence_number()
        now = datetime.now(UTC)

        evidence = Evidence(
            case_id=case_id,
            document_id=req.document_id,
            evidence_number=evidence_num,
            title=req.title.strip(),
            description=req.description.strip() if req.description else None,
            evidence_type=req.evidence_type,
            status="in_custody",  # Registered evidence directly enters custody of registering officer
            sensitivity_level=req.sensitivity_level,
            original_file_hash=original_hash,
            current_file_hash=original_hash,
            integrity_status="verified",
            current_custodian_id=current_user.id,
            pending_custodian_id=None,
            transfer_pending=False,
            transfer_reason=None,
            storage_key=storage_key,
            storage_bucket=storage_bucket,
            mime_type=mime_type,
            file_size_bytes=file_size_bytes,
            collection_date=req.collection_date,
            collection_location=req.collection_location.strip() if req.collection_location else None,
            source=req.source.strip() if req.source else None,
            registered_by_id=current_user.id,
            created_at=now,
            updated_at=now,
        )

        await self.repo.create_evidence(evidence)

        # 1. Establish Genesis Custody Event (H_0)
        canonical_bytes = canonicalize_custody_event(
            evidence_id=evidence.id,
            event_type="registered",
            from_user_id=None,
            to_user_id=current_user.id,
            reason=req.notes or "Initial evidence intake and registration into custody ledger",
            file_hash_at_event=original_hash,
            timestamp=now,
            location=req.collection_location,
        )
        genesis_event_hash = compute_custody_event_hash(canonical_bytes, GENESIS_HASH)

        custody_event = EvidenceCustodyEvent(
            evidence_id=evidence.id,
            case_id=case_id,
            event_type="registered",
            from_user_id=None,
            to_user_id=current_user.id,
            reason=req.notes or "Initial evidence intake and registration into custody ledger",
            location=req.collection_location,
            notes=f"Evidence {evidence_num} intake. Custodian assigned: {current_user.full_name}",
            file_hash_at_event=original_hash,
            previous_event_hash=GENESIS_HASH,
            event_hash=genesis_event_hash,
            acknowledgement_status="acknowledged",
            acknowledged_at=now,
            event_metadata={
                "evidence_number": evidence_num,
                "evidence_type": req.evidence_type,
                "original_hash": original_hash,
            },
            created_at=now,
        )
        await self.repo.create_custody_event(custody_event)

        # 2. Record system audit event
        await self.audit_service.record_event(
            actor_id=current_user.id,
            action="EVIDENCE_REGISTERED",
            resource_type="evidence",
            resource_id=evidence.id,
            case_id=case_id,
            details={
                "evidence_number": evidence_num,
                "title": req.title,
                "evidence_type": req.evidence_type,
                "custodian_id": str(current_user.id),
                "original_hash": original_hash,
            },
            result="success",
        )

        await self.session.commit()
        await self.session.refresh(evidence)
        return self._to_response(evidence, event_count=1)

    async def get_evidence(self, evidence_id: UUID, current_user: User) -> EvidenceResponse:
        """Retrieves evidence details with zero-trust case access check."""
        evidence = await self.repo.get_by_id(evidence_id)
        if not evidence:
            raise EntityNotFoundException(detail="Evidence not found", error_code="EVID_004")

        await self._verify_case_access(evidence.case_id, current_user)
        count = await self.repo.count_custody_events(evidence.id)
        return self._to_response(evidence, event_count=count)

    async def update_evidence(
        self,
        evidence_id: UUID,
        req: EvidenceUpdateRequest,
        current_user: User,
    ) -> EvidenceResponse:
        """Updates editable metadata on evidence record."""
        evidence = await self.repo.get_by_id(evidence_id)
        if not evidence:
            raise EntityNotFoundException(detail="Evidence not found", error_code="EVID_004")

        await self._verify_case_access(evidence.case_id, current_user)

        if req.title is not None:
            evidence.title = req.title.strip()
        if req.description is not None:
            evidence.description = req.description.strip()
        if req.sensitivity_level is not None:
            if req.sensitivity_level not in EVIDENCE_SENSITIVITY:
                raise ValidationException(detail="Invalid sensitivity level", error_code="EVID_002")
            evidence.sensitivity_level = req.sensitivity_level
        if req.collection_location is not None:
            evidence.collection_location = req.collection_location.strip()
        if req.source is not None:
            evidence.source = req.source.strip()

        evidence.updated_at = datetime.now(UTC)

        await self.audit_service.record_event(
            actor_id=current_user.id,
            action="EVIDENCE_METADATA_UPDATED",
            resource_type="evidence",
            resource_id=evidence.id,
            case_id=evidence.case_id,
            details={"evidence_number": evidence.evidence_number},
            result="success",
        )

        await self.session.commit()
        await self.session.refresh(evidence)
        count = await self.repo.count_custody_events(evidence.id)
        return self._to_response(evidence, event_count=count)

    async def list_case_evidence(
        self,
        case_id: UUID,
        current_user: User,
        evidence_type: str | None = None,
        status: str | None = None,
        custodian_id: UUID | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[EvidenceResponse]:
        """Lists all evidence in a case for an authorized member."""
        await self._verify_case_access(case_id, current_user)
        items = await self.repo.list_by_case(
            case_id=case_id,
            evidence_type=evidence_type,
            status=status,
            custodian_id=custodian_id,
            search=search,
            skip=skip,
            limit=limit,
        )
        return [self._to_response(it) for it in items]

    async def list_accessible_evidence(
        self,
        current_user: User,
        evidence_type: str | None = None,
        status: str | None = None,
        custodian_id: UUID | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[EvidenceResponse]:
        """Lists evidence across all assigned cases for the current officer."""
        allowed_case_ids = await self._get_allowed_case_ids_for_user(current_user)
        if not allowed_case_ids:
            return []

        items = await self.repo.list_accessible_evidence(
            allowed_case_ids=allowed_case_ids,
            evidence_type=evidence_type,
            status=status,
            custodian_id=custodian_id,
            search=search,
            skip=skip,
            limit=limit,
        )
        return [self._to_response(it) for it in items]

    async def initiate_custody_transfer(
        self,
        evidence_id: UUID,
        req: EvidenceCustodyTransferRequest,
        current_user: User,
    ) -> EvidenceResponse:
        """
        Initiates a two-phase custody transfer.
        The current custodian remains responsible until recipient explicitly acknowledges receipt.
        Uses PostgreSQL row-level locking (with_for_update) to prevent concurrent race conditions.
        """
        evidence = await self.repo.get_by_id_for_update(evidence_id)
        if not evidence:
            raise EntityNotFoundException(detail="Evidence not found", error_code="EVID_004")

        await self._verify_case_access(evidence.case_id, current_user)

        # 1. Caller must be current custodian
        if evidence.current_custodian_id != current_user.id:
            raise PermissionDeniedException(
                detail="Only the active custodian can initiate a custody handover",
                error_code="CUSTODY_001",
            )

        # 2. Prevent duplicate pending transfers
        if evidence.transfer_pending:
            raise ValidationException(
                detail="A custody transfer is already pending acknowledgement for this evidence",
                error_code="CUSTODY_002",
            )

        # 3. Recipient validation: cannot transfer to self
        if req.to_user_id == current_user.id:
            raise ValidationException(
                detail="Cannot transfer custody to yourself",
                error_code="CUSTODY_003",
            )

        # 4. Recipient validation: recipient must be an active member of this case
        recipient_membership = await self.case_repo.check_membership(evidence.case_id, req.to_user_id)
        if not recipient_membership:
            raise ValidationException(
                detail="Transfer recipient must be an active assigned officer in this case",
                error_code="CUSTODY_004",
            )

        now = datetime.now(UTC)
        evidence.transfer_pending = True
        evidence.pending_custodian_id = req.to_user_id
        evidence.transfer_reason = req.reason.strip()
        evidence.updated_at = now

        # Get predecessor event hash
        latest_event = await self.repo.get_latest_custody_event(evidence.id)
        prev_hash = latest_event.event_hash if latest_event else GENESIS_HASH

        canonical_bytes = canonicalize_custody_event(
            evidence_id=evidence.id,
            event_type="transfer_initiated",
            from_user_id=current_user.id,
            to_user_id=req.to_user_id,
            reason=req.reason,
            file_hash_at_event=evidence.current_file_hash,
            timestamp=now,
            location=req.location,
        )
        new_event_hash = compute_custody_event_hash(canonical_bytes, prev_hash)

        custody_event = EvidenceCustodyEvent(
            evidence_id=evidence.id,
            case_id=evidence.case_id,
            event_type="transfer_initiated",
            from_user_id=current_user.id,
            to_user_id=req.to_user_id,
            reason=req.reason.strip(),
            location=req.location.strip() if req.location else None,
            notes=req.notes.strip() if req.notes else "Custody transfer initiated and pending recipient acceptance",
            file_hash_at_event=evidence.current_file_hash,
            previous_event_hash=prev_hash,
            event_hash=new_event_hash,
            acknowledgement_status="pending",
            acknowledged_at=None,
            event_metadata={
                "from_custodian": str(current_user.id),
                "to_custodian": str(req.to_user_id),
            },
            created_at=now,
        )
        await self.repo.create_custody_event(custody_event)

        # Audit
        await self.audit_service.record_event(
            actor_id=current_user.id,
            action="CUSTODY_TRANSFER_INITIATED",
            resource_type="evidence",
            resource_id=evidence.id,
            case_id=evidence.case_id,
            details={
                "evidence_number": evidence.evidence_number,
                "from_custodian_id": str(current_user.id),
                "to_custodian_id": str(req.to_user_id),
                "reason": req.reason,
            },
            result="success",
        )

        await self.session.commit()
        await self.session.refresh(evidence)
        count = await self.repo.count_custody_events(evidence.id)
        return self._to_response(evidence, event_count=count)

    async def acknowledge_custody_transfer(
        self,
        evidence_id: UUID,
        req: EvidenceCustodyAcknowledgeRequest,
        current_user: User,
    ) -> EvidenceResponse:
        """
        Finalizes custody transfer upon explicit recipient acknowledgement.
        Updates current_custodian_id, clears pending state, and extends the custody hash chain.
        Uses PostgreSQL row-level locking (with_for_update).
        """
        evidence = await self.repo.get_by_id_for_update(evidence_id)
        if not evidence:
            raise EntityNotFoundException(detail="Evidence not found", error_code="EVID_004")

        await self._verify_case_access(evidence.case_id, current_user)

        # 1. Transfer must be pending
        if not evidence.transfer_pending or not evidence.pending_custodian_id:
            raise ValidationException(
                detail="No custody transfer is currently pending for this evidence",
                error_code="CUSTODY_005",
            )

        # 2. Only designated recipient can acknowledge
        if evidence.pending_custodian_id != current_user.id:
            raise PermissionDeniedException(
                detail="Only the designated recipient officer can acknowledge custody handover",
                error_code="CUSTODY_006",
            )

        now = datetime.now(UTC)
        previous_custodian_id = evidence.current_custodian_id

        # Update evidence custody
        evidence.current_custodian_id = current_user.id
        evidence.pending_custodian_id = None
        evidence.transfer_pending = False
        transfer_reason = evidence.transfer_reason or "Custody transfer acknowledged"
        evidence.transfer_reason = None
        evidence.updated_at = now

        # If evidence was in 'registered' status, advance to 'in_custody'
        if evidence.status == "registered":
            evidence.status = "in_custody"

        # Extend custody hash chain
        latest_event = await self.repo.get_latest_custody_event(evidence.id)
        prev_hash = latest_event.event_hash if latest_event else GENESIS_HASH

        canonical_bytes = canonicalize_custody_event(
            evidence_id=evidence.id,
            event_type="transfer_acknowledged",
            from_user_id=previous_custodian_id,
            to_user_id=current_user.id,
            reason=f"Custody receipt acknowledged: {transfer_reason}",
            file_hash_at_event=evidence.current_file_hash,
            timestamp=now,
            location=req.location,
        )
        new_event_hash = compute_custody_event_hash(canonical_bytes, prev_hash)

        custody_event = EvidenceCustodyEvent(
            evidence_id=evidence.id,
            case_id=evidence.case_id,
            event_type="transfer_acknowledged",
            from_user_id=previous_custodian_id,
            to_user_id=current_user.id,
            reason=f"Custody receipt acknowledged: {transfer_reason}",
            location=req.location.strip() if req.location else None,
            notes=req.notes.strip() if req.notes else "Evidence received and verified in good order by recipient officer",
            file_hash_at_event=evidence.current_file_hash,
            previous_event_hash=prev_hash,
            event_hash=new_event_hash,
            acknowledgement_status="acknowledged",
            acknowledged_at=now,
            event_metadata={
                "previous_custodian": str(previous_custodian_id),
                "new_custodian": str(current_user.id),
            },
            created_at=now,
        )
        await self.repo.create_custody_event(custody_event)

        # Audit
        await self.audit_service.record_event(
            actor_id=current_user.id,
            action="CUSTODY_TRANSFER_ACKNOWLEDGED",
            resource_type="evidence",
            resource_id=evidence.id,
            case_id=evidence.case_id,
            details={
                "evidence_number": evidence.evidence_number,
                "previous_custodian_id": str(previous_custodian_id),
                "new_custodian_id": str(current_user.id),
            },
            result="success",
        )

        await self.session.commit()
        await self.session.refresh(evidence)
        count = await self.repo.count_custody_events(evidence.id)
        return self._to_response(evidence, event_count=count)

    async def cancel_custody_transfer(
        self,
        evidence_id: UUID,
        current_user: User,
    ) -> EvidenceResponse:
        """Allows active custodian to cancel a pending transfer before it is acknowledged."""
        evidence = await self.repo.get_by_id_for_update(evidence_id)
        if not evidence:
            raise EntityNotFoundException(detail="Evidence not found", error_code="EVID_004")

        await self._verify_case_access(evidence.case_id, current_user)

        if evidence.current_custodian_id != current_user.id:
            raise PermissionDeniedException(detail="Only the current custodian can retract a transfer", error_code="CUSTODY_001")

        if not evidence.transfer_pending:
            raise ValidationException(detail="No pending transfer to cancel", error_code="CUSTODY_007")

        now = datetime.now(UTC)
        pending_target = evidence.pending_custodian_id
        evidence.transfer_pending = False
        evidence.pending_custodian_id = None
        evidence.transfer_reason = None
        evidence.updated_at = now

        latest_event = await self.repo.get_latest_custody_event(evidence.id)
        prev_hash = latest_event.event_hash if latest_event else GENESIS_HASH

        canonical_bytes = canonicalize_custody_event(
            evidence_id=evidence.id,
            event_type="transfer_cancelled",
            from_user_id=current_user.id,
            to_user_id=current_user.id,
            reason="Pending custody handover retracted by initiating custodian",
            file_hash_at_event=evidence.current_file_hash,
            timestamp=now,
        )
        new_event_hash = compute_custody_event_hash(canonical_bytes, prev_hash)

        custody_event = EvidenceCustodyEvent(
            evidence_id=evidence.id,
            case_id=evidence.case_id,
            event_type="transfer_cancelled",
            from_user_id=current_user.id,
            to_user_id=current_user.id,
            reason="Pending custody handover retracted by initiating custodian",
            notes="Transfer cancelled prior to recipient acknowledgement",
            file_hash_at_event=evidence.current_file_hash,
            previous_event_hash=prev_hash,
            event_hash=new_event_hash,
            acknowledgement_status="cancelled",
            acknowledged_at=now,
            event_metadata={"cancelled_recipient": str(pending_target)},
            created_at=now,
        )
        await self.repo.create_custody_event(custody_event)

        await self.audit_service.record_event(
            actor_id=current_user.id,
            action="CUSTODY_TRANSFER_CANCELLED",
            resource_type="evidence",
            resource_id=evidence.id,
            case_id=evidence.case_id,
            details={"evidence_number": evidence.evidence_number},
            result="success",
        )

        await self.session.commit()
        await self.session.refresh(evidence)
        count = await self.repo.count_custody_events(evidence.id)
        return self._to_response(evidence, event_count=count)

    async def transition_status(
        self,
        evidence_id: UUID,
        req: EvidenceStatusTransitionRequest,
        current_user: User,
    ) -> EvidenceResponse:
        """
        Enforces legal state machine transitions for evidence lifecycle.
        Validates transition path, updates lifecycle state, records custody event, and audits.
        """
        evidence = await self.repo.get_by_id_for_update(evidence_id)
        if not evidence:
            raise EntityNotFoundException(detail="Evidence not found", error_code="EVID_004")

        await self._verify_case_access(evidence.case_id, current_user)

        target = req.target_status.lower()
        allowed = VALID_STATUS_TRANSITIONS.get(evidence.status, [])
        if target not in allowed:
            raise ValidationException(
                detail=f"Illegal status transition from '{evidence.status}' to '{target}'. Allowed: {allowed}",
                error_code="EVID_005",
            )

        now = datetime.now(UTC)
        old_status = evidence.status
        evidence.status = target
        evidence.updated_at = now
        if target == "archived":
            evidence.archived_at = now

        # Extend custody hash chain with status change event
        latest_event = await self.repo.get_latest_custody_event(evidence.id)
        prev_hash = latest_event.event_hash if latest_event else GENESIS_HASH

        canonical_bytes = canonicalize_custody_event(
            evidence_id=evidence.id,
            event_type=target,
            from_user_id=current_user.id,
            to_user_id=evidence.current_custodian_id,
            reason=req.reason,
            file_hash_at_event=evidence.current_file_hash,
            timestamp=now,
            location=req.location,
        )
        new_event_hash = compute_custody_event_hash(canonical_bytes, prev_hash)

        custody_event = EvidenceCustodyEvent(
            evidence_id=evidence.id,
            case_id=evidence.case_id,
            event_type=target,
            from_user_id=current_user.id,
            to_user_id=evidence.current_custodian_id,
            reason=req.reason.strip(),
            location=req.location.strip() if req.location else None,
            notes=req.notes.strip() if req.notes else f"Lifecycle progression: {old_status} -> {target}",
            file_hash_at_event=evidence.current_file_hash,
            previous_event_hash=prev_hash,
            event_hash=new_event_hash,
            acknowledgement_status="acknowledged",
            acknowledged_at=now,
            event_metadata={"old_status": old_status, "new_status": target},
            created_at=now,
        )
        await self.repo.create_custody_event(custody_event)

        # Audit
        await self.audit_service.record_event(
            actor_id=current_user.id,
            action="EVIDENCE_STATUS_TRANSITION",
            resource_type="evidence",
            resource_id=evidence.id,
            case_id=evidence.case_id,
            details={
                "evidence_number": evidence.evidence_number,
                "old_status": old_status,
                "new_status": target,
                "reason": req.reason,
            },
            result="success",
        )

        await self.session.commit()
        await self.session.refresh(evidence)
        count = await self.repo.count_custody_events(evidence.id)
        return self._to_response(evidence, event_count=count)

    async def list_custody_events(
        self,
        evidence_id: UUID,
        current_user: User,
    ) -> list[CustodyEventResponse]:
        """Retrieves complete chronological custody history for authorized case members."""
        evidence = await self.repo.get_by_id(evidence_id)
        if not evidence:
            raise EntityNotFoundException(detail="Evidence not found", error_code="EVID_004")

        await self._verify_case_access(evidence.case_id, current_user)
        events = await self.repo.list_custody_events(evidence.id)
        return [self._to_custody_response(e) for e in events]

    async def verify_custody_chain(
        self,
        evidence_id: UUID,
        current_user: User,
    ) -> CustodyChainVerificationResponse:
        """
        Cryptographically verifies the sequential custody hash chain for an evidence record.
        Detects tampering, missing records, or broken links.
        """
        evidence = await self.repo.get_by_id(evidence_id)
        if not evidence:
            raise EntityNotFoundException(detail="Evidence not found", error_code="EVID_004")

        await self._verify_case_access(evidence.case_id, current_user)
        events = await self.repo.list_custody_events(evidence.id)
        result = verify_custody_chain(events)

        # Audit verification
        await self.audit_service.record_event(
            actor_id=current_user.id,
            action="CUSTODY_CHAIN_VERIFIED",
            resource_type="evidence",
            resource_id=evidence.id,
            case_id=evidence.case_id,
            details={
                "evidence_number": evidence.evidence_number,
                "valid": result["valid"],
                "events_checked": result["events_checked"],
            },
            result="success" if result["valid"] else "failure",
        )
        await self.session.commit()

        return CustodyChainVerificationResponse(
            valid=result["valid"],
            events_checked=result["events_checked"],
            first_invalid_event=result["first_invalid_event"],
            reason=result["reason"],
            genesis_hash=result["genesis_hash"],
            tip_hash=result["tip_hash"],
        )

    async def verify_evidence_integrity(
        self,
        evidence_id: UUID,
        current_user: User,
    ) -> EvidenceIntegrityResponse:
        """
        Verifies the digital integrity of evidence against authoritative original SHA-256 hash.
        If underlying storage bytes have been tampered with or modified, raises security alert and audits.
        """
        evidence = await self.repo.get_by_id(evidence_id)
        if not evidence:
            raise EntityNotFoundException(detail="Evidence not found", error_code="EVID_004")

        await self._verify_case_access(evidence.case_id, current_user)

        now = datetime.now(UTC)

        # Physical / Non-digital evidence has no storage payload to stream
        if not evidence.storage_key:
            return EvidenceIntegrityResponse(
                evidence_id=evidence.id,
                original_hash=evidence.original_file_hash,
                current_hash=evidence.current_file_hash,
                match=True,
                integrity_status="verified",
                checked_at=now,
            )

        # Digital artifact verification from MinIO / S3 storage
        try:
            stored_stream = self.storage.download_stream(
                key=evidence.storage_key,
                bucket=evidence.storage_bucket or "sih190-documents",
            )
            hasher = hashlib.sha256()
            for chunk in stored_stream:
                hasher.update(chunk)
            calculated_hash = hasher.hexdigest().lower()
        except Exception as e:
            evidence.integrity_status = "compromised"
            await self.session.commit()
            raise ValidationException(
                detail=f"Storage retrieval failed during integrity verification: {str(e)}",
                error_code="STORAGE_002",
            ) from e

        match = calculated_hash == (evidence.original_file_hash or "").lower()
        evidence.current_file_hash = calculated_hash
        evidence.integrity_status = "verified" if match else "compromised"
        evidence.updated_at = now

        if not match:
            # Audit security alert: Never silently replace authoritative original hash
            await self.audit_service.record_event(
                actor_id=current_user.id,
                action="INTEGRITY_MISMATCH",
                resource_type="evidence",
                resource_id=evidence.id,
                case_id=evidence.case_id,
                details={
                    "evidence_number": evidence.evidence_number,
                    "original_hash": evidence.original_file_hash,
                    "calculated_hash": calculated_hash,
                    "storage_key": evidence.storage_key,
                },
                result="failure",
            )
        else:
            await self.audit_service.record_event(
                actor_id=current_user.id,
                action="EVIDENCE_INTEGRITY_VERIFIED",
                resource_type="evidence",
                resource_id=evidence.id,
                case_id=evidence.case_id,
                details={
                    "evidence_number": evidence.evidence_number,
                    "hash": calculated_hash,
                },
                result="success",
            )

        await self.session.commit()

        return EvidenceIntegrityResponse(
            evidence_id=evidence.id,
            original_hash=evidence.original_file_hash,
            current_hash=calculated_hash,
            match=match,
            integrity_status=evidence.integrity_status,
            checked_at=now,
        )
