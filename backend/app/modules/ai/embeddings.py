"""
Dense Vector Embeddings Generation Service
Stage 7 in the AI Document Intelligence Pipeline.
Generates 768-dimensional embeddings for text chunks.
"""

import logging

from app.core.config import settings
from app.modules.ai.gemini_client import gemini_client

logger = logging.getLogger(__name__)


def generate_embeddings_for_chunks(chunks: list[str]) -> list[list[float]]:
    """
    Generates 768-dim embeddings for a list of text chunks.
    Ensures vector dimensions match database constraints.
    """
    if not chunks:
        return []

    embeddings = gemini_client.generate_embeddings_batch(chunks)
    # Sanity check dimension
    validated: list[list[float]] = []
    for emb in embeddings:
        if len(emb) != settings.EMBEDDING_DIMENSIONS:
            # Pad or truncate if somehow mismatching
            if len(emb) < settings.EMBEDDING_DIMENSIONS:
                emb = emb + [0.0] * (settings.EMBEDDING_DIMENSIONS - len(emb))
            else:
                emb = emb[: settings.EMBEDDING_DIMENSIONS]
        validated.append(emb)

    return validated


def generate_query_embedding(query: str) -> list[float]:
    """Generates embedding for a user search or RAG question."""
    emb = gemini_client.generate_embedding(query)
    if len(emb) != settings.EMBEDDING_DIMENSIONS:
        if len(emb) < settings.EMBEDDING_DIMENSIONS:
            emb = emb + [0.0] * (settings.EMBEDDING_DIMENSIONS - len(emb))
        else:
            emb = emb[: settings.EMBEDDING_DIMENSIONS]
    return emb

