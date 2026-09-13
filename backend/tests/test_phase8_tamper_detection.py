"""
Phase 8 Tests: Tamper Detection, Incident Handling & Safe Demonstration
Validates live SHA-256 verification on download, refusal of compromised files,
audit logging, critical security alerts, and controlled tamper simulation.
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
    case_num = f"CASE-TMP8-{uuid4().hex[:8].upper()}"
    res = await client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "case_number": case_num,
            "title": f"Phase 8 Tamper Test {case_num}",
            "priority": "critical",
            "fir_number": f"FIR-{uuid4().hex[:6].upper()}",
            "police_station": "Anti-Corruption Bureau",
        },
    )
    assert res.status_code == 201
    return res.json()


@pytest.mark.asyncio
async def test_live_tamper_detection_and_download_refusal(client: AsyncClient):
    """
    1. Upload verified document.
    2. Verify download succeeds.
    3. Simulate tampering via /api/v1/security/simulate-tamper.
    4. Verify download is refused with INTEGRITY_FAILED.
    5. Verify document integrity check returns match=False.
    6. Verify pre-export check marks export as compromised.
    """
    token = await get_token(client)
    admin_token = await get_token(client, "admin@ncrb.gov.in", "Admin@DocShield2026!")
    headers = {"Authorization": f"Bearer {token}"}

    case = await create_case(client, token)
    case_id = case["id"]

    # 1. Upload valid document
    doc_bytes = make_docx("Official CBI forensic ballistic report on cartridge casings.")
    files = {"file": ("ballistic_report.docx", doc_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    upload_res = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=headers,
        data={
            "case_id": case_id,
            "title": "Ballistics Analysis Report",
            "document_type": "forensic_report",
            "classification": "confidential",
        },
        files=files,
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 2. Verify download works prior to tampering
    dl_res = await client.get(f"/api/v1/documents/{doc_id}/download", headers=headers)
    assert dl_res.status_code == 200
    assert len(dl_res.content) > 0

    # 3. Simulate tampering
    tamper_res = await client.post(
        "/api/v1/security/simulate-tamper",
        headers=headers,
        json={"target_type": "document", "target_id": doc_id},
    )
    assert tamper_res.status_code == 200
    tamper_data = tamper_res.json()
    assert tamper_data["target_id"] == doc_id
    assert tamper_data["previous_hash"] != tamper_data["tampered_payload_hash"]

    # 4. Attempt to download tampered document -> MUST BE REFUSED
    tampered_dl = await client.get(f"/api/v1/documents/{doc_id}/download", headers=headers)
    assert tampered_dl.status_code == 400
    err_json = tampered_dl.json()
    assert err_json.get("error_code") == "INTEGRITY_FAILED" or "integrity" in err_json.get("detail", "").lower()

    # 5. Live verification endpoint also flags compromised
    verify_res = await client.get(f"/api/v1/documents/{doc_id}/verify", headers=headers)
    assert verify_res.status_code == 200
    verify_data = verify_res.json()
    assert verify_data["match"] is False
    assert verify_data["integrity_status"] == "compromised"

    # 6. Admin can see the critical integrity security event
    sec_events_res = await client.get(
        f"/api/v1/security/events?category=INTEGRITY&case_id={case_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert sec_events_res.status_code == 200
    sec_events = sec_events_res.json()
    assert sec_events["total"] >= 1

    # 7. Generate export on tampered case -> export must flag compromised
    export_res = await client.post(
        f"/api/v1/cases/{case_id}/exports",
        headers=headers,
        json={"include_files": True},
    )
    assert export_res.status_code == 201
    exp_data = export_res.json()
    assert exp_data["integrity_status"] == "compromised"
    assert exp_data["verification_summary"]["all_verified"] is False
