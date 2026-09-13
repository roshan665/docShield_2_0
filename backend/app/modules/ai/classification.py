"""
Legal Document Classification Service
Stage 3 in the AI Document Intelligence Pipeline.
Categorizes documents into Indian legal taxonomy with confidence scores.
"""

import json
import logging
import re

from app.modules.ai.gemini_client import gemini_client
from app.schemas.ai import ClassificationResult

logger = logging.getLogger(__name__)

LEGAL_CATEGORIES = {
    "fir": [
        r"first information report",
        r"\bf\.?i\.?r\.?\b",
        r"section 154 cr\.?p\.?c",
        r"police station",
        r"u/s\s+\d+",
        r"complainant / informant",
    ],
    "charge_sheet": [
        r"charge[\s-]?sheet",
        r"final report",
        r"section 173 cr\.?p\.?c",
        r"accused persons sent for trial",
        r"list of prosecution witnesses",
    ],
    "police_report": [
        r"police report",
        r"investigation report",
        r"case diary",
        r"special report",
        r"superintendent of police",
    ],
    "forensic_report": [
        r"forensic science laboratory",
        r"\bfsl\b",
        r"chemical examination",
        r"ballistics",
        r"dna analysis",
        r"digital forensics",
        r"forensic analysis report",
    ],
    "medical_report": [
        r"post[\s-]?mortem",
        r"autopsy",
        r"medico[\s-]?legal",
        r"injury report",
        r"hospital",
        r"medical officer",
        r"cause of death",
    ],
    "witness_statement": [
        r"statement of witness",
        r"section 161 cr\.?p\.?c",
        r"section 164 cr\.?p\.?c",
        r"statement under",
        r"deponent",
        r"solemnly affirm",
    ],
    "court_order": [
        r"in the court of",
        r"order sheet",
        r"learned magistrate",
        r"sessions judge",
        r"high court",
        r"supreme court",
        r"it is ordered",
    ],
    "bail_application": [
        r"bail application",
        r"anticipatory bail",
        r"section 437 cr\.?p\.?c",
        r"section 438 cr\.?p\.?c",
        r"section 439 cr\.?p\.?c",
        r"applicant / accused",
        r"grant of bail",
    ],
    "panchnama": [
        r"panchnama",
        r"panchas",
        r"panch witnesses",
        r"spot inspection",
        r"recovery panchnama",
    ],
    "seizure_memo": [
        r"seizure memo",
        r"seizure list",
        r"articles seized",
        r"confiscation",
        r"malkhana",
        r"recovered from the possession",
    ],
}


def classify_document(text: str, filename: str = "") -> ClassificationResult:
    """
    Classifies legal document text using Google Gemini or deterministic legal heuristic matching.
    """
    cleaned_text = text.strip()
    if not cleaned_text:
        return ClassificationResult(
            document_type="other",
            confidence=0.1,
            reasoning="Empty or unreadable document content.",
        )

    # First attempt LLM classification if Gemini is configured
    if gemini_client.is_configured:
        prompt = f"""
You are an expert Indian legal document classifier for the National Crime Records Bureau.
Classify the following document excerpt into exactly one of these categories:
- fir (First Information Report)
- police_report (General Police/Investigation Report)
- charge_sheet (Final Report under CrPC/BNSS)
- forensic_report (FSL / Digital Forensics / Ballistics)
- medical_report (Post Mortem / Medico-legal / Injury)
- witness_statement (Section 161/164 statement)
- court_order (Judicial / Magistrate / Court Order)
- bail_application (Bail Application under 437/438/439 CrPC)
- panchnama (Spot or Recovery Panchnama)
- seizure_memo (Property Seizure Memo / List)
- other (Generic legal or administrative record)

Filename: {filename}
Document Text (first 2000 chars):
\"\"\"
{cleaned_text[:2000]}
\"\"\"

Respond with ONLY valid JSON with keys:
"document_type": string,
"confidence": float (0.0 to 1.0),
"reasoning": string (brief 1-sentence justification)
"""
        raw_response = gemini_client.generate_text(
            prompt,
            system_instruction="Return strictly valid JSON only. Do not wrap in markdown quotes if possible.",
        )
        if raw_response:
            try:
                # Strip markdown codeblocks if present
                clean_json = raw_response
                if clean_json.startswith("```"):
                    clean_json = re.sub(r"^```[a-zA-Z]*\n", "", clean_json)
                    clean_json = re.sub(r"\n```$", "", clean_json)
                data = json.loads(clean_json.strip())
                doc_type = str(data.get("document_type", "other")).lower()
                if doc_type in LEGAL_CATEGORIES or doc_type == "other":
                    return ClassificationResult(
                        document_type=doc_type,
                        confidence=float(data.get("confidence", 0.85)),
                        reasoning=str(data.get("reasoning", "Classified via Google Gemini 2.5")),
                    )
            except Exception as e:
                logger.warning(f"Failed to parse LLM classification response: {e}")

    # Fallback / Deterministic heuristic pattern matching
    sample = f"{filename.lower()}\n{cleaned_text[:3000].lower()}"
    scores: dict[str, int] = {}

    for category, patterns in LEGAL_CATEGORIES.items():
        score = 0
        for pattern in patterns:
            matches = len(re.findall(pattern, sample))
            score += matches * 2
        if score > 0:
            scores[category] = score

    if not scores:
        return ClassificationResult(
            document_type="other",
            confidence=0.5,
            reasoning="No dominant legal pattern detected; classified as general legal document.",
        )

    best_category = max(scores, key=scores.get)
    max_score = scores[best_category]
    # Compute confidence based on score strength
    confidence = min(0.95, round(0.60 + (max_score * 0.05), 2))

    return ClassificationResult(
        document_type=best_category,
        confidence=confidence,
        reasoning=f"Matched Indian legal indicators for {best_category} with score {max_score}.",
    )

