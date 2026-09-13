"""
Case Management Dependency Injections
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.audit.service import AuditService
from app.modules.cases.service import CaseService


async def get_case_service(session: AsyncSession = Depends(get_db)) -> CaseService:
    """Provides CaseService instance bound to request session."""
    return CaseService(session)


async def get_audit_service(session: AsyncSession = Depends(get_db)) -> AuditService:
    """Provides AuditService instance bound to request session."""
    return AuditService(session)

