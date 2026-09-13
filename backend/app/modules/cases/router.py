"""
Case Management REST API Router (/api/v1/cases)
Enforces authentication, RBAC permission checks, and explicit membership access scoping.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from app.models.auth import User
from app.modules.auth.dependencies import get_current_user, require_permission
from app.modules.cases.dependencies import get_case_service
from app.modules.cases.service import CaseService
from app.schemas.audit import CaseTimelineEventResponse
from app.schemas.auth import UserResponse
from app.schemas.case import (
    CaseCreateRequest,
    CaseMemberAddRequest,
    CaseMemberResponse,
    CaseResponse,
    CaseUpdateRequest,
)

router = APIRouter(prefix="/cases", tags=["Case Management"])


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    request: Request,
    data: CaseCreateRequest,
    current_user: User = Depends(require_permission("cases", "create")),
    case_service: CaseService = Depends(get_case_service),
) -> CaseResponse:
    """
    Creates a new case and auto-enrolls the creator as Lead Investigator.
    Required permission: cases:create (Investigators, Supervisors).
    """
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await case_service.create_case(
        data=data,
        creator=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@router.get("", response_model=list[CaseResponse])
async def list_cases(
    status: str | None = Query(None),
    priority: str | None = Query(None),
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_permission("cases", "read")),
    case_service: CaseService = Depends(get_case_service),
) -> list[CaseResponse]:
    """
    Lists only cases where the authenticated user is an active member in case_members.
    Zero cross-case leakage. Required permission: cases:read.
    """
    cases, _ = await case_service.list_cases(
        current_user=current_user,
        status=status,
        priority=priority,
        search=search,
        skip=skip,
        limit=limit,
    )
    return cases


@router.get("/assignable-officers", response_model=list[UserResponse])
async def list_assignable_officers(
    current_user: User = Depends(get_current_user),
    case_service: CaseService = Depends(get_case_service),
) -> list[UserResponse]:
    """
    Lists active system personnel available for case assignment.
    Accessible to authenticated officers.
    """
    users = await case_service.list_assignable_officers()
    return [
        UserResponse(
            id=u.id,
            employee_id=u.employee_id,
            email=u.email,
            full_name=u.full_name,
            role=u.role.name,
            role_display_name=u.role.display_name,
            department=u.department,
            designation=u.designation,
            is_active=u.is_active,
            is_locked=u.is_locked,
            last_login=u.last_login,
            created_at=u.created_at,
            permissions=[],
        )
        for u in users
    ]


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    request: Request,
    case_id: UUID,
    current_user: User = Depends(require_permission("cases", "read")),
    case_service: CaseService = Depends(get_case_service),
) -> CaseResponse:
    """
    Fetches case details. User must be an active member of this case.
    Returns 404 if not found or unauthorized (preventing IDOR enumeration).
    """
    client_ip = request.client.host if request.client else None
    return await case_service.get_case(
        case_id=case_id,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    request: Request,
    case_id: UUID,
    data: CaseUpdateRequest,
    current_user: User = Depends(require_permission("cases", "update")),
    case_service: CaseService = Depends(get_case_service),
) -> CaseResponse:
    """
    Updates case details or advances status lifecycle (with state machine validation).
    User must be lead_investigator or supervisor on the case.
    """
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await case_service.update_case(
        case_id=case_id,
        data=data,
        current_user=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@router.delete("/{case_id}", status_code=status.HTTP_200_OK)
async def delete_case(
    request: Request,
    case_id: UUID,
    current_user: User = Depends(require_permission("cases", "delete")),
    case_service: CaseService = Depends(get_case_service),
) -> dict:
    """
    Soft-archives a case. Required permission: cases:delete (Supervisor).
    """
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await case_service.delete_case(
        case_id=case_id,
        current_user=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )
    return {"message": "Case archived successfully"}


# -----------------------------------------------------------------------------
# Case Team Membership Endpoints
# -----------------------------------------------------------------------------

@router.get("/{case_id}/members", response_model=list[CaseMemberResponse])
async def list_case_members(
    case_id: UUID,
    current_user: User = Depends(require_permission("cases", "read")),
    case_service: CaseService = Depends(get_case_service),
) -> list[CaseMemberResponse]:
    """
    Lists active case team members. User must be an active member of this case.
    """
    return await case_service.list_members(case_id=case_id, current_user=current_user)


@router.post("/{case_id}/members", response_model=CaseMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_case_member(
    request: Request,
    case_id: UUID,
    data: CaseMemberAddRequest,
    current_user: User = Depends(require_permission("cases", "add_members")),
    case_service: CaseService = Depends(get_case_service),
) -> CaseMemberResponse:
    """
    Assigns an officer to the case team.
    Only Lead Investigator or Supervisor may add members.
    Prevents duplicate active members and rejects deactivated users.
    """
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await case_service.add_member(
        case_id=case_id,
        data=data,
        current_user=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@router.delete("/{case_id}/members/{user_id}", status_code=status.HTTP_200_OK)
async def remove_case_member(
    request: Request,
    case_id: UUID,
    user_id: UUID,
    current_user: User = Depends(require_permission("cases", "add_members")),
    case_service: CaseService = Depends(get_case_service),
) -> dict:
    """
    Soft-removes an officer from the case team.
    Only Lead Investigator or Supervisor may remove members.
    """
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await case_service.remove_member(
        case_id=case_id,
        target_user_id=user_id,
        current_user=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )
    return {"message": "Case member removed successfully"}


# -----------------------------------------------------------------------------
# Case Timeline
# -----------------------------------------------------------------------------

@router.get("/{case_id}/timeline", response_model=list[CaseTimelineEventResponse])
async def get_case_timeline(
    case_id: UUID,
    current_user: User = Depends(require_permission("cases", "read")),
    case_service: CaseService = Depends(get_case_service),
) -> list[CaseTimelineEventResponse]:
    """
    Retrieves the chronological activity timeline for a case from its audit events.
    User must be an active member of this case.
    """
    return await case_service.get_case_timeline(case_id=case_id, current_user=current_user)
