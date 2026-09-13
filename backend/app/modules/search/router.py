"""
Search & RAG REST API Endpoints (/api/v1/search)
Provides production-grade, authorization-aware search and RAG endpoints:
- POST /api/v1/search/semantic
- POST /api/v1/search/keyword
- POST /api/v1/search/hybrid
- POST /api/v1/search/ask
- GET  /api/v1/search/status
"""

import logging

from fastapi import APIRouter, Depends, status

from app.core.rate_limit import rate_limit_rag, rate_limit_search
from app.models.auth import User
from app.modules.ai.dependencies import (
    get_rag_service,
    get_semantic_search_service,
)
from app.modules.ai.rag_service import RAGService
from app.modules.ai.semantic_search import SemanticSearchService
from app.modules.auth.dependencies import require_permission
from app.schemas.search import (
    SearchAskRequest,
    SearchAskResponse,
    SearchHybridRequest,
    SearchKeywordRequest,
    SearchResponse,
    SearchSemanticRequest,
    SearchStatusResponse,
)

logger = logging.getLogger(__name__)

search_router = APIRouter(prefix="/search", tags=["Search & RAG Intelligence"])


@search_router.post(
    "/semantic",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_search)],
)
async def search_semantic(
    request: SearchSemanticRequest,
    current_user: User = Depends(require_permission("documents", "read")),
    search_service: SemanticSearchService = Depends(get_semantic_search_service),
) -> SearchResponse:
    """
    Executes dense vector cosine similarity search in pgvector.
    Enforces strict case membership pre-authorization in SQL.
    Rate-limited to 30 requests/minute.
    """
    return await search_service.search_semantic(user=current_user, request=request)


@search_router.post(
    "/keyword",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_search)],
)
async def search_keyword(
    request: SearchKeywordRequest,
    current_user: User = Depends(require_permission("documents", "read")),
    search_service: SemanticSearchService = Depends(get_semantic_search_service),
) -> SearchResponse:
    """
    Executes keyword and metadata search in PostgreSQL.
    Enforces strict case membership pre-authorization in SQL.
    Rate-limited to 30 requests/minute.
    """
    return await search_service.search_keyword(user=current_user, request=request)


@search_router.post(
    "/hybrid",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_search)],
)
async def search_hybrid(
    request: SearchHybridRequest,
    current_user: User = Depends(require_permission("documents", "read")),
    search_service: SemanticSearchService = Depends(get_semantic_search_service),
) -> SearchResponse:
    """
    Executes Reciprocal Rank Fusion (RRF) Hybrid Search.
    Combines dense pgvector semantic cosine similarity and sparse keyword search.
    Rate-limited to 30 requests/minute.
    """
    return await search_service.search_hybrid(user=current_user, request=request)


@search_router.post(
    "/ask",
    response_model=SearchAskResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_rag)],
)
async def ask_rag(
    request: SearchAskRequest,
    current_user: User = Depends(require_permission("documents", "read")),
    rag_service: RAGService = Depends(get_rag_service),
) -> SearchAskResponse:
    """
    Case AI Assistant Q&A using Retrieval-Augmented Generation (RAG).
    Grounded strictly in authorized case document chunks with validated citations.
    Carries mandatory statutory legal disclaimer.
    Rate-limited to 15 requests/minute.
    """
    return await rag_service.ask(user=current_user, request=request)


@search_router.get(
    "/status",
    response_model=SearchStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_search_status(
    current_user: User = Depends(require_permission("documents", "read")),
    search_service: SemanticSearchService = Depends(get_semantic_search_service),
) -> SearchStatusResponse:
    """
    Returns index and embedding statistics for cases accessible to the authenticated user.
    """
    return await search_service.get_index_status(user=current_user)

