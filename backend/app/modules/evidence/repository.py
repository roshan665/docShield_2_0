"""
Evidence & Chain of Custody Repository Layer
Handles transactional queries, row-level locking, and PostgreSQL persistence.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.custody import EvidenceCustodyEvent
from app.models.evidence import Evidence


class EvidenceRepository:
    """Repository handling database operations for evidence records and custody ledger."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_evidence_number(self) -> str:
        """Generates sequential official evidence identifier: EVID-YYYY-XXXXX."""
        year = datetime.now(UTC).year
        prefix = f"EVID-{year}-"

        query = select(func.count(Evidence.id)).where(Evidence.evidence_number.like(f"{prefix}%"))
        res = await self.session.execute(query)
        count = res.scalar_one() or 0
        return f"{prefix}{count + 1:05d}"

    async def get_by_id(self, evidence_id: UUID) -> Evidence | None:
        """Retrieves evidence record by UUID with relationships loaded."""
        stmt = (
            select(Evidence)
            .where(Evidence.id == evidence_id)
            .options(
                selectinload(Evidence.current_custodian),
                selectinload(Evidence.pending_custodian),
                selectinload(Evidence.registered_by),
                selectinload(Evidence.document),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_id_for_update(self, evidence_id: UUID) -> Evidence | None:
        """
        Retrieves evidence record with PostgreSQL pessimistic row-level lock (FOR UPDATE).
        Essential for serializing custody transfers and preventing concurrent race conditions.
        """
        stmt = (
            select(Evidence)
            .where(Evidence.id == evidence_id)
            .with_for_update()
            .options(
                selectinload(Evidence.current_custodian),
                selectinload(Evidence.pending_custodian),
                selectinload(Evidence.registered_by),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_by_case(
        self,
        case_id: UUID,
        evidence_type: str | None = None,
        status: str | None = None,
        custodian_id: UUID | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Evidence]:
        """Lists evidence belonging to a specific case with optional filters."""
        stmt = (
            select(Evidence)
            .where(Evidence.case_id == case_id)
            .options(
                selectinload(Evidence.current_custodian),
                selectinload(Evidence.pending_custodian),
                selectinload(Evidence.registered_by),
            )
            .order_by(desc(Evidence.created_at))
        )

        if evidence_type:
            stmt = stmt.where(Evidence.evidence_type == evidence_type)
        if status:
            stmt = stmt.where(Evidence.status == status)
        if custodian_id:
            stmt = stmt.where(Evidence.current_custodian_id == custodian_id)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Evidence.title.ilike(pattern),
                    Evidence.evidence_number.ilike(pattern),
                    Evidence.description.ilike(pattern),
                )
            )

        stmt = stmt.offset(skip).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def list_accessible_evidence(
        self,
        allowed_case_ids: list[UUID],
        evidence_type: str | None = None,
        status: str | None = None,
        custodian_id: UUID | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Evidence]:
        """Lists evidence records across assigned cases with server-side authorization enforcement."""
        if not allowed_case_ids:
            return []

        stmt = (
            select(Evidence)
            .where(Evidence.case_id.in_(allowed_case_ids))
            .options(
                selectinload(Evidence.current_custodian),
                selectinload(Evidence.pending_custodian),
                selectinload(Evidence.registered_by),
            )
            .order_by(desc(Evidence.created_at))
        )

        if evidence_type:
            stmt = stmt.where(Evidence.evidence_type == evidence_type)
        if status:
            stmt = stmt.where(Evidence.status == status)
        if custodian_id:
            stmt = stmt.where(Evidence.current_custodian_id == custodian_id)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Evidence.title.ilike(pattern),
                    Evidence.evidence_number.ilike(pattern),
                    Evidence.description.ilike(pattern),
                )
            )

        stmt = stmt.offset(skip).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_evidence(self, evidence: Evidence) -> Evidence:
        """Persists new evidence entity."""
        self.session.add(evidence)
        await self.session.flush()
        return evidence

    async def create_custody_event(self, event: EvidenceCustodyEvent) -> EvidenceCustodyEvent:
        """Persists immutable custody ledger event."""
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_latest_custody_event(self, evidence_id: UUID) -> EvidenceCustodyEvent | None:
        """Retrieves the latest recorded custody event for an evidence item."""
        stmt = (
            select(EvidenceCustodyEvent)
            .where(EvidenceCustodyEvent.evidence_id == evidence_id)
            .order_by(desc(EvidenceCustodyEvent.created_at))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_custody_events(self, evidence_id: UUID) -> list[EvidenceCustodyEvent]:
        """Retrieves complete chronological custody history (ascending order for verification)."""
        stmt = (
            select(EvidenceCustodyEvent)
            .where(EvidenceCustodyEvent.evidence_id == evidence_id)
            .options(
                selectinload(EvidenceCustodyEvent.from_user),
                selectinload(EvidenceCustodyEvent.to_user),
            )
            .order_by(EvidenceCustodyEvent.created_at.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def count_custody_events(self, evidence_id: UUID) -> int:
        """Counts total custody events recorded for an evidence record."""
        stmt = select(func.count(EvidenceCustodyEvent.id)).where(EvidenceCustodyEvent.evidence_id == evidence_id)
        res = await self.session.execute(stmt)
        return res.scalar_one() or 0

