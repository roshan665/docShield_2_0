"""
Legal Document Summarization & Metadata Enrichment Service
Stage 5 in the AI Document Intelligence Pipeline.
Generates concise 150-300 word executive legal summaries and key-value metadata pairs.
"""

import logging
from typing import Any

from app.modules.ai.gemini_client import gemini_client

logger = logging.getLogger(__name__)


def generate_summary(text: str, doc_type: str = "document") -> str:
    """
    Generates a professional 150-300 word legal executive summary.
    Uses Gemini LLM if available; otherwise falls back to deterministic extractive summarization.
    """
    cleaned_text = text.strip()
    if not cleaned_text:
        return "No text content available to summarize."

    # If text is already very brief
    words = cleaned_text.split()
    if len(words) <= 100:
        return cleaned_text

    # 1. Attempt LLM generation
    if gemini_client.is_configured:
        prompt = f"""
You are an executive legal analyst for law enforcement and judicial officers.
Summarize this {doc_type} in 150 to 250 words.
Focus on:
1. Core matter / alleged offences / sections of law
2. Primary parties involved (informant, accused, witnesses)
3. Key dates, locations, and actions taken
4. Status or operational directive

Text:
\"\"\"
{cleaned_text[:4000]}
\"\"\"

Produce a concise, factual, objective summary suitable for courtroom briefing.
"""
        res = gemini_client.generate_text(
            prompt,
            system_instruction="Provide a factual, objective, court-grade summary. Do not speculate.",
        )
        if res and len(res.split()) >= 20:
            return res.strip()

    # 2. Extractive fallback
    # Break into sentences or paragraphs and select representative pieces
    paragraphs = [p.strip() for p in cleaned_text.split("\n\n") if len(p.strip()) > 30]
    if not paragraphs:
        paragraphs = [p.strip() for p in cleaned_text.split("\n") if len(p.strip()) > 30]

    if not paragraphs:
        return " ".join(words[:150]) + "..."

    summary_parts = []
    # Take first paragraph (often header/intro/charges)
    summary_parts.append(paragraphs[0])

    # Search for paragraph mentioning sections or charges or incidents
    middle_candidates = [
        p for p in paragraphs[1:-1]
        if any(term in p.lower() for term in ["section", "ipc", "accused", "incident", "investigation", "seized"])
    ]
    if middle_candidates:
        summary_parts.append(middle_candidates[0])
    elif len(paragraphs) > 2:
        summary_parts.append(paragraphs[1])

    # Take concluding paragraph
    if len(paragraphs) > 1 and paragraphs[-1] not in summary_parts:
        summary_parts.append(paragraphs[-1])

    combined_summary = " ".join(summary_parts)
    summary_words = combined_summary.split()
    if len(summary_words) > 250:
        return " ".join(summary_words[:250]) + "..."
    return combined_summary


def extract_metadata_entries(
    text: str,
    doc_type: str,
    entities: list[dict[str, Any]],
    ocr_applied: bool = False,
) -> list[dict[str, Any]]:
    """
    Produces structured key-value metadata entries for the document.
    """
    metadata: list[dict[str, Any]] = [
        {
            "key": "document_classification",
            "value": doc_type,
            "source": "ai_extracted",
            "confidence": 0.95,
        },
        {
            "key": "word_count",
            "value": str(len(text.split())),
            "source": "system",
            "confidence": 1.0,
        },
        {
            "key": "ocr_processed",
            "value": "true" if ocr_applied else "false",
            "source": "system",
            "confidence": 1.0,
        },
    ]

    # Map salient entities to metadata keys
    fir_ents = [e["entity_value"] for e in entities if e["entity_type"] == "fir_number"]
    if fir_ents:
        metadata.append({"key": "fir_number", "value": fir_ents[0], "source": "ai_extracted", "confidence": 0.90})

    case_ents = [e["entity_value"] for e in entities if e["entity_type"] == "case_number"]
    if case_ents:
        metadata.append({"key": "case_number", "value": case_ents[0], "source": "ai_extracted", "confidence": 0.90})

    ps_ents = [e["entity_value"] for e in entities if e["entity_type"] == "police_station"]
    if ps_ents:
        metadata.append({"key": "police_station", "value": ps_ents[0], "source": "ai_extracted", "confidence": 0.90})

    sections = [e["entity_value"] for e in entities if e["entity_type"] == "law_section"]
    if sections:
        metadata.append({"key": "applicable_sections", "value": ", ".join(sections[:5]), "source": "ai_extracted", "confidence": 0.85})

    return metadata

