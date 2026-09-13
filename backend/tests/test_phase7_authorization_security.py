"""
Phase 7 Security Tests: Pre-Retrieval Authorization & Zero Cross-Case Data Leakage
Enforces IDOR / BOLA prevention (404), zero cross-case leakage in search and RAG,
and exclusion of compromised or unsearchable document versions.
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


@pytest.mark.asyncio
async def test_zero_cross_case_leakage_and_idor_defense(client: AsyncClient):
    """
    Validates:
    1. User A (in Case A) CANNOT search or ask about Case B (gets HTTP 404).
    2. User A cross-case search returns ZERO records from Case B.
    3. User B (in Case B) CAN search Case B.
    """
    # 1. Admin login and provision two distinct investigators
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ncrb.gov.in", "password": "Admin@DocShield2026!"},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    email_a = f"officer_a_{uuid4().hex[:6]}@ncrb.gov.in"
    email_b = f"officer_b_{uuid4().hex[:6]}@ncrb.gov.in"

    res_u1 = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "employee_id": f"EMP-A-{uuid4().hex[:4].upper()}",
            "email": email_a,
            "full_name": "Officer Alpha",
            "password": "Password123!",
            "role_name": "investigator",
        },
    )
    assert res_u1.status_code == 201

    res_u2 = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "employee_id": f"EMP-B-{uuid4().hex[:4].upper()}",
            "email": email_b,
            "full_name": "Officer Bravo",
            "password": "Password123!",
            "role_name": "investigator",
        },
    )
    assert res_u2.status_code == 201

    # Login both users
    login_a = await client.post("/api/v1/auth/login", json={"email": email_a, "password": "Password123!"})
    assert login_a.status_code == 200
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    login_b = await client.post("/api/v1/auth/login", json={"email": email_b, "password": "Password123!"})
    assert login_b.status_code == 200
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 2. Officer A creates Case A; Officer B creates Case B
    res_case_a = await client.post(
        "/api/v1/cases",
        headers=headers_a,
        json={
            "case_number": f"CASE-A-{uuid4().hex[:6].upper()}",
            "title": "Operation Alpha (Secret)",
            "priority": "critical",
            "fir_number": f"FIR-A-{uuid4().hex[:4].upper()}",
            "police_station": "Intelligence Unit A",
        },
    )
    assert res_case_a.status_code == 201
    case_a_id = res_case_a.json()["id"]

    res_case_b = await client.post(
        "/api/v1/cases",
        headers=headers_b,
        json={
            "case_number": f"CASE-B-{uuid4().hex[:6].upper()}",
            "title": "Operation Bravo (Top Secret)",
            "priority": "critical",
            "fir_number": f"FIR-B-{uuid4().hex[:4].upper()}",
            "police_station": "Intelligence Unit B",
        },
    )
    assert res_case_b.status_code == 201
    case_b_id = res_case_b.json()["id"]

    # 3. User A uploads Doc A to Case A
    doc_a_bytes = make_docx("Alpha witness statement: Target confessed to offshore account Alpha-9944.")
    res_doc_a = await client.post(
        f"/api/v1/cases/{case_a_id}/documents",
        headers=headers_a,
        data={"title": "Alpha Interrogation", "document_type": "witness_statement"},
        files={"file": ("alpha.docx", doc_a_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert res_doc_a.status_code == 201
    await client.post(f"/api/v1/documents/{res_doc_a.json()['id']}/ai/process", headers=headers_a)

    # 4. User B uploads Doc B to Case B
    doc_b_bytes = make_docx("Bravo secret informant code-named BLACKBIRD operates inside foreign embassy.")
    res_doc_b = await client.post(
        f"/api/v1/cases/{case_b_id}/documents",
        headers=headers_b,
        data={"title": "Bravo Informant Dossier", "document_type": "witness_statement"},
        files={"file": ("bravo.docx", doc_b_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert res_doc_b.status_code == 201
    await client.post(f"/api/v1/documents/{res_doc_b.json()['id']}/ai/process", headers=headers_b)

    # 5. IDOR Defense: User A attempts to search Case B directly -> 404
    resp_idor = await client.post(
        "/api/v1/search/semantic",
        json={"query": "BLACKBIRD foreign embassy", "case_id": case_b_id},
        headers=headers_a,
    )
    assert resp_idor.status_code == 404

    # User A attempts to ask RAG about Case B -> 404
    resp_idor_ask = await client.post(
        "/api/v1/search/ask",
        json={"question": "Who is BLACKBIRD?", "case_id": case_b_id},
        headers=headers_a,
    )
    assert resp_idor_ask.status_code == 404

    # 6. Zero Cross-Case Data Leakage: User A does a cross-case search (case_id=None)
    resp_cross_a = await client.post(
        "/api/v1/search/semantic",
        json={"query": "BLACKBIRD foreign embassy", "case_id": None, "min_similarity": 0.1},
        headers=headers_a,
    )
    assert resp_cross_a.status_code == 200
    for r in resp_cross_a.json()["results"]:
        assert str(r["case_id"]) != case_b_id
        assert "BLACKBIRD" not in r["chunk_text"]

    # In contrast, User B searching Case B DOES find BLACKBIRD
    resp_b = await client.post(
        "/api/v1/search/semantic",
        json={"query": "BLACKBIRD foreign embassy", "case_id": case_b_id, "min_similarity": 0.1},
        headers=headers_b,
    )
    assert resp_b.status_code == 200
    assert resp_b.json()["total_results"] >= 1
    assert "BLACKBIRD" in resp_b.json()["results"][0]["chunk_text"]

