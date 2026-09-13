"""
AI Pipeline REST API Endpoints
Provides routes for document AI analysis, officer entity verification,
case-scoped semantic search, and Case AI Assistant RAG.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.models.auth import User
from app.modules.ai.dependencies import (
    get_ai_service,
    get_rag_service,
    get_semantic_search_service,
)
from app.modules.ai.rag_service import RAGService
from app.modules.ai.semantic_search import SemanticSearchService
from app.modules.ai.service import AIService
from app.modules.auth.dependencies import require_permission
from app.schemas.ai import (
    DocumentAIInsightsResponse,
    EntityVerificationRequest,
    ExtractedEntityItem,
    RAGAnswerResponse,
    RAGQuestionRequest,
    SemanticSearchRequest,
    SemanticSearchResponse,
)

logger = logging.getLogger(__name__)

ai_router = APIRouter(tags=["AI Document Intelligence"])


# ==============================================================================
# 1. Document AI Processing & Insights Endpoints
# ==============================================================================


@ai_router.post(
    "/documents/{document_id}/ai/process",
    response_model=DocumentAIInsightsResponse,
    status_code=status.HTTP_200_OK,
)
async def process_document_ai(
    document_id: UUID,
    current_user: User = Depends(require_permission("documents", "read")),
    ai_service: AIService = Depends(get_ai_service),
) -> DocumentAIInsightsResponse:
    """
    Executes or re-runs the 7-stage AI Document Intelligence Pipeline on a document.
    Enforces case membership authorization.
    """
    document = await ai_service.doc_repo.get_by_id(document_id)
    if not document:
        from app.core.exceptions import EntityNotFoundException

        raise EntityNotFoundException(detail="Document not found", error_code="DOC_001")

    await ai_service.verify_case_access(document.case_id, current_user)
    return await ai_service.process_document(document_id=document_id, actor_id=current_user.id)


@ai_router.get(
    "/documents/{document_id}/ai",
    response_model=DocumentAIInsightsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_document_ai_insights(
    document_id: UUID,
    current_user: User = Depends(require_permission("documents", "read")),
    ai_service: AIService = Depends(get_ai_service),
) -> DocumentAIInsightsResponse:
    """
    Retrieves the complete AI analysis package for a document, including:
    classification, confidence, summary, OCR text, entities, and metadata.
    """
    return await ai_service.get_document_insights(document_id=document_id, current_user=current_user)


@ai_router.patch(
    "/documents/{document_id}/entities/{entity_id}/verify",
    response_model=ExtractedEntityItem,
    status_code=status.HTTP_200_OK,
)
async def verify_extracted_entity(
    document_id: UUID,
    entity_id: UUID,
    payload: EntityVerificationRequest,
    current_user: User = Depends(require_permission("documents", "read")),
    ai_service: AIService = Depends(get_ai_service),
) -> ExtractedEntityItem:
    """
    Human-in-the-loop verification of an AI-extracted entity by an authorized officer.
    Emits an immutable audit trail event.
    """
    return await ai_service.verify_entity(
        document_id=document_id,
        entity_id=entity_id,
        verified=payload.verified,
        current_user=current_user,
    )


# ==============================================================================
# 2. Case-Scoped Semantic Search & RAG Assistant Endpoints
# ==============================================================================


@ai_router.post(
    "/cases/{case_id}/ai/search",
    response_model=SemanticSearchResponse,
    status_code=status.HTTP_200_OK,
)
async def semantic_search_case(
    case_id: UUID,
    payload: SemanticSearchRequest,
    current_user: User = Depends(require_permission("cases", "read")),
    ai_service: AIService = Depends(get_ai_service),
    search_service: SemanticSearchService = Depends(get_semantic_search_service),
) -> SemanticSearchResponse:
    """
    Executes dense vector similarity search strictly within the scope of the case.
    Non-members receive 404 to prevent unauthorized data enumeration.
    """
    await ai_service.verify_case_access(case_id, current_user)
    return await search_service.search_case(case_id=case_id, request=payload)


@ai_router.post(
    "/cases/{case_id}/ai/ask",
    response_model=RAGAnswerResponse,
    status_code=status.HTTP_200_OK,
)
async def ask_case_assistant(
    case_id: UUID,
    payload: RAGQuestionRequest,
    current_user: User = Depends(require_permission("cases", "read")),
    ai_service: AIService = Depends(get_ai_service),
    rag_service: RAGService = Depends(get_rag_service),
) -> RAGAnswerResponse:
    """
    Asks the Case AI Assistant a natural language question.
    Responses are strictly grounded in authorized case document excerpts with citations.
    """
    await ai_service.verify_case_access(case_id, current_user)
    return await rag_service.answer_question(case_id=case_id, request=payload)

