"""
AI Module FastAPI Dependencies
Provides dependency injection providers for AIService, SemanticSearchService, and RAGService.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.ai.rag_service import RAGService
from app.modules.ai.semantic_search import SemanticSearchService
from app.modules.ai.service import AIService
from app.storage.s3 import S3StorageService
from app.storage.service import StorageService


def get_storage_service() -> StorageService:
    """Dependency provider for S3/MinIO storage service."""
    return S3StorageService()


def get_ai_service(
    session: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> AIService:
    """Dependency provider for AI document intelligence pipeline service."""
    return AIService(session=session, storage=storage)


def get_semantic_search_service(
    session: AsyncSession = Depends(get_db),
) -> SemanticSearchService:
    """Dependency provider for case-scoped semantic search service."""
    return SemanticSearchService(session=session)


def get_rag_service(
    session: AsyncSession = Depends(get_db),
) -> RAGService:
    """Dependency provider for Case AI Assistant RAG service."""
    return RAGService(session=session)

