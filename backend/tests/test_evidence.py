"""
Evidence Lifecycle & Access Control Integration Tests
Verifies evidence registration, document linkage, case-scoping (IDOR), and state machine guardrails.
"""

import io
import uuid

import pytest
from httpx import AsyncClient

VALID_PDF_BYTES = b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


async def get_auth_token(client: AsyncClient, email: str, password: str) -> str:
    """Helper to authenticate and retrieve access token."""
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


async def create_test_case(client: AsyncClient, token: str) -> dict:
    """Helper creating a test case with creator enrolled as lead investigator."""
    case_num = f"CASE-EVID-{uuid.uuid4().hex[:8].upper()}"
    res = await client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "case_number": case_num,
            "title": f"Evidence Test Case {case_num}",
            "priority": "critical",
            "fir_number": f"FIR-{uuid.uuid4().hex[:6].upper()}",
            "police_station": "Cyber Crime Special Cell",
        },
    )
    assert res.status_code == 201
    return res.json()


@pytest.mark.asyncio
async def test_evidence_registration_authorized(client: AsyncClient):
    """Verifies that an authorized case member can register physical and digital evidence."""
    token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    case = await create_test_case(client, token)
    case_id = case["id"]

    # 1. Register physical evidence (Device)
    res_phys = await client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Western Digital 2TB External Hard Disk",
            "description": "Seized from primary suspect residence during raid",
            "evidence_type": "device",
            "sensitivity_level": "confidential",
            "collection_location": "Sector 62, Noida, UP",
            "source": "Suspect Bedroom Desk",
            "notes": "Panchnama witness signatures recorded",
        },
    )
    assert res_phys.status_code == 201
    phys_data = res_phys.json()
    assert phys_data["evidence_number"].startswith("EVID-")
    assert phys_data["status"] == "in_custody"
    assert phys_data["current_custodian_id"] is not None
    assert phys_data["transfer_pending"] is False

    # 2. Upload document to case first
    doc_res = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("cctv_log.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")},
        data={"title": "CCTV Access Log", "document_type": "supporting_document"},
    )
    assert doc_res.status_code == 201
    doc_id = doc_res.json()["id"]
    doc_hash = doc_res.json()["file_hash_sha256"]

    # 3. Register digital evidence linked to document
    res_dig = await client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Server Access Logs (Digital)",
            "description": "Exported gateway traffic logs",
            "evidence_type": "digital_document",
            "document_id": doc_id,
            "sensitivity_level": "secret",
        },
    )
    assert res_dig.status_code == 201
    dig_data = res_dig.json()
    assert dig_data["original_file_hash"] == doc_hash
    assert dig_data["current_file_hash"] == doc_hash
    assert dig_data["integrity_status"] == "verified"


@pytest.mark.asyncio
async def test_evidence_registration_unauthorized(client: AsyncClient):
    """Verifies that non-members cannot register evidence into unauthorized cases (IDOR protection)."""
    inv_token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    other_token = await get_auth_token(client, "forensic@ncrb.gov.in", "ForensicExpert@2026!")

    # Investigator creates case
    case = await create_test_case(client, inv_token)
    case_id = case["id"]

    # Forensic expert (not added to case) attempts to register evidence
    res = await client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers={"Authorization": f"Bearer {other_token}"},
        json={
            "title": "Unauthorized Evidence Intake",
            "evidence_type": "physical_evidence",
        },
    )
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_evidence_listing_and_scoping(client: AsyncClient):
    """Verifies that evidence listing is strictly filtered by active case assignment."""
    inv_token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    other_token = await get_auth_token(client, "legal@ncrb.gov.in", "Legal@2026!")

    case = await create_test_case(client, inv_token)
    case_id = case["id"]

    # Register evidence
    await client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={"title": "Seized Mobile Phone", "evidence_type": "device"},
    )

    # 1. Investigator lists case evidence -> sees 1 item
    list_res = await client.get(
        f"/api/v1/cases/{case_id}/evidence",
        headers={"Authorization": f"Bearer {inv_token}"},
    )
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 2. Legal officer (not a member) attempts to list case evidence -> receives 404
    unauth_list = await client.get(
        f"/api/v1/cases/{case_id}/evidence",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert unauth_list.status_code == 404


@pytest.mark.asyncio
async def test_evidence_status_state_machine(client: AsyncClient):
    """Verifies that evidence lifecycle transitions strictly obey the legal state machine."""
    token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    case = await create_test_case(client, token)
    case_id = case["id"]

    # Register evidence (starts in_custody)
    res = await client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Blood Sample Vial", "evidence_type": "forensic_artifact"},
    )
    assert res.status_code == 201
    evidence_id = res.json()["id"]

    # 1. Invalid transition: in_custody -> archived (Must not bypass analysis/court)
    inv_trans = await client.post(
        f"/api/v1/evidence/{evidence_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_status": "archived", "reason": "Direct archival attempt"},
    )
    assert inv_trans.status_code in (400, 422)
    assert "illegal" in inv_trans.json()["detail"].lower() or "invalid" in inv_trans.json()["detail"].lower()

    # 2. Valid progression: in_custody -> in_analysis
    t1 = await client.post(
        f"/api/v1/evidence/{evidence_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_status": "in_analysis", "reason": "Forwarded for DNA profiling"},
    )
    assert t1.status_code == 200
    assert t1.json()["status"] == "in_analysis"

    # 3. Valid progression: in_analysis -> analyzed
    t2 = await client.post(
        f"/api/v1/evidence/{evidence_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_status": "analyzed", "reason": "DNA match profile generated"},
    )
    assert t2.status_code == 200
    assert t2.json()["status"] == "analyzed"

    # 4. Valid progression: analyzed -> submitted_to_court
    t3 = await client.post(
        f"/api/v1/evidence/{evidence_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_status": "submitted_to_court", "reason": "Exhibited before session court"},
    )
    assert t3.status_code == 200
    assert t3.json()["status"] == "submitted_to_court"

    # 5. Valid progression: submitted_to_court -> archived
    t4 = await client.post(
        f"/api/v1/evidence/{evidence_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_status": "archived", "reason": "Case trial completed"},
    )
    assert t4.status_code == 200
    assert t4.json()["status"] == "archived"
    assert t4.json()["archived_at"] is not None
