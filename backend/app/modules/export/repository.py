"""
Repository for Case Export Data Access
Conforms to Router -> Service -> Repository -> Model pattern.
"""

from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.export import CaseExport


class ExportRepository:
    """Data access repository for legal court exports."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_export(self, export: CaseExport) -> CaseExport:
        """Persists a new case export record."""
        self.session.add(export)
        await self.session.flush()
        return export

    async def get_export_by_id(self, export_id: UUID) -> CaseExport | None:
        """Retrieves an export record by ID with case relationship loaded."""
        stmt = (
            select(CaseExport)
            .options(selectinload(CaseExport.case))
            .where(CaseExport.id == export_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_exports_for_case(
        self,
        case_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[CaseExport], int]:
        """Lists export records for a case ordered chronologically descending."""
        count_stmt = (
            select(func.count(CaseExport.id))
            .where(CaseExport.case_id == case_id)
        )
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one() or 0

        stmt = (
            select(CaseExport)
            .options(selectinload(CaseExport.case))
            .where(CaseExport.case_id == case_id)
            .order_by(desc(CaseExport.created_at))
            .offset(skip)
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all()), total

    async def update_export(self, export: CaseExport) -> CaseExport:
        """Updates an existing case export record."""
        await self.session.flush()
        return export

