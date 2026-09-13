"""
Phase 8 End-to-End Evidence Lifecycle Test
Validates the complete flow from authentication, case creation, document processing,
evidence chain of custody, semantic retrieval, legal court export, and security monitoring.
"""

import io
from datetime import UTC, datetime
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


async def get_token(client: AsyncClient, email: str, pwd: str) -> str:
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_complete_e2e_evidence_lifecycle(client: AsyncClient):
    """
    Complete SIH evaluation flow:
    1. Investigator logins and creates case.
    2. Adds Forensic Expert to case.
    3. Uploads FIR/depository document.
    4. Registers evidence article linked to document.
    5. Transfers custody to Forensic Expert.
    6. Forensic Expert acknowledges custody.
    7. Searches document via semantic vector search.
    8. Generates court-ready export with manifest.
    9. Simulates storage tampering on document.
    10. Verifies download refusal on tampered file.
    11. Admin verifies security monitoring dashboard metrics and alert.
    """
    # 1. Investigator Login
    inv_token = await get_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    inv_headers = {"Authorization": f"Bearer {inv_token}"}

    # 2. Create Case
    case_num = f"CASE-E2E-{uuid4().hex[:8].upper()}"
    case_res = await client.post(
        "/api/v1/cases",
        headers=inv_headers,
        json={
            "case_number": case_num,
            "title": f"SIH Grand Finale Case {case_num}",
            "priority": "critical",
            "fir_number": f"FIR-{uuid4().hex[:6].upper()}",
            "police_station": "Special Cell New Delhi",
        },
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # 3. Add Forensic Expert to Case
    for_token = await get_token(client, "forensic@ncrb.gov.in", "ForensicExpert@2026!")
    for_headers = {"Authorization": f"Bearer {for_token}"}
    me_res = await client.get("/api/v1/auth/me", headers=for_headers)
    for_user_id = me_res.json()["id"]

    add_member_res = await client.post(
        f"/api/v1/cases/{case_id}/members",
        headers=inv_headers,
        json={"user_id": for_user_id, "role_in_case": "forensic_analyst", "added_at": datetime.now(UTC).isoformat()},
    )
    assert add_member_res.status_code in [200, 201]

    # 4. Upload Document
    doc_bytes = make_docx("FIRST INFORMATION REPORT: Unidentified vehicle DL-01-A-9999 seized with encrypted hard drive.")
    files = {"file": ("fir_record.docx", doc_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    doc_res = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=inv_headers,
        data={
            "case_id": case_id,
            "title": "Primary FIR Document",
            "document_type": "fir",
            "classification": "confidential",
        },
        files=files,
    )
    assert doc_res.status_code == 201
    doc_id = doc_res.json()["id"]

    # 5. Register Evidence
    ev_res = await client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers=inv_headers,
        json={
            "title": "Western Digital 2TB Hard Drive",
            "evidence_type": "digital_document",
            "document_id": doc_id,
            "sensitivity_level": "confidential",
            "notes": "Recovered from glove compartment",
        },
    )
    assert ev_res.status_code == 201
    ev_id = ev_res.json()["id"]

    # 6. Transfer Custody to Forensic Expert
    transfer_res = await client.post(
        f"/api/v1/evidence/{ev_id}/custody/transfer",
        headers=inv_headers,
        json={
            "to_user_id": for_user_id,
            "reason": "Detailed forensic partition extraction and analysis",
            "location": "Central Forensic Science Laboratory (CFSL)",
        },
    )
    assert transfer_res.status_code == 200

    # 7. Forensic Expert Acknowledges Custody
    ack_res = await client.post(
        f"/api/v1/evidence/{ev_id}/custody/acknowledge",
        headers=for_headers,
        json={"notes": "Received in tamper-evident sealed forensic anti-static bag"},
    )
    assert ack_res.status_code == 200
    assert ack_res.json()["current_custodian_id"] == for_user_id

    # 8. Semantic Search on Authorized Case
    search_res = await client.post(
        "/api/v1/search/semantic",
        headers=inv_headers,
        json={"query": "encrypted hard drive partition", "case_id": case_id},
    )
    assert search_res.status_code == 200

    # 9. Generate Court-Ready Export
    export_res = await client.post(
        f"/api/v1/cases/{case_id}/exports",
        headers=inv_headers,
        json={"include_files": True, "reason": "High Court of Delhi Production"},
    )
    assert export_res.status_code == 201
    exp_id = export_res.json()["id"]

    # Download Export ZIP
    dl_exp = await client.get(f"/api/v1/cases/{case_id}/exports/{exp_id}/download", headers=inv_headers)
    assert dl_exp.status_code == 200

    # 10. Simulate Tamper
    tamper_res = await client.post(
        "/api/v1/security/simulate-tamper",
        headers=inv_headers,
        json={"target_type": "document", "target_id": doc_id},
    )
    assert tamper_res.status_code == 200

    # 11. Download Refusal on Tampered Document
    bad_dl = await client.get(f"/api/v1/documents/{doc_id}/download", headers=inv_headers)
    assert bad_dl.status_code == 400

    # 12. Admin Security Dashboard Visibility
    admin_token = await get_token(client, "admin@ncrb.gov.in", "Admin@DocShield2026!")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    metrics_res = await client.get("/api/v1/security/metrics", headers=admin_headers)
    assert metrics_res.status_code == 200
    metrics = metrics_res.json()
    assert metrics["integrity_violations"] >= 1
    assert metrics["critical_events"] >= 1
