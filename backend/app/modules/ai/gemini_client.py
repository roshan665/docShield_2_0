"""
Google Gemini AI & Fallback Provider Client
Handles interaction with Google Gemini 2.5 Flash and text-embedding-004,
with robust offline fallback for air-gapped or keyless testing environments.
"""

import hashlib
import logging
import math
import re

from app.core.config import settings

logger = logging.getLogger(__name__)

# Check if google.generativeai is available
try:
    import google.generativeai as genai

    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    GENAI_AVAILABLE = False


def _hash_vector(text: str, dim: int = 768) -> list[float]:
    """
    Generate a deterministic unit vector of dimension `dim` based on text tokens.
    Used when Gemini API is unavailable or offline.
    Uses bag-of-words and character n-gram hashing to preserve pseudo-similarity.
    """
    vec = [0.0] * dim
    words = re.findall(r"\w+", text.lower())
    if not words:
        words = ["empty"]

    for word in words:
        # Hash each word into vector buckets
        h = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if ((h >> 8) & 1) else -1.0
        vec[idx] += sign

    # Also add character 3-grams for subword similarity
    for i in range(len(text) - 2):
        trigram = text[i : i + 3].lower()
        h = int(hashlib.md5(trigram.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 0.5 if ((h >> 4) & 1) else -0.5
        vec[idx] += sign

    # Normalize to unit length (L2 norm)
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [round(x / norm, 6) for x in vec]
    else:
        vec[0] = 1.0
    return vec


class GeminiClient:
    """Client for Google Gemini LLM and Embedding models with fallback."""

    def __init__(self) -> None:
        self.api_key = settings.GEMINI_API_KEY
        self.is_configured = False
        if self.api_key and GENAI_AVAILABLE:
            try:
                genai.configure(api_key=self.api_key)
                self.is_configured = True
                logger.info("Google Gemini client configured with provided API key.")
            except Exception as e:
                logger.warning(f"Failed to configure Gemini client: {e}. Using fallback.")
        else:
            logger.info("No GEMINI_API_KEY found. Utilizing deterministic local NLP fallback.")

    def generate_embedding(self, text: str) -> list[float]:
        """Generate 768-dimensional dense vector embedding."""
        if self.is_configured and GENAI_AVAILABLE:
            try:
                result = genai.embed_content(
                    model=settings.EMBEDDING_MODEL,
                    content=text,
                    task_type="retrieval_document",
                )
                embedding = result.get("embedding")
                if embedding and len(embedding) == settings.EMBEDDING_DIMENSIONS:
                    return [float(x) for x in embedding]
            except Exception as e:
                logger.warning(f"Gemini embedding API call failed: {e}. Falling back to deterministic vector.")

        return _hash_vector(text, settings.EMBEDDING_DIMENSIONS)

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch embedding generation for text chunks."""
        return [self.generate_embedding(t) for t in texts]

    def generate_text(self, prompt: str, system_instruction: str | None = None) -> str:
        """Call Gemini LLM with prompt and optional system instructions."""
        if self.is_configured and GENAI_AVAILABLE:
            try:
                model = genai.GenerativeModel(
                    model_name=settings.GEMINI_MODEL,
                    system_instruction=system_instruction,
                )
                response = model.generate_content(prompt)
                if response.text:
                    return response.text.strip()
            except Exception as e:
                logger.warning(f"Gemini text generation failed: {e}. Falling back.")

        return ""


gemini_client = GeminiClient()

