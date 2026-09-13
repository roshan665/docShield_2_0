"""
Phase 7 Tests: Semantic, Keyword, and Hybrid Search
Validates authorization-aware search, Reciprocal Rank Fusion, thresholding, and index status.
"""

import io
from uuid import uuid4

import docx
import pytest
from httpx import AsyncClient


def make_docx(text: str) -> bytes:
    doc = docx.Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


async def get_token(client: AsyncClient, email: str = "officer@ncrb.gov.in", pwd: str = "Investigator@2026!") -> str:
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    assert res.status_code == 200
    return res.json()["access_token"]


async def create_case(client: AsyncClient, token: str) -> dict:
    case_num = f"CASE-SRCH7-{uuid4().hex[:8].upper()}"
    res = await client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "case_number": case_num,
            "title": f"Phase 7 Search Test {case_num}",
            "priority": "high",
            "fir_number": f"FIR-{uuid4().hex[:6].upper()}",
            "police_station": "Financial Crimes Cell",
        },
    )
    assert res.status_code == 201
    return res.json()


@pytest.mark.asyncio
async def test_semantic_search_endpoints_and_status(client: AsyncClient):
    """
    Verifies /api/v1/search/semantic, /api/v1/search/keyword, /api/v1/search/hybrid,
    and /api/v1/search/status with case membership authorization.
    """
    token = await get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    case = await create_case(client, token)
    case_id = case["id"]

    # Upload document
    doc_bytes = make_docx(
        "SECURITIES AND EXCHANGE BOARD OF INDIA AUDIT\n"
        "Forensic analysis detected shell company accounts routing funds through Mumbai bank branch.\n"
        "Server logs reveal unauthorized database dump initiated from IP 192.168.1.105 on March 14."
    )
    res_upload = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=headers,
        data={
            "title": "Forensic Audit Report",
            "document_type": "forensic_report",
            "description": "Analysis of fraudulent securities transactions",
            "classification": "confidential",
        },
        files={
            "file": (
                "audit.docx",
                doc_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        },
    )
    assert res_upload.status_code == 201
    doc_id = res_upload.json()["id"]

    # Run AI pipeline
    res_ai = await client.post(f"/api/v1/documents/{doc_id}/ai/process", headers=headers)
    assert res_ai.status_code == 200

    # 1. Test Semantic Search scoped to case_id
    semantic_payload = {
        "query": "shell company accounts Mumbai bank funds",
        "case_id": case_id,
        "top_k": 5,
        "min_similarity": 0.2,
    }
    resp = await client.post("/api/v1/search/semantic", json=semantic_payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["search_type"] == "semantic"
    assert data["total_results"] >= 1
    top_hit = data["results"][0]
    assert top_hit["chunk_id"].startswith("DOC-")
    assert "Mumbai" in top_hit["chunk_text"] or "shell" in top_hit["chunk_text"]

    # 2. Test Keyword Search
    kw_payload = {
        "query": "database dump",
        "case_id": case_id,
        "top_k": 5,
    }
    resp_kw = await client.post("/api/v1/search/keyword", json=kw_payload, headers=headers)
    assert resp_kw.status_code == 200
    kw_data = resp_kw.json()
    assert kw_data["search_type"] == "keyword"
    assert kw_data["total_results"] >= 1
    assert any("database dump" in r["chunk_text"].lower() for r in kw_data["results"])

    # 3. Test Hybrid Search (RRF)
    hybrid_payload = {
        "query": "unauthorized server logs dump",
        "case_id": case_id,
        "top_k": 5,
        "alpha": 0.7,
    }
    resp_hybrid = await client.post("/api/v1/search/hybrid", json=hybrid_payload, headers=headers)
    assert resp_hybrid.status_code == 200
    hybrid_data = resp_hybrid.json()
    assert hybrid_data["search_type"] == "hybrid"
    assert hybrid_data["total_results"] >= 1
    assert "rrf_score" in hybrid_data["results"][0]

    # 4. Test Cross-Case Search (case_id=None)
    cross_payload = {
        "query": "forensic analysis",
        "case_id": None,
        "top_k": 10,
        "min_similarity": 0.2,
    }
    resp_cross = await client.post("/api/v1/search/semantic", json=cross_payload, headers=headers)
    assert resp_cross.status_code == 200
    assert resp_cross.json()["total_results"] >= 1

    # 5. Test Search Status
    resp_status = await client.get("/api/v1/search/status", headers=headers)
    assert resp_status.status_code == 200
    status_data = resp_status.json()
    assert status_data["total_embeddings"] >= 1
    assert status_data["searchable_embeddings"] >= 1
    assert status_data["indexed_documents_count"] >= 1
    assert status_data["vector_dimensions"] == 768
