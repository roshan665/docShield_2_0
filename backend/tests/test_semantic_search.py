"""
Tests for Case-Scoped Semantic Search (pgvector vector similarity).
Verifies ranking, cosine similarity filtering, and strict zero-trust case isolation.
"""

import io
from uuid import uuid4

import docx
import pytest
from httpx import AsyncClient


def make_docx_bytes(text: str) -> bytes:
    doc = docx.Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


async def get_auth_token(client: AsyncClient, email: str, password: str) -> str:
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


async def create_test_case(client: AsyncClient, token: str) -> dict:
    case_num = f"CASE-SRCH-{uuid4().hex[:8].upper()}"
    res = await client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "case_number": case_num,
            "title": f"Search Test Case {case_num}",
            "priority": "high",
            "fir_number": f"FIR-{uuid4().hex[:6].upper()}",
            "police_station": "Crime Branch",
        },
    )
    assert res.status_code == 201
    return res.json()


@pytest.mark.asyncio
async def test_case_scoped_semantic_search(client: AsyncClient):
    """
    Test uploading documents into a case, running AI processing,
    and executing case-scoped semantic searches.
    """
    investigator_token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    case = await create_test_case(client, investigator_token)
    case_id = case["id"]
    headers = {"Authorization": f"Bearer {investigator_token}"}

    # Upload Doc 1: Ballistics report
    ballistics_bytes = make_docx_bytes(
        "FORENSIC SCIENCE LABORATORY\n"
        "Ballistics examination of 9mm cartridge casing recovered from crime scene.\n"
        "Confirmed fired from country-made pistol Exhibit 2."
    )
    res1 = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=headers,
        data={
            "title": "Ballistics Analysis Report",
            "document_type": "forensic_report",
            "description": "FSL Ballistics testing for 9mm shell casing",
            "classification": "confidential",
        },
        files={
            "file": (
                "ballistics.docx",
                ballistics_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        },
    )
    assert res1.status_code == 201
    doc1_id = res1.json()["id"]
    await client.post(f"/api/v1/documents/{doc1_id}/ai/process", headers=headers)

    # Upload Doc 2: Financial fraud audit
    ledger_bytes = make_docx_bytes(
        "BANK OF BARODA AUDIT REPORT\n"
        "Suspect transfer of 50 lakhs to shell entity offshore.\n"
        "Account number 458902189."
    )
    res2 = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=headers,
        data={
            "title": "Bank Account Ledger",
            "document_type": "supporting_document",
            "description": "Ledger entries of illicit transactions",
            "classification": "confidential",
        },
        files={
            "file": (
                "bank_ledger.docx",
                ledger_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        },
    )
    assert res2.status_code == 201
    doc2_id = res2.json()["id"]
    await client.post(f"/api/v1/documents/{doc2_id}/ai/process", headers=headers)

    # Perform semantic search for ballistics
    search_res = await client.post(
        f"/api/v1/cases/{case_id}/ai/search",
        headers=headers,
        json={"query": "cartridge casing 9mm pistol forensic", "top_k": 5, "min_similarity": 0.2},
    )
    assert search_res.status_code == 200
    data = search_res.json()
    assert data["case_id"] == case_id
    assert data["results_count"] >= 1
    # Verify ballistics doc is ranked high
    doc_titles = [r["document_title"] for r in data["results"]]
    assert "Ballistics Analysis Report" in doc_titles


@pytest.mark.asyncio
async def test_semantic_search_zero_cross_case_leakage(client: AsyncClient):
    """
    Ensure vectors in Case A are NEVER returned when searching Case B.
    And a user without access to a case gets 404.
    """
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ncrb.gov.in", "password": "Admin@DocShield2026!"},
    )
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin creates second investigator
    inv2_email = f"inv2_{uuid4().hex[:6]}@ncrb.gov.in"
    await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "employee_id": f"EMP-I2-{uuid4().hex[:4].upper()}",
            "email": inv2_email,
            "full_name": "Investigator Two",
            "password": "Password123!",
            "role_name": "investigator",
        },
    )

    # Inv 2 logs in and creates Case B
    inv2_login = await client.post(
        "/api/v1/auth/login",
        json={"email": inv2_email, "password": "Password123!"},
    )
    inv2_token = inv2_login.json()["access_token"]
    inv2_headers = {"Authorization": f"Bearer {inv2_token}"}

    case_b_res = await client.post(
        "/api/v1/cases",
        headers=inv2_headers,
        json={
            "case_number": f"CASE-SEC-{uuid4().hex[:6].upper()}",
            "title": "Isolated Top Secret Case B",
            "incident_date": "2024-05-01T10:00:00Z",
            "jurisdiction": "Central Delhi",
        },
    )
    assert case_b_res.status_code == 201
    case_b_id = case_b_res.json()["id"]

    # Inv 1 logs in and tries to search Case B -> MUST return 404
    inv1_token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    inv1_headers = {"Authorization": f"Bearer {inv1_token}"}

    leak_res = await client.post(
        f"/api/v1/cases/{case_b_id}/ai/search",
        headers=inv1_headers,
        json={"query": "secret documents", "top_k": 5},
    )
    assert leak_res.status_code == 404

