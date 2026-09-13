"""
Evidence Management Dependency Injections
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.documents.dependencies import get_storage_service
from app.modules.evidence.service import EvidenceService
from app.storage.service import StorageService


async def get_evidence_service(
    session: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> EvidenceService:
    """Provides EvidenceService instance bound to request session."""
    return EvidenceService(session=session, storage=storage)

