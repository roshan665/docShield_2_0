"""
Case & Case Membership Database Repository
Encapsulates database queries for cases and case membership.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import User
from app.models.case import Case, CaseMember


class CaseRepository:
    """Repository handling Case persistence and membership scoping."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, case: Case) -> Case:
        """Persists a new Case record."""
        self.session.add(case)
        await self.session.flush()
        return case

    async def get_by_id(self, case_id: UUID) -> Case | None:
        """Loads a case by ID with relationships eager-loaded."""
        query = (
            select(Case)
            .options(
                selectinload(Case.members).selectinload(CaseMember.user),
                selectinload(Case.creator),
                selectinload(Case.investigating_officer),
            )
            .where(Case.id == case_id)
        )
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def get_by_case_number(self, case_number: str) -> Case | None:
        """Looks up a case by unique case_number."""
        query = select(Case).where(Case.case_number == case_number)
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def update(self, case: Case) -> Case:
        """Updates case entity."""
        case.updated_at = datetime.now(UTC)
        await self.session.flush()
        return case

    async def list_cases_for_user(
        self,
        user_id: UUID,
        status: str | None = None,
        priority: str | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[tuple[Case, str]], int]:
        """
        Lists cases strictly filtered by the user's active membership in case_members.
        Returns tuples of (Case, user_role_in_case) and the total count.
        """
        base_query = (
            select(Case, CaseMember.role_in_case)
            .join(CaseMember, (CaseMember.case_id == Case.id) & (CaseMember.user_id == user_id) & (CaseMember.is_active == True))  # noqa: E712
            .options(
                selectinload(Case.creator),
                selectinload(Case.investigating_officer),
                selectinload(Case.members),
            )
        )

        if status:
            base_query = base_query.where(Case.status == status)
        if priority:
            base_query = base_query.where(Case.priority == priority)
        if search:
            search_pattern = f"%{search.strip()}%"
            base_query = base_query.where(
                or_(
                    Case.title.ilike(search_pattern),
                    Case.case_number.ilike(search_pattern),
                    Case.fir_number.ilike(search_pattern),
                    Case.police_station.ilike(search_pattern),
                )
            )

        # Count total matching records for the user
        subq = base_query.order_by(None).subquery()
        count_subquery = select(func.count()).select_from(subq)
        count_res = await self.session.execute(count_subquery)
        total = count_res.scalar() or 0

        # Execute paginated query
        paged_query = base_query.order_by(Case.created_at.desc()).offset(skip).limit(limit)
        res = await self.session.execute(paged_query)
        items = res.all()
        # Each item is a Row containing (Case, role_in_case)
        return [(row[0], row[1]) for row in items], total

    async def check_membership(self, case_id: UUID, user_id: UUID) -> CaseMember | None:
        """Checks if a user is an active member of a case."""
        query = select(CaseMember).where(
            (CaseMember.case_id == case_id)
            & (CaseMember.user_id == user_id)
            & (CaseMember.is_active == True)  # noqa: E712
        )
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def get_membership_record(self, case_id: UUID, user_id: UUID) -> CaseMember | None:
        """Retrieves membership record regardless of active status (for reactivation)."""
        query = select(CaseMember).where(
            (CaseMember.case_id == case_id) & (CaseMember.user_id == user_id)
        )
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def add_member(
        self,
        case_id: UUID,
        user_id: UUID,
        role_in_case: str,
        added_by: UUID | None,
    ) -> CaseMember:
        """Enrolls an officer in a case or reactivates an existing membership."""
        now = datetime.now(UTC)
        existing = await self.get_membership_record(case_id, user_id)
        if existing:
            existing.role_in_case = role_in_case
            existing.is_active = True
            existing.removed_at = None
            existing.added_by = added_by
            existing.added_at = now
            existing.updated_at = now
            await self.session.flush()
            return existing

        member = CaseMember(
            case_id=case_id,
            user_id=user_id,
            role_in_case=role_in_case,
            added_by=added_by,
            added_at=now,
            is_active=True,
        )
        self.session.add(member)
        await self.session.flush()
        return member

    async def remove_member(self, case_id: UUID, user_id: UUID) -> CaseMember | None:
        """Soft-removes an officer from a case."""
        member = await self.check_membership(case_id, user_id)
        if not member:
            return None

        member.is_active = False
        member.removed_at = datetime.now(UTC)
        member.updated_at = datetime.now(UTC)
        await self.session.flush()
        return member

    async def list_members(self, case_id: UUID) -> list[CaseMember]:
        """Lists all active case members with user information."""
        query = (
            select(CaseMember)
            .options(selectinload(CaseMember.user).selectinload(User.role))
            .where((CaseMember.case_id == case_id) & (CaseMember.is_active == True))  # noqa: E712
            .order_by(CaseMember.added_at.asc())
        )
        res = await self.session.execute(query)
        return list(res.scalars().all())
