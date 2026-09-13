"""
AI Data Access Repository
Encapsulates CRUD operations for document metadata, extracted entities,
and pgvector embeddings with strict pre-retrieval authorization,
Reciprocal Rank Fusion (RRF) hybrid search, and version-isolated indexing.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ai import DocumentEmbedding, DocumentMetadata, ExtractedEntity
from app.models.document import Document, DocumentVersion

logger = logging.getLogger(__name__)


class AIRepository:
    """Repository handling persistence and vector search for AI artifacts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def clear_document_ai_data(self, document_id: UUID) -> None:
        """Purges previous AI analysis results when re-processing a document."""
        await self.session.execute(
            delete(ExtractedEntity).where(ExtractedEntity.document_id == document_id)
        )
        await self.session.execute(
            delete(DocumentMetadata).where(DocumentMetadata.document_id == document_id)
        )
        await self.session.execute(
            delete(DocumentEmbedding).where(DocumentEmbedding.document_id == document_id)
        )
        await self.session.flush()

    async def save_entities(
        self, document_id: UUID, entities: list[dict[str, Any]]
    ) -> list[ExtractedEntity]:
        """Bulk save extracted entities."""
        db_entities = [
            ExtractedEntity(
                document_id=document_id,
                entity_type=e["entity_type"],
                entity_value=e["entity_value"],
                confidence=e.get("confidence"),
                start_offset=e.get("start_offset"),
                end_offset=e.get("end_offset"),
                source=e.get("source", "ai"),
                verified=False,
            )
            for e in entities
        ]
        self.session.add_all(db_entities)
        await self.session.flush()
        return db_entities

    async def save_metadata_entries(
        self, document_id: UUID, metadata: list[dict[str, Any]]
    ) -> list[DocumentMetadata]:
        """Bulk save document metadata key-values."""
        db_entries = [
            DocumentMetadata(
                document_id=document_id,
                key=m["key"],
                value=str(m["value"]),
                source=m.get("source", "ai_extracted"),
                confidence=m.get("confidence"),
            )
            for m in metadata
        ]
        self.session.add_all(db_entries)
        await self.session.flush()
        return db_entries

    async def save_embeddings(
        self,
        document_id: UUID,
        case_id: UUID,
        chunks: list[str],
        embeddings: list[list[float]],
        version_id: UUID | None = None,
        version_number: int = 1,
        model_name: str | None = None,
    ) -> list[DocumentEmbedding]:
        """
        Save or upsert chunk embeddings to pgvector.
        Enforces version-isolation and stable chunk IDs: DOC-{id[:8]}-V{ver}-C{idx}.
        """
        active_model = model_name or settings.EMBEDDING_MODEL
        doc_prefix = str(document_id)[:8].upper()

        saved_embeddings: list[DocumentEmbedding] = []

        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings, strict=True)):
            chunk_id = f"DOC-{doc_prefix}-V{version_number}-C{idx}"

            if version_id is not None:
                # PostgreSQL ON CONFLICT DO UPDATE for idempotency
                insert_stmt = pg_insert(DocumentEmbedding).values(
                    document_id=document_id,
                    case_id=case_id,
                    version_id=version_id,
                    chunk_id=chunk_id,
                    chunk_index=idx,
                    chunk_text=chunk,
                    embedding=emb,
                    model_name=active_model,
                    vector_dimensions=len(emb),
                    is_searchable=True,
                )
                upsert_stmt = insert_stmt.on_conflict_do_update(
                    constraint="uq_version_chunk_model",
                    set_={
                        "chunk_text": insert_stmt.excluded.chunk_text,
                        "embedding": insert_stmt.excluded.embedding,
                        "chunk_id": insert_stmt.excluded.chunk_id,
                        "is_searchable": True,
                    },
                ).returning(DocumentEmbedding)

                res = await self.session.execute(upsert_stmt)
                record = res.scalar_one()
                await self.session.refresh(record)
                saved_embeddings.append(record)
            else:
                record = DocumentEmbedding(
                    document_id=document_id,
                    case_id=case_id,
                    version_id=None,
                    chunk_id=chunk_id,
                    chunk_index=idx,
                    chunk_text=chunk,
                    embedding=emb,
                    model_name=active_model,
                    vector_dimensions=len(emb),
                    is_searchable=True,
                )
                self.session.add(record)
                saved_embeddings.append(record)

        await self.session.flush()
        return saved_embeddings

    async def invalidate_version_embeddings(self, version_id: UUID) -> int:
        """Mark all embeddings for a compromised or corrupted version as unsearchable."""
        result = await self.session.execute(
            update(DocumentEmbedding)
            .where(DocumentEmbedding.version_id == version_id)
            .values(is_searchable=False)
        )
        await self.session.flush()
        return result.rowcount

    async def get_entities(self, document_id: UUID) -> list[ExtractedEntity]:
        """Retrieve all extracted entities for a document."""
        result = await self.session.execute(
            select(ExtractedEntity)
            .where(ExtractedEntity.document_id == document_id)
            .order_by(ExtractedEntity.entity_type, ExtractedEntity.created_at)
        )
        return list(result.scalars().all())

    async def verify_entity(self, entity_id: UUID, verified: bool) -> ExtractedEntity | None:
        """Mark an entity as officer-verified or unverified."""
        result = await self.session.execute(
            select(ExtractedEntity).where(ExtractedEntity.id == entity_id)
        )
        entity = result.scalar_one_or_none()
        if entity:
            entity.verified = verified
            await self.session.flush()
        return entity

    async def get_metadata(self, document_id: UUID) -> list[DocumentMetadata]:
        """Retrieve all metadata entries for a document."""
        result = await self.session.execute(
            select(DocumentMetadata)
            .where(DocumentMetadata.document_id == document_id)
            .order_by(DocumentMetadata.key)
        )
        return list(result.scalars().all())

    async def get_embeddings_count(self, document_id: UUID) -> int:
        """Return the number of stored vector chunks for a document."""
        result = await self.session.execute(
            select(func.count(DocumentEmbedding.id)).where(DocumentEmbedding.document_id == document_id)
        )
        return result.scalar_one() or 0

    async def search_case_embeddings(
        self,
        case_id: UUID,
        query_vector: list[float],
        top_k: int = 10,
        min_similarity: float = 0.4,
    ) -> list[dict[str, Any]]:
        """
        Legacy case-scoped vector cosine similarity search.
        Preserved for backwards compatibility with Phase 6 endpoints.
        """
        return await self.search_vector_authorized(
            query_vector=query_vector,
            authorized_case_ids=[case_id],
            case_id=case_id,
            top_k=top_k,
            min_similarity=min_similarity,
        )

    async def search_vector_authorized(
        self,
        query_vector: list[float],
        authorized_case_ids: list[UUID],
        case_id: UUID | None = None,
        top_k: int = 10,
        min_similarity: float = 0.4,
    ) -> list[dict[str, Any]]:
        """
        Perform vector cosine similarity search in pgvector with strict pre-retrieval authorization.
        Authorization happens directly in the SQL WHERE clause.
        Zero cross-case data leakage.
        """
        if not authorized_case_ids:
            return []

        target_case_ids = [case_id] if case_id is not None else authorized_case_ids
        # Ensure targeted case is within authorized list
        target_case_ids = [cid for cid in target_case_ids if cid in authorized_case_ids]
        if not target_case_ids:
            return []

        # Cosine distance in pgvector: DocumentEmbedding.embedding.cosine_distance(query_vector)
        # Cosine similarity = 1 - cosine distance
        cosine_dist = DocumentEmbedding.embedding.cosine_distance(query_vector).label("distance")

        stmt = (
            select(
                DocumentEmbedding,
                Document.title.label("document_title"),
                Document.document_type.label("document_type"),
                DocumentVersion.version_number.label("version_number"),
                cosine_dist,
            )
            .join(Document, DocumentEmbedding.document_id == Document.id)
            .outerjoin(DocumentVersion, DocumentEmbedding.version_id == DocumentVersion.id)
            .where(
                DocumentEmbedding.case_id.in_(target_case_ids),
                DocumentEmbedding.is_searchable.is_(True),
                Document.status != "deleted",
                or_(
                    DocumentVersion.integrity_status.is_(None),
                    DocumentVersion.integrity_status != "compromised",
                ),
            )
            .order_by(cosine_dist)
            .limit(top_k * 2)
        )

        rows = (await self.session.execute(stmt)).all()
        results: list[dict[str, Any]] = []

        for emb, doc_title, doc_type, ver_num, dist in rows:
            if dist is None:
                continue
            similarity = round(1.0 - float(dist), 4)
            if similarity >= min_similarity:
                chunk_id = emb.chunk_id or f"DOC-{str(emb.document_id)[:8].upper()}-V{ver_num or 1}-C{emb.chunk_index}"
                results.append(
                    {
                        "chunk_id": chunk_id,
                        "document_id": emb.document_id,
                        "case_id": emb.case_id,
                        "version_id": emb.version_id,
                        "version_number": ver_num or 1,
                        "document_title": doc_title,
                        "document_type": doc_type,
                        "chunk_index": emb.chunk_index,
                        "chunk_text": emb.chunk_text,
                        "similarity": similarity,
                        "search_type": "semantic",
                    }
                )

        return results[:top_k]

    async def search_keyword_authorized(
        self,
        query_str: str,
        authorized_case_ids: list[UUID],
        case_id: UUID | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Keyword and full-text search across authorized documents, entities, and chunk text.
        Executed strictly within the pre-authorized case scope in SQL.
        """
        if not authorized_case_ids or not query_str.strip():
            return []

        target_case_ids = [case_id] if case_id is not None else authorized_case_ids
        target_case_ids = [cid for cid in target_case_ids if cid in authorized_case_ids]
        if not target_case_ids:
            return []

        terms = [t.strip() for t in query_str.split() if len(t.strip()) > 1][:5]
        if not terms:
            terms = [query_str.strip()]

        # Build term filters for chunk text and document title
        ilike_filters = [
            or_(
                DocumentEmbedding.chunk_text.ilike(f"%{term}%"),
                Document.title.ilike(f"%{term}%"),
                Document.summary.ilike(f"%{term}%"),
            )
            for term in terms
        ]

        stmt = (
            select(
                DocumentEmbedding,
                Document.title.label("document_title"),
                Document.document_type.label("document_type"),
                DocumentVersion.version_number.label("version_number"),
            )
            .join(Document, DocumentEmbedding.document_id == Document.id)
            .outerjoin(DocumentVersion, DocumentEmbedding.version_id == DocumentVersion.id)
            .where(
                DocumentEmbedding.case_id.in_(target_case_ids),
                DocumentEmbedding.is_searchable.is_(True),
                Document.status != "deleted",
                or_(
                    DocumentVersion.integrity_status.is_(None),
                    DocumentVersion.integrity_status != "compromised",
                ),
                or_(*ilike_filters),
            )
            .limit(top_k * 3)
        )

        rows = (await self.session.execute(stmt)).all()
        results: list[dict[str, Any]] = []

        query_lower = query_str.lower()
        for emb, doc_title, doc_type, ver_num in rows:
            text_lower = emb.chunk_text.lower()
            title_lower = (doc_title or "").lower()

            # Calculate frequency-based relevance score
            match_count = sum(text_lower.count(t.lower()) for t in terms)
            if query_lower in text_lower:
                match_count += 3
            if query_lower in title_lower:
                match_count += 4

            score = round(min(1.0, 0.4 + (match_count * 0.1)), 4)
            chunk_id = emb.chunk_id or f"DOC-{str(emb.document_id)[:8].upper()}-V{ver_num or 1}-C{emb.chunk_index}"

            results.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": emb.document_id,
                    "case_id": emb.case_id,
                    "version_id": emb.version_id,
                    "version_number": ver_num or 1,
                    "document_title": doc_title,
                    "document_type": doc_type,
                    "chunk_index": emb.chunk_index,
                    "chunk_text": emb.chunk_text,
                    "similarity": score,
                    "search_type": "keyword",
                }
            )

        # Sort by score descending
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    async def search_hybrid_authorized(
        self,
        query_vector: list[float],
        query_str: str,
        authorized_case_ids: list[UUID],
        case_id: UUID | None = None,
        top_k: int = 10,
        alpha: float = 0.7,
    ) -> list[dict[str, Any]]:
        """
        Hybrid Search using Reciprocal Rank Fusion (RRF).
        Merges dense vector semantic search (alpha weight) and sparse keyword search (1 - alpha weight).
        RRF formula: Score(d) = alpha * (1 / (k + rank_sem)) + (1 - alpha) * (1 / (k + rank_kw))
        where k = 60 (standard TREC constant).
        """
        # Retrieve candidates from both branches
        k_rrf = 60.0
        candidate_k = max(top_k * 2, 20)

        semantic_results = await self.search_vector_authorized(
            query_vector=query_vector,
            authorized_case_ids=authorized_case_ids,
            case_id=case_id,
            top_k=candidate_k,
            min_similarity=0.2,
        )

        keyword_results = await self.search_keyword_authorized(
            query_str=query_str,
            authorized_case_ids=authorized_case_ids,
            case_id=case_id,
            top_k=candidate_k,
        )

        # Index candidates by chunk_id
        items_by_id: dict[str, dict[str, Any]] = {}
        rrf_scores: dict[str, float] = {}

        for rank, item in enumerate(semantic_results, start=1):
            cid = item["chunk_id"]
            items_by_id[cid] = item
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (alpha * (1.0 / (k_rrf + rank)))

        for rank, item in enumerate(keyword_results, start=1):
            cid = item["chunk_id"]
            if cid not in items_by_id:
                items_by_id[cid] = item
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + ((1.0 - alpha) * (1.0 / (k_rrf + rank)))

        # Sort by merged RRF score
        sorted_cids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

        final_results: list[dict[str, Any]] = []
        max_rrf = rrf_scores[sorted_cids[0]] if sorted_cids else 1.0

        for cid in sorted_cids[:top_k]:
            item = dict(items_by_id[cid])
            # Normalize RRF score to 0.0 - 1.0 range
            norm_score = round(rrf_scores[cid] / max_rrf, 4) if max_rrf > 0 else 0.5
            item["similarity"] = norm_score
            item["rrf_score"] = round(rrf_scores[cid], 6)
            item["search_type"] = "hybrid"
            final_results.append(item)

        return final_results

    async def get_index_statistics(self, authorized_case_ids: list[UUID]) -> dict[str, Any]:
        """Return index statistics for user-accessible cases."""
        if not authorized_case_ids:
            return {
                "total_embeddings": 0,
                "searchable_embeddings": 0,
                "indexed_documents_count": 0,
                "model_name": settings.EMBEDDING_MODEL,
                "vector_dimensions": settings.EMBEDDING_DIMENSIONS,
            }

        total_stmt = select(func.count(DocumentEmbedding.id)).where(
            DocumentEmbedding.case_id.in_(authorized_case_ids)
        )
        searchable_stmt = select(func.count(DocumentEmbedding.id)).where(
            DocumentEmbedding.case_id.in_(authorized_case_ids),
            DocumentEmbedding.is_searchable.is_(True),
        )
        docs_stmt = select(func.count(func.distinct(DocumentEmbedding.document_id))).where(
            DocumentEmbedding.case_id.in_(authorized_case_ids),
            DocumentEmbedding.is_searchable.is_(True),
        )

        total = (await self.session.execute(total_stmt)).scalar_one() or 0
        searchable = (await self.session.execute(searchable_stmt)).scalar_one() or 0
        docs_count = (await self.session.execute(docs_stmt)).scalar_one() or 0

        return {
            "total_embeddings": total,
            "searchable_embeddings": searchable,
            "indexed_documents_count": docs_count,
            "model_name": settings.EMBEDDING_MODEL,
            "vector_dimensions": settings.EMBEDDING_DIMENSIONS,
        }
