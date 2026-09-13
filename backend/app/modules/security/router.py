"""
Security Monitoring & Tamper Detection REST Router
Provides administrative security visibility, anomaly alerting, and presentation-safe tamper simulation.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.auth import User
from app.modules.auth.dependencies import get_current_user, require_role
from app.modules.security.service import SecurityService
from app.schemas.security import (
    SecurityEventListResponse,
    SecurityEventResponse,
    SecurityMetricsResponse,
    TamperSimulationRequest,
    TamperSimulationResponse,
)

security_router = APIRouter(prefix="/security", tags=["Security Monitoring & Incident Response"])


async def get_security_service(session: AsyncSession = Depends(get_db)) -> SecurityService:
    return SecurityService(session)


@security_router.get(
    "/metrics",
    response_model=SecurityMetricsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_security_metrics(
    current_user: User = Depends(require_role("system_admin", "supervisor")),
    security_service: SecurityService = Depends(get_security_service),
) -> SecurityMetricsResponse:
    """
    Returns aggregated security metrics for the administrative overview dashboard.
    Accessible only to System Administrators and Supervisors.
    """
    data = await security_service.get_metrics()
    return SecurityMetricsResponse(
        total_events=data["total_events"],
        critical_events=data["critical_events"],
        high_events=data["high_events"],
        medium_events=data["medium_events"],
        low_events=data["low_events"],
        info_events=data["info_events"],
        failed_logins=data["failed_logins"],
        locked_accounts=data["locked_accounts"],
        integrity_violations=data["integrity_violations"],
        malicious_files=data["malicious_files"],
        unauthorized_access_attempts=data["unauthorized_access_attempts"],
        rate_limit_events=data["rate_limit_events"],
        category_breakdown=data["category_breakdown"],
        recent_critical_events=[
            SecurityEventResponse.model_validate(x) for x in data["recent_critical_events"]
        ],
    )


@security_router.get(
    "/events",
    response_model=SecurityEventListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_security_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    severity: str | None = Query(None),
    category: str | None = Query(None),
    event_type: str | None = Query(None),
    case_id: UUID | None = Query(None),
    actor_id: UUID | None = Query(None),
    resolved: bool | None = Query(None),
    current_user: User = Depends(require_role("system_admin", "supervisor")),
    security_service: SecurityService = Depends(get_security_service),
) -> SecurityEventListResponse:
    """
    Lists security events with administrative filtering and pagination.
    Accessible only to System Administrators and Supervisors.
    """
    items, total = await security_service.list_events(
        skip=skip,
        limit=limit,
        severity=severity,
        category=category,
        event_type=event_type,
        case_id=case_id,
        actor_id=actor_id,
        resolved=resolved,
    )
    return SecurityEventListResponse(
        items=[SecurityEventResponse.model_validate(x) for x in items],
        total=total,
    )


@security_router.get(
    "/events/{event_id}",
    response_model=SecurityEventResponse,
    status_code=status.HTTP_200_OK,
)
async def get_security_event(
    event_id: UUID,
    current_user: User = Depends(require_role("system_admin", "supervisor")),
    security_service: SecurityService = Depends(get_security_service),
) -> SecurityEventResponse:
    """Retrieves safe structured details for a specific security event."""
    event = await security_service.get_event_by_id(event_id)
    return SecurityEventResponse.model_validate(event)


@security_router.post(
    "/events/{event_id}/resolve",
    response_model=SecurityEventResponse,
    status_code=status.HTTP_200_OK,
)
async def resolve_security_event(
    event_id: UUID,
    current_user: User = Depends(require_role("system_admin")),
    security_service: SecurityService = Depends(get_security_service),
) -> SecurityEventResponse:
    """Marks a security incident as resolved."""
    event = await security_service.resolve_event(event_id, current_user)
    return SecurityEventResponse.model_validate(event)


@security_router.post(
    "/simulate-tamper",
    response_model=TamperSimulationResponse,
    status_code=status.HTTP_200_OK,
)
async def simulate_tamper_for_demo(
    request: Request,
    payload: TamperSimulationRequest,
    current_user: User = Depends(get_current_user),
    security_service: SecurityService = Depends(get_security_service),
) -> TamperSimulationResponse:
    """
    Controlled tamper simulation endpoint for SIH evaluation demonstration.
    Modifies MinIO payload bytes with a test corruption marker without altering
    the authoritative database SHA-256 hash. Live download/verification checks
    will immediately catch the mismatch, refuse access, and alert.
    """
    client_ip = request.client.host if request.client else None
    result = await security_service.simulate_tamper(
        target_type=payload.target_type,
        target_id=payload.target_id,
        current_user=current_user,
        client_ip=client_ip,
    )
    return TamperSimulationResponse(**result)

