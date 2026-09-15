"""
Case Management Business Logic Service
Orchestrates case lifecycle state machine, membership authorization, and audit trail emission.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    ConflictException,
    EntityNotFoundException,
    PermissionDeniedException,
    ValidationException,
)
from app.models.auth import User
from app.models.case import Case
from app.modules.audit.service import AuditService
from app.modules.auth.repository import UserRepository
from app.modules.cases.repository import CaseRepository
from app.schemas.audit import CaseTimelineEventResponse
from app.schemas.case import (
    CaseCreateRequest,
    CaseMemberAddRequest,
    CaseMemberResponse,
    CaseResponse,
    CaseUpdateRequest,
)

# Valid status transitions mapping: from_state -> set of valid to_states
VALID_STATE_TRANSITIONS: dict[str, set[str]] = {
    "open": {"under_investigation", "archived"},
    "under_investigation": {"pending_review", "archived"},
    "pending_review": {"under_investigation", "pending_legal", "archived"},
    "pending_legal": {"closed", "under_investigation", "archived"},
    "closed": {"archived", "under_investigation"},  # Re-opening allowed with audit
    "archived": set(),
}


class CaseService:
    """Business service governing Case operations and membership governance."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.case_repo = CaseRepository(session)
        self.user_repo = UserRepository(session)
        self.audit_service = AuditService(session)

    async def create_case(
        self,
        data: CaseCreateRequest,
        creator: User,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> CaseResponse:
        """
        Registers a new Case and automatically enrolls the creator as lead investigator.
        Emits an append-only audit event.
        """
        # 1. Uniqueness check
        existing = await self.case_repo.get_by_case_number(data.case_number)
        if existing:
            raise ConflictException(
                detail=f"Case number '{data.case_number}' already exists",
                error_code="CASE_002",
            )

        # 2. Create Case entity
        case = Case(
            case_number=data.case_number,
            fir_number=data.fir_number,
            title=data.title,
            description=data.description,
            priority=data.priority,
            category=data.category,
            police_station=data.police_station,
            district=data.district,
            state=data.state,
            status="open",
            investigating_officer_id=creator.id,
            created_by=creator.id,
        )
        case = await self.case_repo.create(case)

        # 3. Creator auto-enrolled as active lead_investigator
        member = await self.case_repo.add_member(
            case_id=case.id,
            user_id=creator.id,
            role_in_case="lead_investigator",
            added_by=creator.id,
        )

        # 4. Record tamper-evident Audit Event
        await self.audit_service.record_event(
            action="CASE_CREATED",
            resource_type="case",
            resource_id=case.id,
            case_id=case.id,
            actor_id=creator.id,
            details={
                "case_number": case.case_number,
                "fir_number": case.fir_number,
                "title": case.title,
                "priority": case.priority,
            },
            result="success",
            ip_address=client_ip,
            user_agent=user_agent,
        )

        return self._build_case_response(case, user_role_in_case=member.role_in_case)

    async def get_case(
        self,
        case_id: UUID,
        current_user: User,
        client_ip: str | None = None,
    ) -> CaseResponse:
        """
        Retrieves case details after verifying explicit active membership or Admin role.
        Non-members receive 404 to avoid leaking existence (IDOR protection).
        """
        is_admin = bool(current_user.role and current_user.role.name in ("system_admin", "admin"))
        membership = await self.case_repo.check_membership(case_id, current_user.id)
        if not membership and not is_admin:
            raise EntityNotFoundException(detail="Case not found", error_code="CASE_001")

        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise EntityNotFoundException(detail="Case not found", error_code="CASE_001")

        role_in_case = membership.role_in_case if membership else "admin"
        return self._build_case_response(case, user_role_in_case=role_in_case)

    async def list_cases(
        self,
        current_user: User,
        status: str | None = None,
        priority: str | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[CaseResponse], int]:
        """
        Lists cases. Admins can view all cases across the system;
        Officers/Advocates only see cases where they are an active member.
        """
        is_admin = bool(current_user.role and current_user.role.name in ("system_admin", "admin"))
        if is_admin:
            items, total = await self.case_repo.list_all_cases(
                status=status,
                priority=priority,
                search=search,
                skip=skip,
                limit=limit,
            )
        else:
            items, total = await self.case_repo.list_cases_for_user(
                user_id=current_user.id,
                status=status,
                priority=priority,
                search=search,
                skip=skip,
                limit=limit,
            )
        responses = [self._build_case_response(case, role) for case, role in items]
        return responses, total

    async def update_case(
        self,
        case_id: UUID,
        data: CaseUpdateRequest,
        current_user: User,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> CaseResponse:
        """
        Updates case details or status. Verifies user is an active member
        with lead_investigator or supervisor role, and validates state machine transitions.
        """
        is_admin = bool(current_user.role and current_user.role.name in ("system_admin", "admin"))
        membership = await self.case_repo.check_membership(case_id, current_user.id)
        if not membership and not is_admin:
            raise EntityNotFoundException(detail="Case not found", error_code="CASE_001")

        if not is_admin and (not membership or membership.role_in_case not in ("lead_investigator", "supervisor")) and current_user.role.name not in ("supervisor", "system_admin"):
            raise PermissionDeniedException(
                detail="Only lead investigator or supervisor may update case details",
                error_code="AUTHZ_001",
            )

        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise EntityNotFoundException(detail="Case not found", error_code="CASE_001")

        changes: dict[str, dict[str, str | None]] = {}

        # Validate status change if requested
        if data.status and data.status != case.status:
            allowed_next = VALID_STATE_TRANSITIONS.get(case.status, set())
            if data.status not in allowed_next:
                raise ValidationException(
                    detail=f"Invalid state transition from '{case.status}' to '{data.status}'",
                    error_code="CASE_003",
                )
            changes["status"] = {"from": case.status, "to": data.status}
            case.status = data.status
            if data.status == "closed":
                case.closed_at = datetime.now(UTC)

        if data.title is not None and data.title != case.title:
            changes["title"] = {"from": case.title, "to": data.title}
            case.title = data.title

        if data.description is not None and data.description != case.description:
            case.description = data.description

        if data.priority is not None and data.priority != case.priority:
            changes["priority"] = {"from": case.priority, "to": data.priority}
            case.priority = data.priority

        if data.category is not None:
            case.category = data.category
        if data.police_station is not None:
            case.police_station = data.police_station
        if data.district is not None:
            case.district = data.district
        if data.state is not None:
            case.state = data.state

        case = await self.case_repo.update(case)

        # Audit event
        action = "CASE_STATUS_CHANGED" if "status" in changes else "CASE_UPDATED"
        await self.audit_service.record_event(
            action=action,
            resource_type="case",
            resource_id=case.id,
            case_id=case.id,
            actor_id=current_user.id,
            details={"changes": changes},
            result="success",
            ip_address=client_ip,
            user_agent=user_agent,
        )

        role_in_case = membership.role_in_case if membership else "admin"
        return self._build_case_response(case, user_role_in_case=role_in_case)

    async def delete_case(
        self,
        case_id: UUID,
        current_user: User,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """
        Soft-archives a case in accordance with evidence preservation requirements.
        """
        is_admin = bool(current_user.role and current_user.role.name in ("system_admin", "admin"))
        membership = await self.case_repo.check_membership(case_id, current_user.id)
        if not membership and not is_admin:
            raise EntityNotFoundException(detail="Case not found", error_code="CASE_001")

        if not is_admin and (not membership or membership.role_in_case not in ("lead_investigator", "supervisor")) and current_user.role.name not in ("supervisor", "system_admin"):
            raise PermissionDeniedException(
                detail="Only lead investigator or supervisor may archive a case",
                error_code="AUTHZ_001",
            )

        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise EntityNotFoundException(detail="Case not found", error_code="CASE_001")

        case.status = "archived"
        case.closed_at = datetime.now(UTC)
        await self.case_repo.update(case)

        await self.audit_service.record_event(
            action="CASE_ARCHIVED",
            resource_type="case",
            resource_id=case.id,
            case_id=case.id,
            actor_id=current_user.id,
            details={"action": "Case archived / closed by authorized officer"},
            result="success",
            ip_address=client_ip,
            user_agent=user_agent,
        )

    # -------------------------------------------------------------------------
    # Case Membership Management
    # -------------------------------------------------------------------------

    async def add_member(
        self,
        case_id: UUID,
        data: CaseMemberAddRequest,
        current_user: User,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> CaseMemberResponse:
        """
        Adds an officer to the case team.
        Prevents duplicate active memberships and rejects deactivated users.
        """
        is_admin = bool(current_user.role and current_user.role.name in ("system_admin", "admin"))
        membership = await self.case_repo.check_membership(case_id, current_user.id)
        if not membership and not is_admin:
            raise EntityNotFoundException(detail="Case not found", error_code="CASE_001")

        if not is_admin and (not membership or membership.role_in_case not in ("lead_investigator", "supervisor")) and current_user.role.name not in ("supervisor", "system_admin"):
            raise PermissionDeniedException(
                detail="Only lead investigator or supervisor may manage case team members",
                error_code="AUTHZ_001",
            )

        target_user = await self.user_repo.get_by_id(data.user_id)
        if not target_user:
            raise EntityNotFoundException(detail="Target user not found")

        if not target_user.is_active or target_user.is_locked:
            raise ValidationException(
                detail="Cannot assign inactive or locked officer to case team",
                error_code="VAL_001",
            )

        # Check existing active membership
        existing = await self.case_repo.check_membership(case_id, data.user_id)
        if existing:
            raise ConflictException(
                detail=f"Officer '{target_user.full_name}' is already an active member of this case",
            )

        member = await self.case_repo.add_member(
            case_id=case_id,
            user_id=data.user_id,
            role_in_case=data.role_in_case,
            added_by=current_user.id,
        )

        await self.audit_service.record_event(
            action="CASE_MEMBER_ADDED",
            resource_type="case_member",
            resource_id=member.id,
            case_id=case_id,
            actor_id=current_user.id,
            details={
                "assigned_officer_id": str(target_user.id),
                "officer_email": target_user.email,
                "role_in_case": data.role_in_case,
            },
            result="success",
            ip_address=client_ip,
            user_agent=user_agent,
        )

        return CaseMemberResponse(
            id=member.id,
            case_id=member.case_id,
            user_id=member.user_id,
            role_in_case=member.role_in_case,
            added_by=member.added_by,
            added_at=member.added_at,
            is_active=member.is_active,
            user_full_name=target_user.full_name,
            user_email=target_user.email,
            user_employee_id=target_user.employee_id,
            user_role=target_user.role.name,
        )

    async def remove_member(
        self,
        case_id: UUID,
        target_user_id: UUID,
        current_user: User,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """
        Soft-removes an officer from a case. Prevents removal of the last lead investigator.
        """
        is_admin = bool(current_user.role and current_user.role.name in ("system_admin", "admin"))
        membership = await self.case_repo.check_membership(case_id, current_user.id)
        if not membership and not is_admin:
            raise EntityNotFoundException(detail="Case not found", error_code="CASE_001")

        if not is_admin and (not membership or membership.role_in_case not in ("lead_investigator", "supervisor")) and current_user.role.name not in ("supervisor", "system_admin"):
            raise PermissionDeniedException(
                detail="Only lead investigator or supervisor may remove case team members",
                error_code="AUTHZ_001",
            )

        target_member = await self.case_repo.check_membership(case_id, target_user_id)
        if not target_member:
            raise EntityNotFoundException(detail="Case member not found")

        # Ensure we do not remove the sole lead investigator
        if target_member.role_in_case == "lead_investigator":
            all_members = await self.case_repo.list_members(case_id)
            leads = [m for m in all_members if m.role_in_case == "lead_investigator"]
            if len(leads) <= 1:
                raise ValidationException(
                    detail="Cannot remove the sole Lead Investigator from the case",
                )

        removed = await self.case_repo.remove_member(case_id, target_user_id)
        if removed:
            await self.audit_service.record_event(
                action="CASE_MEMBER_REMOVED",
                resource_type="case_member",
                resource_id=removed.id,
                case_id=case_id,
                actor_id=current_user.id,
                details={
                    "removed_user_id": str(target_user_id),
                    "former_role_in_case": target_member.role_in_case,
                },
                result="success",
                ip_address=client_ip,
                user_agent=user_agent,
            )

    async def list_members(self, case_id: UUID, current_user: User) -> list[CaseMemberResponse]:
        """Lists active case members. User must be an active member of the case or an Admin."""
        is_admin = bool(current_user.role and current_user.role.name in ("system_admin", "admin"))
        membership = await self.case_repo.check_membership(case_id, current_user.id)
        if not membership and not is_admin:
            raise EntityNotFoundException(detail="Case not found", error_code="CASE_001")

        members = await self.case_repo.list_members(case_id)
        return [
            CaseMemberResponse(
                id=m.id,
                case_id=m.case_id,
                user_id=m.user_id,
                role_in_case=m.role_in_case,
                added_by=m.added_by,
                added_at=m.added_at,
                is_active=m.is_active,
                user_full_name=m.user.full_name if m.user else None,
                user_email=m.user.email if m.user else None,
                user_employee_id=m.user.employee_id if m.user else None,
                user_role=m.user.role.name if m.user and m.user.role else None,
            )
            for m in members
        ]

    async def get_case_timeline(
        self,
        case_id: UUID,
        current_user: User,
    ) -> list[CaseTimelineEventResponse]:
        """
        Retrieves the chronological audit timeline for a case.
        User must be an active member of the case or an Admin.
        """
        is_admin = bool(current_user.role and current_user.role.name in ("system_admin", "admin"))
        membership = await self.case_repo.check_membership(case_id, current_user.id)
        if not membership and not is_admin:
            raise EntityNotFoundException(detail="Case not found", error_code="CASE_001")

        events, _ = await self.audit_service.list_events(case_id=case_id, limit=100)

        timeline: list[CaseTimelineEventResponse] = []
        for ev in events:
            # Human-readable event description
            desc = f"{ev.action.replace('_', ' ').title()}"
            if ev.action == "CASE_CREATED":
                desc = "Case registered and initiated"
            elif ev.action == "CASE_STATUS_CHANGED":
                new_st = ev.details.get("changes", {}).get("status", {}).get("to") if ev.details else None
                desc = f"Case status updated to {new_st}" if new_st else "Case status updated"
            elif ev.action == "CASE_MEMBER_ADDED":
                role = ev.details.get("role_in_case") if ev.details else "member"
                desc = f"Officer assigned to case as {role.replace('_', ' ').title()}"
            elif ev.action == "CASE_MEMBER_REMOVED":
                desc = "Officer removed from case team"
            elif ev.action == "CASE_ARCHIVED":
                desc = "Case closed and archived"

            timeline.append(
                CaseTimelineEventResponse(
                    id=ev.id,
                    timestamp=ev.timestamp,
                    action=ev.action,
                    actor_name=ev.actor.full_name if ev.actor else "System",
                    actor_email=ev.actor.email if ev.actor else None,
                    description=desc,
                    details=ev.details,
                    result=ev.result,
                )
            )

        return timeline

    def _build_case_response(
        self,
        case: Case,
        user_role_in_case: str | None = None,
        members_count: int | None = None,
    ) -> CaseResponse:
        """Constructs CaseResponse DTO from ORM Case entity without triggering unawaited lazy loads."""
        d = case.__dict__
        inv_name = None
        if "investigating_officer" in d and case.investigating_officer:
            inv_name = case.investigating_officer.full_name

        creator_name = None
        if "creator" in d and case.creator:
            creator_name = case.creator.full_name

        if members_count is not None:
            m_count = members_count
        elif "members" in d and case.members is not None:
            m_count = len(case.members)
        else:
            m_count = 1

        return CaseResponse(
            id=case.id,
            case_number=case.case_number,
            fir_number=case.fir_number,
            title=case.title,
            description=case.description,
            status=case.status,
            priority=case.priority,
            category=case.category,
            police_station=case.police_station,
            district=case.district,
            state=case.state,
            investigating_officer_id=case.investigating_officer_id,
            investigating_officer_name=inv_name,
            created_by=case.created_by,
            created_by_name=creator_name,
            closed_at=case.closed_at,
            created_at=case.created_at,
            updated_at=case.updated_at,
            members_count=m_count,
            user_role_in_case=user_role_in_case,
        )

    async def list_assignable_officers(self) -> list[User]:
        """Lists active personnel available for case assignment."""
        query = (
            select(User)
            .options(selectinload(User.role))
            .where(User.is_active == True, User.is_locked == False)  # noqa: E712
            .order_by(User.full_name)
        )
        res = await self.session.execute(query)
        return list(res.scalars().all())

