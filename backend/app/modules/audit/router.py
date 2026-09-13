"""
Audit Trail & Verification REST Router (/api/v1/audit and /api/v1/admin/audit)
Exposes append-only audit event queries and cryptographic hash-chain verification.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.models.auth import User
from app.modules.audit.service import AuditService
from app.modules.auth.dependencies import require_role
from app.modules.cases.dependencies import get_audit_service
from app.schemas.audit import AuditEventResponse, AuditVerificationResponse

audit_router = APIRouter(prefix="/audit", tags=["Audit Trail"])
admin_audit_router = APIRouter(prefix="/admin/audit", tags=["Audit Administration"])


@audit_router.get("/events", response_model=list[AuditEventResponse])
async def list_audit_events(
    case_id: UUID | None = Query(None),
    actor_id: UUID | None = Query(None),
    resource_type: str | None = Query(None),
    action: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_role("supervisor", "system_admin")),
    audit_service: AuditService = Depends(get_audit_service),
) -> list[AuditEventResponse]:
    """
    Lists audit events with filtering and pagination.
    Authorized for Supervisors and System Administrators.
    """
    events, _ = await audit_service.list_events(
        case_id=case_id,
        actor_id=actor_id,
        resource_type=resource_type,
        action=action,
        skip=skip,
        limit=limit,
    )
    return [
        AuditEventResponse(
            id=e.id,
            actor_id=e.actor_id,
            actor_name=e.actor.full_name if e.actor else "System",
            actor_email=e.actor.email if e.actor else None,
            action=e.action,
            resource_type=e.resource_type,
            resource_id=e.resource_id,
            case_id=e.case_id,
            details=e.details,
            result=e.result,
            ip_address=e.ip_address,
            previous_event_hash=e.previous_event_hash,
            event_hash=e.event_hash,
            timestamp=e.timestamp,
        )
        for e in events
    ]


@admin_audit_router.get("/verify", response_model=AuditVerificationResponse)
@audit_router.post("/verify-chain", response_model=AuditVerificationResponse)
async def verify_audit_chain(
    limit: int | None = Query(None, ge=1, le=10000),
    current_user: User = Depends(require_role("system_admin", "supervisor")),
    audit_service: AuditService = Depends(get_audit_service),
) -> AuditVerificationResponse:
    """
    Cryptographically verifies the append-only audit hash chain from genesis to tip.
    Validates that each event's SHA-256 hash matches its canonical data and
    strictly links to the predecessor's hash.
    """
    res = await audit_service.verify_chain(limit=limit)
    return AuditVerificationResponse(**res)
