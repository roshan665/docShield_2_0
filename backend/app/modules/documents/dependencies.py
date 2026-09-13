"""
Document Management Dependency Injections
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.documents.service import DocumentService
from app.storage.s3 import S3StorageService
from app.storage.service import StorageService

_shared_storage: StorageService | None = None


def get_storage_service() -> StorageService:
    """Returns singleton S3StorageService instance."""
    global _shared_storage
    if _shared_storage is None:
        _shared_storage = S3StorageService()
    return _shared_storage


async def get_document_service(
    session: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> DocumentService:
    """Provides DocumentService instance bound to request session."""
    return DocumentService(session=session, storage=storage)
