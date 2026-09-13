"""
Document Chunking Service
Stage 6 in the AI Document Intelligence Pipeline.
Recursive text splitter preserving legal paragraph and sentence boundaries.
"""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def split_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """
    Recursively split text into overlapping chunks respecting natural separators.
    Default parameters: chunk_size=1000, chunk_overlap=200.
    """
    c_size = chunk_size or settings.CHUNK_SIZE
    c_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    cleaned = text.strip()
    if not cleaned:
        return []

    if len(cleaned) <= c_size:
        return [cleaned]

    separators = ["\n\n", "\n", ". ", "; ", ", ", " "]

    def _split_with_separators(txt: str, seps: list[str]) -> list[str]:
        if not seps:
            # Character level fallback
            return [txt[i : i + c_size] for i in range(0, len(txt), c_size - c_overlap)]

        sep = seps[0]
        splits = txt.split(sep)
        chunks: list[str] = []
        current_chunk = ""

        for part in splits:
            candidate = f"{current_chunk}{sep}{part}" if current_chunk else part
            if len(candidate) <= c_size:
                current_chunk = candidate
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                if len(part) > c_size:
                    # Recursive sub-split
                    sub_chunks = _split_with_separators(part, seps[1:])
                    chunks.extend(sub_chunks)
                    current_chunk = ""
                else:
                    current_chunk = part

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    raw_chunks = _split_with_separators(cleaned, separators)

    # Merge small trailing leftovers where needed
    final_chunks: list[str] = []
    min_chunk_threshold = min(c_overlap, c_size // 4, 30)
    for chunk in raw_chunks:
        if not chunk:
            continue
        if len(chunk) < min_chunk_threshold and final_chunks:
            # Append tiny leftovers to previous chunk
            final_chunks[-1] = f"{final_chunks[-1]}\n{chunk}"
        else:
            final_chunks.append(chunk)

    return final_chunks
