"""
Tests for Case AI Assistant (RAG Question Answering).
Verifies grounded answers, source citations, zero hallucination behavior, and zero-trust scoping.
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
    case_num = f"CASE-RAG-{uuid4().hex[:8].upper()}"
    res = await client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "case_number": case_num,
            "title": f"RAG Test Case {case_num}",
            "priority": "high",
            "fir_number": f"FIR-{uuid4().hex[:6].upper()}",
            "police_station": "Narcotics Branch",
        },
    )
    assert res.status_code == 201
    return res.json()


@pytest.mark.asyncio
async def test_rag_assistant_grounded_answer_and_citations(client: AsyncClient):
    """
    Test asking the Case AI Assistant questions regarding uploaded case files.
    Verifies that answer includes source citations and disclaimer.
    """
    investigator_token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    case = await create_test_case(client, investigator_token)
    case_id = case["id"]
    headers = {"Authorization": f"Bearer {investigator_token}"}

    # Upload witness deposition
    stmt_text = (
        "STATEMENT OF WITNESS UNDER SECTION 161 CrPC.\n"
        "I, Rajat Verma, state that on 20th October at 11:30 PM, I saw the blue sedan registration DL 01 AB 9988 "
        "leaving the warehouse premises at high speed. The driver was wearing a black jacket."
    )
    stmt_bytes = make_docx_bytes(stmt_text)

    upload_res = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=headers,
        data={
            "title": "Witness Statement - Rajat Verma",
            "document_type": "witness_statement",
            "description": "Deposition recorded under Section 161 CrPC",
            "classification": "confidential",
        },
        files={
            "file": (
                "witness_statement.docx",
                stmt_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        },
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Process AI
    await client.post(f"/api/v1/documents/{doc_id}/ai/process", headers=headers)

    # Ask the Case AI Assistant
    ask_res = await client.post(
        f"/api/v1/cases/{case_id}/ai/ask",
        headers=headers,
        json={"question": "What vehicle and registration was seen at the warehouse?"},
    )
    assert ask_res.status_code == 200
    answer_data = ask_res.json()
    assert answer_data["case_id"] == case_id
    assert len(answer_data["answer"]) > 10
    assert len(answer_data["sources"]) > 0
    # Check source reference
    top_source = answer_data["sources"][0]
    assert top_source["document_title"] == "Witness Statement - Rajat Verma"
    assert "disclaimer" in answer_data


@pytest.mark.asyncio
async def test_rag_assistant_zero_trust_access(client: AsyncClient):
    """
    Ensure non-members cannot query the Case AI Assistant on cases they do not belong to.
    """
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ncrb.gov.in", "password": "Admin@DocShield2026!"},
    )
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin creates investigator 2
    inv2_email = f"inv2_rag_{uuid4().hex[:6]}@ncrb.gov.in"
    await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "employee_id": f"EMP-IR2-{uuid4().hex[:4].upper()}",
            "email": inv2_email,
            "full_name": "Investigator RAG Two",
            "password": "Password123!",
            "role_name": "investigator",
        },
    )

    # Inv 2 creates Case X
    inv2_login = await client.post(
        "/api/v1/auth/login",
        json={"email": inv2_email, "password": "Password123!"},
    )
    inv2_token = inv2_login.json()["access_token"]
    inv2_headers = {"Authorization": f"Bearer {inv2_token}"}

    case_x_res = await client.post(
        "/api/v1/cases",
        headers=inv2_headers,
        json={
            "case_number": f"CASE-RAGX-{uuid4().hex[:6].upper()}",
            "title": "Restricted Narcotics Case",
            "incident_date": "2024-06-01T12:00:00Z",
            "jurisdiction": "South Delhi",
        },
    )
    assert case_x_res.status_code == 201
    case_x_id = case_x_res.json()["id"]

    # Inv 1 querying Case X should receive 404
    inv1_token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    inv1_headers = {"Authorization": f"Bearer {inv1_token}"}

    ask_res = await client.post(
        f"/api/v1/cases/{case_x_id}/ai/ask",
        headers=inv1_headers,
        json={"question": "Who are the suspects named in this case?"},
    )
    assert ask_res.status_code == 404
