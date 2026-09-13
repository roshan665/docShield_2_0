"""
Evidence & Chain of Custody REST API Router
Exposes secure evidence registration, two-phase custody handover, state machine progression,
cryptographic chain verification, and digital artifact integrity audits.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.models.auth import User
from app.modules.auth.dependencies import get_current_user
from app.modules.evidence.dependencies import get_evidence_service
from app.modules.evidence.service import EvidenceService
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

evidence_router = APIRouter(tags=["Evidence & Chain of Custody"])


# ==============================================================================
# 1. Evidence Registration & Case Scoping
# ==============================================================================


@evidence_router.post(
    "/cases/{case_id}/evidence",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_case_evidence(
    case_id: UUID,
    data: EvidenceRegisterRequest,
    current_user: User = Depends(get_current_user),
    service: EvidenceService = Depends(get_evidence_service),
) -> EvidenceResponse:
    """
    Registers new physical or digital evidence within an authorized case context.
    Captures authoritative SHA-256 for digital artifacts, sets registering officer
    as initial custodian, and records the genesis custody ledger event.
    """
    return await service.register_evidence(
        case_id=case_id,
        req=data,
        current_user=current_user,
    )


@evidence_router.get(
    "/cases/{case_id}/evidence",
    response_model=list[EvidenceResponse],
)
async def list_case_evidence(
    case_id: UUID,
    evidence_type: str | None = Query(None),
    status: str | None = Query(None),
    custodian_id: UUID | None = Query(None),
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: EvidenceService = Depends(get_evidence_service),
) -> list[EvidenceResponse]:
    """Lists all evidence records registered under a specific case."""
    return await service.list_case_evidence(
        case_id=case_id,
        current_user=current_user,
        evidence_type=evidence_type,
        status=status,
        custodian_id=custodian_id,
        search=search,
        skip=skip,
        limit=limit,
    )


@evidence_router.get(
    "/evidence",
    response_model=list[EvidenceResponse],
)
async def list_all_accessible_evidence(
    case_id: UUID | None = Query(None),
    custodian: str | None = Query(None, description="Set to 'me' to filter for current user's custody"),
    evidence_type: str | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: EvidenceService = Depends(get_evidence_service),
) -> list[EvidenceResponse]:
    """
    Global Evidence Vault: Lists evidence records across all assigned cases for the current officer.
    Supports ?custodian=me filter for active custody tracking.
    """
    filter_custodian_id = current_user.id if custodian == "me" else None

    if case_id:
        return await service.list_case_evidence(
            case_id=case_id,
            current_user=current_user,
            evidence_type=evidence_type,
            status=status,
            custodian_id=filter_custodian_id,
            search=search,
            skip=skip,
            limit=limit,
        )

    return await service.list_accessible_evidence(
        current_user=current_user,
        evidence_type=evidence_type,
        status=status,
        custodian_id=filter_custodian_id,
        search=search,
        skip=skip,
        limit=limit,
    )


@evidence_router.get(
    "/evidence/{evidence_id}",
    response_model=EvidenceResponse,
)
async def get_evidence_details(
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    service: EvidenceService = Depends(get_evidence_service),
) -> EvidenceResponse:
    """Retrieves full evidence record details. Enforces active case membership."""
    return await service.get_evidence(
        evidence_id=evidence_id,
        current_user=current_user,
    )


@evidence_router.patch(
    "/evidence/{evidence_id}",
    response_model=EvidenceResponse,
)
async def update_evidence_metadata(
    evidence_id: UUID,
    data: EvidenceUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: EvidenceService = Depends(get_evidence_service),
) -> EvidenceResponse:
    """Updates editable metadata on evidence record."""
    return await service.update_evidence(
        evidence_id=evidence_id,
        req=data,
        current_user=current_user,
    )


# ==============================================================================
# 2. Custody Handover Protocol (Two-Phase: Transfer -> Acknowledge)
# ==============================================================================


@evidence_router.post(
    "/evidence/{evidence_id}/custody/transfer",
    response_model=EvidenceResponse,
)
@evidence_router.post(
    "/evidence/{evidence_id}/transfer",
    response_model=EvidenceResponse,
    include_in_schema=False,
)
async def initiate_custody_transfer(
    evidence_id: UUID,
    data: EvidenceCustodyTransferRequest,
    current_user: User = Depends(get_current_user),
    service: EvidenceService = Depends(get_evidence_service),
) -> EvidenceResponse:
    """
    Phase 1: Initiates a custody transfer.
    Only the active custodian can initiate. Marks transfer as pending.
    Current custodian remains legally responsible until recipient acknowledges.
    """
    return await service.initiate_custody_transfer(
        evidence_id=evidence_id,
        req=data,
        current_user=current_user,
    )


@evidence_router.post(
    "/evidence/{evidence_id}/custody/acknowledge",
    response_model=EvidenceResponse,
)
@evidence_router.post(
    "/evidence/{evidence_id}/receive",
    response_model=EvidenceResponse,
    include_in_schema=False,
)
async def acknowledge_custody_transfer(
    evidence_id: UUID,
    data: EvidenceCustodyAcknowledgeRequest,
    current_user: User = Depends(get_current_user),
    service: EvidenceService = Depends(get_evidence_service),
) -> EvidenceResponse:
    """
    Phase 2: Recipient acknowledges receipt of evidence.
    Only the designated recipient officer can acknowledge.
    Updates current custodian, clears pending transfer, and seals custody event hash.
    """
    return await service.acknowledge_custody_transfer(
        evidence_id=evidence_id,
        req=data,
        current_user=current_user,
    )


@evidence_router.post(
    "/evidence/{evidence_id}/custody/cancel",
    response_model=EvidenceResponse,
)
async def cancel_custody_transfer(
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    service: EvidenceService = Depends(get_evidence_service),
) -> EvidenceResponse:
    """Allows active custodian to cancel a pending transfer prior to recipient acknowledgement."""
    return await service.cancel_custody_transfer(
        evidence_id=evidence_id,
        current_user=current_user,
    )


# ==============================================================================
# 3. Evidence Lifecycle State Machine
# ==============================================================================


@evidence_router.post(
    "/evidence/{evidence_id}/status",
    response_model=EvidenceResponse,
)
async def transition_evidence_status(
    evidence_id: UUID,
    data: EvidenceStatusTransitionRequest,
    current_user: User = Depends(get_current_user),
    service: EvidenceService = Depends(get_evidence_service),
) -> EvidenceResponse:
    """
    Transitions evidence lifecycle status according to legal state machine rules.
    (registered -> in_custody -> in_analysis -> analyzed -> submitted_to_court -> archived).
    """
    return await service.transition_status(
        evidence_id=evidence_id,
        req=data,
        current_user=current_user,
    )


# ==============================================================================
# 4. Chain of Custody Ledger & Cryptographic Verification
# ==============================================================================


@evidence_router.get(
    "/evidence/{evidence_id}/custody",
    response_model=list[CustodyEventResponse],
)
@evidence_router.get(
    "/evidence/{evidence_id}/custody-chain",
    response_model=list[CustodyEventResponse],
    include_in_schema=False,
)
async def list_custody_history(
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    service: EvidenceService = Depends(get_evidence_service),
) -> list[CustodyEventResponse]:
    """Retrieves full chronological custody history for an evidence record."""
    return await service.list_custody_events(
        evidence_id=evidence_id,
        current_user=current_user,
    )


@evidence_router.get(
    "/evidence/{evidence_id}/custody/verify",
    response_model=CustodyChainVerificationResponse,
)
async def verify_custody_ledger(
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    service: EvidenceService = Depends(get_evidence_service),
) -> CustodyChainVerificationResponse:
    """
    Cryptographically verifies the sequential custody hash chain.
    Validates H_n = SHA256(canonical_event_data || H_(n-1)) from genesis to tip.
    """
    return await service.verify_custody_chain(
        evidence_id=evidence_id,
        current_user=current_user,
    )


# ==============================================================================
# 5. Digital Artifact Integrity Verification
# ==============================================================================


@evidence_router.get(
    "/evidence/{evidence_id}/verify",
    response_model=EvidenceIntegrityResponse,
)
async def verify_evidence_digital_integrity(
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    service: EvidenceService = Depends(get_evidence_service),
) -> EvidenceIntegrityResponse:
    """
    Live on-demand verification of underlying digital file payload against authoritative original SHA-256.
    Detects storage corruption or unauthorized tampering.
    """
    return await service.verify_evidence_integrity(
        evidence_id=evidence_id,
        current_user=current_user,
    )

