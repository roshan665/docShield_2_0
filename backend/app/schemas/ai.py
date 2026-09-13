"""
AI Pipeline Pydantic Schemas
Defines request/response models for document classification, entity extraction,
metadata enrichment, semantic search, and RAG question-answering.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClassificationResult(BaseModel):
    """Result from automated document classification."""
    document_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str | None = None


class ExtractedEntityItem(BaseModel):
    """Single named entity extracted from legal document."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    entity_type: str
    entity_value: str
    confidence: float | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    source: str = "ai"
    verified: bool = False
    created_at: datetime


class EntityVerificationRequest(BaseModel):
    """Request by an authorized officer to verify or unverify an AI-extracted entity."""
    verified: bool = True


class DocumentMetadataItem(BaseModel):
    """Key-value metadata pair for a document."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    key: str
    value: str
    source: str = "ai_extracted"
    confidence: float | None = None
    verified_by: UUID | None = None
    verified_at: datetime | None = None
    created_at: datetime


class DocumentAIInsightsResponse(BaseModel):
    """Comprehensive AI analysis package for a document."""
    document_id: UUID
    ai_processed: bool
    ai_classification: str | None = None
    ai_confidence: float | None = None
    summary: str | None = None
    ocr_text: str | None = None
    entities: list[ExtractedEntityItem] = []
    metadata_entries: list[DocumentMetadataItem] = []
    chunk_count: int = 0
    ai_processing_error: str | None = None


class SemanticSearchRequest(BaseModel):
    """Request for case-scoped vector similarity search."""
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=50)
    min_similarity: float = Field(default=0.4, ge=0.0, le=1.0)


class SemanticSearchResultItem(BaseModel):
    """Ranked vector similarity search match."""
    document_id: UUID
    document_title: str
    document_type: str
    chunk_index: int
    chunk_text: str
    similarity: float


class SemanticSearchResponse(BaseModel):
    """List of semantic search matches."""
    case_id: UUID
    query: str
    results_count: int
    results: list[SemanticSearchResultItem]


class RAGQuestionRequest(BaseModel):
    """Natural language question directed at the Case AI Assistant."""
    question: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=15)


class RAGSourceReference(BaseModel):
    """Document citation grounding an AI-generated answer."""
    document_id: UUID
    document_title: str
    document_type: str
    chunk_index: int
    snippet: str


class RAGAnswerResponse(BaseModel):
    """Court-admissible grounded RAG assistant answer with source citations."""
    case_id: UUID
    question: str
    answer: str
    sources: list[RAGSourceReference]
    ai_generated: bool = True
    disclaimer: str = (
        "AI-generated response for investigative assistance. "
        "Strictly verified against authorized case documents. Not legal advice."
    )

