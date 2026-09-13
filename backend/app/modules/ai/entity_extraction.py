"""
Indian Legal Named Entity Recognition (NER) Service
Stage 4 in the AI Document Intelligence Pipeline.
Extracts domain-specific legal entities:
- law_section, fir_number, case_number, police_station, date
- person, organization, location, evidence_ref, phone_number, vehicle_number
"""

import json
import logging
import re
from typing import Any

from app.models.ai import ENTITY_TYPES
from app.modules.ai.gemini_client import gemini_client

logger = logging.getLogger(__name__)

# Regex definitions for Indian legal patterns
PATTERNS = {
    "fir_number": [
        r"(?:F\.?I\.?R\.?(?:\s*(?:No|Number))?[\s.:/-]*)([\w/]+(?:/\d{2,4})?)",
        r"(?:Crime\s*No[\s.:/-]*)([\w/]+(?:/\d{2,4})?)",
    ],
    "case_number": [
        r"(?:(?:Crl\.?\s*(?:A|Misc|Rev|No)|CC|Sessions\s*Case|SC|Criminal\s*Appeal)[\s.:/-]*)([\w/]+(?:/\d{2,4})?)",
        r"(?:Special\s*Case\s*No[\s.:/-]*)([\w/]+(?:/\d{2,4})?)",
    ],
    "law_section": [
        r"(?:(?:Section|Sec\.?|u/s|U/S)\s*)([0-9]{1,4}(?:-[A-Za-z]+)?(?:\s*\([0-9a-zA-Z]+\))*(?:\s*(?:r/w|read\s*with)\s*[0-9]{1,4})*(?:\s*(?:IPC|CrPC|BNS|BNSS|NDPS|POCSO|Arms\s*Act|IT\s*Act|Motor\s*Vehicles\s*Act))?)",
        r"\b([0-9]{3}(?:-[A-Z])?\s+(?:IPC|BNS|CrPC))\b",
    ],
    "police_station": [
        r"(?:(?:Police\s*Station|P\.?S\.?)[\s.:/-]*)([A-Za-z\s]+?)(?:,\s*|\.\s*|\n|\s+District|\s+Dist)",
    ],
    "date": [
        r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
        r"\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{4})\b",
    ],
    "phone_number": [
        r"(?:\+91[\s-]?)?([6-9]\d{9})\b",
    ],
    "vehicle_number": [
        r"\b([A-Z]{2}[-\s]?[0-9]{1,2}[-\s]?[A-Z]{1,3}[-\s]?[0-9]{4})\b",
    ],
    "evidence_ref": [
        r"(?:(?:Exhibit|Ex\.|Article|M\.O\.|Item)[\s.:/-]*)([A-Za-z0-9-]+)",
    ],
}


def extract_regex_entities(text: str) -> list[dict[str, Any]]:
    """Extract domain entities using targeted Indian legal regexes."""
    results: list[dict[str, Any]] = []
    seen = set()

    for entity_type, regex_list in PATTERNS.items():
        for regex in regex_list:
            for match in re.finditer(regex, text, re.IGNORECASE):
                val = match.group(1).strip()
                # Exclude noisy or trivial matches
                if len(val) < 2 or len(val) > 120:
                    continue
                if entity_type == "police_station":
                    val = val.title()
                key = (entity_type, val.lower())
                if key not in seen:
                    seen.add(key)
                    results.append(
                        {
                            "entity_type": entity_type,
                            "entity_value": val,
                            "confidence": 0.90,
                            "start_offset": match.start(1),
                            "end_offset": match.end(1),
                            "source": "regex_nlp",
                        }
                    )
    return results


def extract_entities_with_llm(text: str) -> list[dict[str, Any]]:
    """Use Gemini to extract semantic entities (person, organization, location)."""
    if not gemini_client.is_configured:
        return []

    prompt = f"""
You are an expert NLP system for Indian Police & Judiciary documents.
Extract named entities from the text below.
Only use these entity types:
- person (suspects, victims, witnesses, investigating officers, judges)
- organization (police stations, courts, forensic labs, hospitals, banks)
- location (crime scenes, addresses, cities, districts, states)
- law_section (IPC, CrPC, BNS, POCSO sections)
- fir_number
- case_number
- police_station
- evidence_ref (weapons, seized articles, digital exhibits)
- phone_number
- vehicle_number

Text (first 3000 chars):
\"\"\"
{text[:3000]}
\"\"\"

Return ONLY a JSON list of objects:
[
  {{"entity_type": "person", "entity_value": "Rajesh Kumar", "confidence": 0.95}},
  ...
]
"""
    raw = gemini_client.generate_text(
        prompt,
        system_instruction="Return strictly a valid JSON array of objects. Do not include markdown code block syntax if possible.",
    )
    if not raw:
        return []

    try:
        clean_json = raw
        if clean_json.startswith("```"):
            clean_json = re.sub(r"^```[a-zA-Z]*\n", "", clean_json)
            clean_json = re.sub(r"\n```$", "", clean_json)
        data = json.loads(clean_json.strip())
        if isinstance(data, list):
            valid_entities = []
            for item in data:
                etype = str(item.get("entity_type", "")).lower()
                evalue = str(item.get("entity_value", "")).strip()
                if etype in ENTITY_TYPES and evalue and len(evalue) > 1:
                    conf = float(item.get("confidence", 0.85))
                    # Find offset if present
                    start_off = text.find(evalue)
                    end_off = (start_off + len(evalue)) if start_off != -1 else None
                    valid_entities.append(
                        {
                            "entity_type": etype,
                            "entity_value": evalue,
                            "confidence": conf,
                            "start_offset": start_off if start_off != -1 else None,
                            "end_offset": end_off,
                            "source": "gemini_llm",
                        }
                    )
            return valid_entities
    except Exception as e:
        logger.warning(f"Failed to parse LLM entity response: {e}")

    return []


def extract_entities(text: str) -> list[dict[str, Any]]:
    """
    Combined entity extraction pipeline:
    1. Heuristic regex matcher for structured legal identifiers
    2. LLM / NLP matcher for named semantic entities
    3. Merged and deduplicated result
    """
    cleaned_text = text.strip()
    if not cleaned_text:
        return []

    # 1. Regex extractions
    regex_entities = extract_regex_entities(cleaned_text)

    # 2. LLM extractions
    llm_entities = extract_entities_with_llm(cleaned_text)

    # Combine with deduplication
    combined: list[dict[str, Any]] = []
    seen = set()

    for item in regex_entities + llm_entities:
        key = (item["entity_type"], item["entity_value"].lower())
        if key not in seen:
            seen.add(key)
            combined.append(item)

    return combined

