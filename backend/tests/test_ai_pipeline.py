"""
Unit and Integration Tests for Stage 1 to Stage 7 AI Document Intelligence Pipeline.
Verifies text extraction, OCR fallback, classification, NER, summarization, chunking,
embeddings generation, and officer entity verification.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.modules.ai.chunking import split_text
from app.modules.ai.classification import classify_document
from app.modules.ai.embeddings import (
    generate_embeddings_for_chunks,
    generate_query_embedding,
)
from app.modules.ai.entity_extraction import extract_entities, extract_regex_entities
from app.modules.ai.ocr_service import is_tesseract_available, perform_ocr
from app.modules.ai.summarization import extract_metadata_entries, generate_summary
from app.modules.ai.text_extraction import extract_document_text, normalize_text


def test_text_normalization():
    raw = "Header \r\n\r\n Line 1   \x00\n\n\n\nLine 2   "
    clean = normalize_text(raw)
    assert "\x00" not in clean
    assert "\r" not in clean
    assert "Line 1" in clean
    assert "Line 2" in clean


def test_text_extraction_plaintext():
    content = b"FIRST INFORMATION REPORT\nUnder Section 302 IPC\nPolice Station Connaught Place"
    text, needs_ocr = extract_document_text(content, "fir_report.txt", "text/plain")
    assert "FIRST INFORMATION REPORT" in text
    assert needs_ocr is False


def test_ocr_service_graceful_fallback():
    # Calling OCR on dummy bytes should not crash even if tesseract is absent
    dummy_image = b"RIFF\x00\x00\x00\x00WEBPVP8 \x00\x00\x00\x00"
    res = perform_ocr(dummy_image, "image/png")
    assert isinstance(res.text, str)
    assert isinstance(res.success, bool)
    assert isinstance(is_tesseract_available(), bool)


def test_document_classification_heuristics():
    fir_text = """
    FIRST INFORMATION REPORT
    (Under Section 154 Cr.P.C.)
    1. District: Central, P.S.: Connaught Place, Year: 2024, FIR No.: 0142/2024
    2. Acts & Sections: Section 302 IPC, Section 34 IPC
    3. Complainant / Informant: Ramesh Sharma
    """
    res = classify_document(fir_text, "fir_0142.pdf")
    assert res.document_type == "fir"
    assert res.confidence >= 0.60
    assert "FIR" in res.reasoning or "fir" in res.reasoning

    cs_text = """
    FINAL REPORT / CHARGE-SHEET
    Under Section 173 Cr.P.C.
    In the Court of Learned Metropolitan Magistrate, Delhi.
    Accused persons sent for trial under Section 420 IPC, 120B IPC.
    List of prosecution witnesses: 1. Inspector Anil Kumar...
    """
    res_cs = classify_document(cs_text, "charge_sheet_draft.docx")
    assert res_cs.document_type == "charge_sheet"
    assert res_cs.confidence >= 0.60

    generic_text = "This is a brief memo regarding inventory office stationery."
    res_gen = classify_document(generic_text, "office_memo.txt")
    assert res_gen.document_type == "other"


def test_indian_legal_entity_extraction():
    legal_text = """
    FIR No. 421/2024 dated 14/08/2024 registered at Police Station Connaught Place, New Delhi.
    Case Number Crl.A 982/2023 pending before Sessions Court.
    The accused was booked under Section 302 IPC read with Section 120B IPC and Section 25 Arms Act.
    Vehicle DL 01 AB 9988 and phone number 9876543210 were recovered as Exhibit 4.
    """
    entities = extract_regex_entities(legal_text)
    types_found = {e["entity_type"] for e in entities}
    values_found = {e["entity_value"] for e in entities}

    assert "fir_number" in types_found
    assert "law_section" in types_found
    assert "phone_number" in types_found
    assert "vehicle_number" in types_found
    assert "police_station" in types_found

    assert "9876543210" in values_found
    assert "DL 01 AB 9988" in values_found

    combined = extract_entities(legal_text)
    assert len(combined) >= 4


def test_summarization_and_metadata():
    text = (
        "FIRST INFORMATION REPORT under Section 154 CrPC at Police Station Karol Bagh. "
        "The informant reported that on 12/05/2024, the accused broke into the warehouse and stole copper coils. "
        "Case registered under Section 379 IPC. The investigating officer visited the spot, prepared the site map, "
        "and seized fingerprint samples as Exhibit A. Investigation is currently in progress."
    )
    summary = generate_summary(text, "fir")
    assert len(summary) > 30
    assert "Karol Bagh" in summary or "Section" in summary or "informant" in summary

    entities = extract_entities(text)
    metadata = extract_metadata_entries(text, "fir", entities, ocr_applied=False)
    keys = {m["key"] for m in metadata}
    assert "document_classification" in keys
    assert "word_count" in keys
    assert "ocr_processed" in keys


def test_chunking_recursive_splitter():
    text = "Paragraph 1 sentence one. Sentence two.\n\nParagraph 2 sentence three. Sentence four.\n\nParagraph 3."
    chunks = split_text(text, chunk_size=40, chunk_overlap=10)
    assert len(chunks) >= 2
    assert all(len(c) > 0 for c in chunks)


def test_embeddings_generation():
    chunks = [
        "First Information Report against suspect at Police Station.",
        "Forensic Ballistics report confirming 9mm cartridge match.",
    ]
    embs = generate_embeddings_for_chunks(chunks)
    assert len(embs) == 2
    assert len(embs[0]) == 768
    assert len(embs[1]) == 768

    q_emb = generate_query_embedding("suspect ballistics match")
    assert len(q_emb) == 768


async def get_auth_token(client: AsyncClient, email: str, password: str) -> str:
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


async def create_test_case(client: AsyncClient, token: str) -> dict:
    case_num = f"CASE-AI-{uuid4().hex[:8].upper()}"
    res = await client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "case_number": case_num,
            "title": f"AI Intelligence Case {case_num}",
            "priority": "high",
            "fir_number": f"FIR-{uuid4().hex[:6].upper()}",
            "police_station": "Special Cell New Delhi",
        },
    )
    assert res.status_code == 201
    return res.json()


def make_docx_bytes(text: str) -> bytes:
    import io

    import docx

    doc = docx.Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_api_document_ai_insights_lifecycle(client: AsyncClient):
    """
    Test uploading a legal document, running the 7-stage AI pipeline,
    retrieving AI insights, and verifying an entity.
    """
    investigator_token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    case = await create_test_case(client, investigator_token)
    case_id = case["id"]
    headers = {"Authorization": f"Bearer {investigator_token}"}

    # 1. Upload a legal document
    file_text = (
        "FIRST INFORMATION REPORT\n"
        "Under Section 154 Cr.P.C.\n"
        "FIR No. 555/2024 at Police Station Mandir Marg.\n"
        "Offence: Section 420 IPC, 406 IPC.\n"
        "Accused Suresh Kumar received Rs 50,00,000 by fraudulent misrepresentation."
    )
    docx_bytes = make_docx_bytes(file_text)

    upload_res = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=headers,
        data={
            "title": "FIR 555 - Mandir Marg",
            "document_type": "fir",
            "description": "Original FIR for fraud investigation",
            "classification": "confidential",
        },
        files={
            "file": (
                "fir_555.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        },
    )
    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    doc_id = doc_data["id"]

    # 2. Trigger AI Pipeline
    process_res = await client.post(
        f"/api/v1/documents/{doc_id}/ai/process",
        headers=headers,
    )
    assert process_res.status_code == 200
    ai_data = process_res.json()
    assert ai_data["ai_processed"] is True
    assert ai_data["ai_classification"] == "fir"
    assert ai_data["ai_confidence"] is not None
    assert len(ai_data["summary"]) > 20
    assert len(ai_data["entities"]) > 0
    assert ai_data["chunk_count"] >= 1

    # 3. Retrieve AI Insights
    get_res = await client.get(
        f"/api/v1/documents/{doc_id}/ai",
        headers=headers,
    )
    assert get_res.status_code == 200
    insights = get_res.json()
    assert insights["document_id"] == doc_id
    assert insights["ai_processed"] is True
    assert len(insights["entities"]) > 0

    # 4. Verify an extracted entity (human-in-the-loop)
    entity_to_verify = insights["entities"][0]
    verify_res = await client.patch(
        f"/api/v1/documents/{doc_id}/entities/{entity_to_verify['id']}/verify",
        headers=headers,
        json={"verified": True},
    )
    assert verify_res.status_code == 200
    verified_data = verify_res.json()
    assert verified_data["verified"] is True
