"""
Authorization-Aware Semantic & Hybrid Search Service
Enforces strict case membership pre-retrieval filtering in SQL.
Zero cross-case leakage, Reciprocal Rank Fusion (RRF), and full audit logging.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityNotFoundException
from app.models.auth import User
from app.models.case import CaseMember
from app.modules.ai.embeddings import generate_query_embedding
from app.modules.ai.repository import AIRepository
from app.modules.audit.service import AuditService
from app.schemas.ai import (
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticSearchResultItem,
)
from app.schemas.search import (
    SearchHybridRequest,
    SearchKeywordRequest,
    SearchResponse,
    SearchResultItem,
    SearchSemanticRequest,
    SearchStatusResponse,
)

logger = logging.getLogger(__name__)


class SemanticSearchService:
    """Provides semantic, keyword, and hybrid RRF search with pre-retrieval authorization."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AIRepository(session)
        self.audit_service = AuditService(session)

    async def _get_authorized_case_ids(self, user_id: UUID, requested_case_id: UUID | None = None) -> list[UUID]:
        """
        Retrieves case IDs the user is actively authorized to access.
        If a specific case_id is requested, validates active membership;
        raises EntityNotFoundException (404) if unauthorized (IDOR defense).
        """
        if requested_case_id is not None:
            # Check specific case membership
            stmt = select(CaseMember.case_id).where(
                (CaseMember.case_id == requested_case_id)
                & (CaseMember.user_id == user_id)
                & (CaseMember.is_active == True)  # noqa: E712
            )
            res = await self.session.execute(stmt)
            if not res.scalar_one_or_none():
                raise EntityNotFoundException(f"Case {requested_case_id} not found or access not granted")
            return [requested_case_id]

        # Fetch all active case memberships for the user
        stmt = select(CaseMember.case_id).where(
            (CaseMember.user_id == user_id) & (CaseMember.is_active == True)  # noqa: E712
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def search_semantic(
        self,
        user: User,
        request: SearchSemanticRequest,
    ) -> SearchResponse:
        """
        Executes dense vector cosine similarity search in pgvector.
        Pre-retrieval authorization is strictly enforced in SQL.
        """
        authorized_case_ids = await self._get_authorized_case_ids(user.id, request.case_id)
        if not authorized_case_ids:
            return SearchResponse(
                query=request.query,
                case_id=request.case_id,
                search_type="semantic",
                total_results=0,
                results=[],
            )

        query_vector = generate_query_embedding(request.query)
        raw_results = await self.repo.search_vector_authorized(
            query_vector=query_vector,
            authorized_case_ids=authorized_case_ids,
            case_id=request.case_id,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
        )

        items = [SearchResultItem(**r) for r in raw_results]

        # Audit Trail
        await self.audit_service.record_event(
            action="search.semantic",
            actor_id=user.id,
            resource_type="search",
            resource_id=request.case_id or user.id,
            case_id=request.case_id,
            details={
                "query": request.query,
                "top_k": request.top_k,
                "min_similarity": request.min_similarity,
                "results_count": len(items),
                "scope": "case" if request.case_id else "global_authorized",
            },
            result="success",
        )
        await self.session.commit()

        return SearchResponse(
            query=request.query,
            case_id=request.case_id,
            search_type="semantic",
            total_results=len(items),
            results=items,
        )

    async def search_keyword(
        self,
        user: User,
        request: SearchKeywordRequest,
    ) -> SearchResponse:
        """
        Executes PostgreSQL keyword search over authorized document texts and metadata.
        """
        authorized_case_ids = await self._get_authorized_case_ids(user.id, request.case_id)
        if not authorized_case_ids:
            return SearchResponse(
                query=request.query,
                case_id=request.case_id,
                search_type="keyword",
                total_results=0,
                results=[],
            )

        raw_results = await self.repo.search_keyword_authorized(
            query_str=request.query,
            authorized_case_ids=authorized_case_ids,
            case_id=request.case_id,
            top_k=request.top_k,
        )

        items = [SearchResultItem(**r) for r in raw_results]

        # Audit Trail
        await self.audit_service.record_event(
            action="search.keyword",
            actor_id=user.id,
            resource_type="search",
            resource_id=request.case_id or user.id,
            case_id=request.case_id,
            details={
                "query": request.query,
                "top_k": request.top_k,
                "results_count": len(items),
                "scope": "case" if request.case_id else "global_authorized",
            },
            result="success",
        )
        await self.session.commit()

        return SearchResponse(
            query=request.query,
            case_id=request.case_id,
            search_type="keyword",
            total_results=len(items),
            results=items,
        )

    async def search_hybrid(
        self,
        user: User,
        request: SearchHybridRequest,
    ) -> SearchResponse:
        """
        Executes Hybrid Search combining semantic vector and keyword queries via Reciprocal Rank Fusion (RRF).
        """
        authorized_case_ids = await self._get_authorized_case_ids(user.id, request.case_id)
        if not authorized_case_ids:
            return SearchResponse(
                query=request.query,
                case_id=request.case_id,
                search_type="hybrid",
                total_results=0,
                results=[],
            )

        query_vector = generate_query_embedding(request.query)
        raw_results = await self.repo.search_hybrid_authorized(
            query_vector=query_vector,
            query_str=request.query,
            authorized_case_ids=authorized_case_ids,
            case_id=request.case_id,
            top_k=request.top_k,
            alpha=request.alpha,
        )

        items = [SearchResultItem(**r) for r in raw_results]

        # Audit Trail
        await self.audit_service.record_event(
            action="search.hybrid",
            actor_id=user.id,
            resource_type="search",
            resource_id=request.case_id or user.id,
            case_id=request.case_id,
            details={
                "query": request.query,
                "top_k": request.top_k,
                "alpha": request.alpha,
                "results_count": len(items),
                "scope": "case" if request.case_id else "global_authorized",
            },
            result="success",
        )
        await self.session.commit()

        return SearchResponse(
            query=request.query,
            case_id=request.case_id,
            search_type="hybrid",
            total_results=len(items),
            results=items,
        )

    async def get_index_status(self, user: User) -> SearchStatusResponse:
        """Returns index statistics for cases authorized to the user."""
        authorized_case_ids = await self._get_authorized_case_ids(user.id, requested_case_id=None)
        stats = await self.repo.get_index_statistics(authorized_case_ids)
        return SearchStatusResponse(**stats)

    async def search_case(
        self,
        case_id: UUID,
        request: SemanticSearchRequest,
    ) -> SemanticSearchResponse:
        """Legacy Phase 6 wrapper for case-scoped semantic search."""
        query_vector = generate_query_embedding(request.query)
        raw_results = await self.repo.search_case_embeddings(
            case_id=case_id,
            query_vector=query_vector,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
        )
        items = [
            SemanticSearchResultItem(
                document_id=r["document_id"],
                document_title=r["document_title"],
                document_type=r["document_type"],
                chunk_index=r["chunk_index"],
                chunk_text=r["chunk_text"],
                similarity=r["similarity"],
            )
            for r in raw_results
        ]
        return SemanticSearchResponse(
            case_id=case_id,
            query=request.query,
            results_count=len(items),
            results=items,
        )
