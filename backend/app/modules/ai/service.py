"""
AI Document Intelligence Pipeline Service
Coordinates the 7-stage processing workflow:
Document -> Text Extraction -> OCR -> Document Classification -> Entity Extraction -> Metadata & Summary -> Chunking -> Embeddings (pgvector)
"""

import hashlib
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import EntityNotFoundException
from app.models.auth import User
from app.models.document import Document
from app.modules.ai.chunking import split_text
from app.modules.ai.classification import classify_document
from app.modules.ai.embeddings import generate_embeddings_for_chunks
from app.modules.ai.entity_extraction import extract_entities
from app.modules.ai.ocr_service import perform_ocr
from app.modules.ai.repository import AIRepository
from app.modules.ai.summarization import extract_metadata_entries, generate_summary
from app.modules.ai.text_extraction import extract_document_text
from app.modules.audit.service import AuditService
from app.modules.cases.repository import CaseRepository
from app.modules.documents.repository import DocumentRepository
from app.schemas.ai import (
    DocumentAIInsightsResponse,
    DocumentMetadataItem,
    ExtractedEntityItem,
)
from app.storage.s3 import S3StorageService
from app.storage.service import StorageService

logger = logging.getLogger(__name__)


class AIService:
    """Orchestrates end-to-end AI document intelligence and analysis."""

    def __init__(
        self,
        session: AsyncSession,
        storage: StorageService | None = None,
    ):
        self.session = session
        self.repo = AIRepository(session)
        self.doc_repo = DocumentRepository(session)
        self.case_repo = CaseRepository(session)
        self.audit_service = AuditService(session)
        self.storage = storage or S3StorageService()

    async def verify_case_access(self, case_id: UUID, user: User) -> None:
        """
        Enforce zero-trust case scoping.
        Non-members receive 404 to avoid enumeration.
        """
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise EntityNotFoundException(detail="Case not found", error_code="CASE_001")

        membership = await self.case_repo.check_membership(case_id, user.id)
        if not membership:
            raise EntityNotFoundException(detail="Case not found", error_code="CASE_001")

    async def process_document(
        self,
        document_id: UUID,
        actor_id: UUID | None = None,
    ) -> DocumentAIInsightsResponse:
        """
        Executes the 7-stage AI Document Intelligence Pipeline.
        """
        document = await self.doc_repo.get_document_by_id(document_id)
        if not document:
            raise EntityNotFoundException(detail="Document not found", error_code="DOC_001")

        if not document.current_version:
            raise EntityNotFoundException(detail="Document has no active version", error_code="DOC_002")

        logger.info(f"Starting AI Pipeline for document {document.id} ({document.title})")

        # Clear existing AI artifacts for clean re-processing
        await self.repo.clear_document_ai_data(document_id)

        try:
            # Stage 1: Document Retrieval from Object Storage
            storage_key = document.current_version.storage_key
            storage_bucket = document.current_version.storage_bucket or settings.S3_BUCKET_DOCUMENTS
            filename = document.current_version.original_filename or document.original_filename or ""
            mime_type = document.current_version.mime_type or document.mime_type or ""

            file_bytes = self.storage.download(storage_key, storage_bucket)

            # Integrity Verification Gate: Verify payload hash matches version SHA-256 before processing
            if document.current_version and document.current_version.file_hash_sha256:
                computed_hash = hashlib.sha256(file_bytes).hexdigest()
                if computed_hash.lower() != document.current_version.file_hash_sha256.lower():
                    logger.error(
                        f"Integrity check failed for document {document.id} version {document.current_version.id}! "
                        f"Expected {document.current_version.file_hash_sha256}, got {computed_hash}"
                    )
                    document.current_version.integrity_status = "compromised"
                    document.ai_processed = False
                    document.ai_processing_error = (
                        "Integrity verification failed: storage payload hash does not match version SHA-256."
                    )
                    await self.repo.invalidate_version_embeddings(document.current_version.id)
                    await self.audit_service.record_event(
                        action="embedding.integrity_rejected",
                        actor_id=actor_id,
                        resource_type="document_version",
                        resource_id=document.current_version.id,
                        case_id=document.case_id,
                        details={
                            "expected_sha256": document.current_version.file_hash_sha256,
                            "actual_sha256": computed_hash,
                            "reason": "SHA-256 payload tampering detected during AI pipeline",
                        },
                        result="failure",
                    )
                    await self.session.commit()
                    raise ValueError(
                        f"Security Alert: Document version integrity check failed (expected {document.current_version.file_hash_sha256[:12]}..., got {computed_hash[:12]}...)"
                    )

            # Stage 2: Text Extraction & OCR
            extracted_text, is_scanned = extract_document_text(
                file_bytes=file_bytes,
                filename=filename,
                mime_type=mime_type,
            )

            ocr_text = None
            if (is_scanned or not extracted_text.strip()) and settings.OCR_ENABLED:
                logger.info(f"Triggering OCR for document {document.id}")
                ocr_result = perform_ocr(file_bytes, mime_type)
                if ocr_result.text.strip():
                    ocr_text = ocr_result.text.strip()

            combined_text = extracted_text.strip()
            if ocr_text:
                if combined_text:
                    combined_text = f"{combined_text}\n\n--- OCR EXTRACTED TEXT ---\n{ocr_text}"
                else:
                    combined_text = ocr_text

            if not combined_text:
                document.ai_processed = False
                document.ai_processing_error = "Unable to extract readable text or OCR characters."
                await self.session.commit()
                return await self.get_document_insights_internal(document)

            # Stage 3: Document Classification
            classification = classify_document(combined_text, filename)

            # Stage 4: Entity Extraction
            raw_entities = extract_entities(combined_text)

            # Stage 5: Metadata & Summarization
            summary = generate_summary(combined_text, classification.document_type)
            raw_metadata = extract_metadata_entries(
                text=combined_text,
                doc_type=classification.document_type,
                entities=raw_entities,
                ocr_applied=bool(ocr_text),
            )

            # Stage 6: Chunking
            chunks = split_text(combined_text)

            # Stage 7: Embeddings & Vector Storage
            embeddings = generate_embeddings_for_chunks(chunks)

            # Persist entities, metadata, and chunk vectors
            db_entities = await self.repo.save_entities(document_id, raw_entities)
            db_metadata = await self.repo.save_metadata_entries(document_id, raw_metadata)
            if chunks and embeddings:
                version_id = document.current_version.id if document.current_version else None
                version_number = document.current_version.version_number if document.current_version else 1
                await self.repo.save_embeddings(
                    document_id=document_id,
                    case_id=document.case_id,
                    chunks=chunks,
                    embeddings=embeddings,
                    version_id=version_id,
                    version_number=version_number,
                )
                await self.audit_service.record_event(
                    action="embedding.generated",
                    actor_id=actor_id,
                    resource_type="document_version",
                    resource_id=version_id or document.id,
                    case_id=document.case_id,
                    details={
                        "chunks_count": len(chunks),
                        "model": settings.EMBEDDING_MODEL,
                        "vector_dimensions": settings.EMBEDDING_DIMENSIONS,
                    },
                    result="success",
                )

            # Update Document Model
            document.ai_processed = True
            document.ai_classification = classification.document_type
            document.ai_confidence = classification.confidence
            document.ocr_text = ocr_text
            document.summary = summary
            document.ai_processing_error = None

            # Record Audit Trail Event
            await self.audit_service.record_event(
                action="document.ai_processed",
                actor_id=actor_id,
                resource_type="document",
                resource_id=document.id,
                case_id=document.case_id,
                details={
                    "classification": classification.document_type,
                    "confidence": classification.confidence,
                    "entities_count": len(db_entities),
                    "metadata_count": len(db_metadata),
                    "chunks_count": len(chunks),
                    "ocr_applied": bool(ocr_text),
                },
                result="success",
            )

            await self.session.commit()
            logger.info(f"AI Pipeline completed successfully for document {document.id}")

            return DocumentAIInsightsResponse(
                document_id=document.id,
                ai_processed=True,
                ai_classification=document.ai_classification,
                ai_confidence=document.ai_confidence,
                summary=document.summary,
                ocr_text=document.ocr_text,
                entities=[ExtractedEntityItem.model_validate(e) for e in db_entities],
                metadata_entries=[DocumentMetadataItem.model_validate(m) for m in db_metadata],
                chunk_count=len(chunks),
                ai_processing_error=None,
            )

        except Exception as exc:
            logger.exception(f"AI Pipeline failed for document {document.id}: {exc}")
            document.ai_processed = False
            document.ai_processing_error = str(exc)
            await self.session.commit()
            raise

    async def get_document_insights_internal(
        self, document: Document
    ) -> DocumentAIInsightsResponse:
        """Helper to build insights response from persisted database records."""
        entities = await self.repo.get_entities(document.id)
        metadata = await self.repo.get_metadata(document.id)
        chunk_count = await self.repo.get_embeddings_count(document.id)

        return DocumentAIInsightsResponse(
            document_id=document.id,
            ai_processed=document.ai_processed,
            ai_classification=document.ai_classification,
            ai_confidence=document.ai_confidence,
            summary=document.summary,
            ocr_text=document.ocr_text,
            entities=[ExtractedEntityItem.model_validate(e) for e in entities],
            metadata_entries=[DocumentMetadataItem.model_validate(m) for m in metadata],
            chunk_count=chunk_count,
            ai_processing_error=document.ai_processing_error,
        )

    async def get_document_insights(
        self, document_id: UUID, current_user: User
    ) -> DocumentAIInsightsResponse:
        """Officer-authenticated retrieval of document AI analysis."""
        document = await self.doc_repo.get_by_id(document_id)
        if not document:
            raise EntityNotFoundException(detail="Document not found", error_code="DOC_001")

        await self.verify_case_access(document.case_id, current_user)
        return await self.get_document_insights_internal(document)

    async def verify_entity(
        self,
        document_id: UUID,
        entity_id: UUID,
        verified: bool,
        current_user: User,
    ) -> ExtractedEntityItem:
        """Human-in-the-loop verification of an AI extracted entity."""
        document = await self.doc_repo.get_by_id(document_id)
        if not document:
            raise EntityNotFoundException(detail="Document not found", error_code="DOC_001")

        await self.verify_case_access(document.case_id, current_user)

        updated_entity = await self.repo.verify_entity(entity_id, verified)
        if not updated_entity or updated_entity.document_id != document_id:
            raise EntityNotFoundException(detail="Extracted entity not found", error_code="AI_001")

        await self.audit_service.record_event(
            action="entity.verified" if verified else "entity.unverified",
            actor_id=current_user.id,
            resource_type="extracted_entity",
            resource_id=updated_entity.id,
            case_id=document.case_id,
            details={
                "document_id": str(document.id),
                "entity_type": updated_entity.entity_type,
                "entity_value": updated_entity.entity_value,
                "verified": verified,
            },
            result="success",
        )

        await self.session.commit()
        return ExtractedEntityItem.model_validate(updated_entity)
