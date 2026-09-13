"""
Cryptographic Custody Chain & Digital Integrity Verification Tests
Verifies hash chain generation, verification, simulated tamper detection, and S3 artifact integrity audits.
"""

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.database import AsyncSessionLocal

VALID_PDF_BYTES = b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


async def get_auth_token(client: AsyncClient, email: str, password: str) -> str:
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


async def get_user_id(client: AsyncClient, token: str) -> str:
    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    return res.json()["id"]


async def create_test_case(client: AsyncClient, token: str) -> dict:
    case_num = f"CASE-CHAIN-{uuid.uuid4().hex[:8].upper()}"
    res = await client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "case_number": case_num,
            "title": f"Chain Test Case {case_num}",
            "priority": "critical",
            "fir_number": f"FIR-{uuid.uuid4().hex[:6].upper()}",
            "police_station": "Crime Branch Special Cell",
        },
    )
    assert res.status_code == 201
    return res.json()


@pytest.mark.asyncio
async def test_custody_hash_chain_verification(client: AsyncClient):
    """
    Verifies that sequential custody events maintain mathematical hash-chain continuity:
    H_n = SHA256(canonical_event_data || H_(n-1)).
    """
    inv_token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    forensic_token = await get_auth_token(client, "forensic@ncrb.gov.in", "ForensicExpert@2026!")
    forensic_id = await get_user_id(client, forensic_token)

    case = await create_test_case(client, inv_token)
    case_id = case["id"]

    # Add forensic expert to case
    await client.post(
        f"/api/v1/cases/{case_id}/members",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={"user_id": forensic_id, "role_in_case": "forensic_analyst"},
    )

    # 1. Registration event (Genesis H_0)
    reg_res = await client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={"title": "Primary Server SSD", "evidence_type": "device"},
    )
    evidence_id = reg_res.json()["id"]

    # 2. Transfer initiation (Event 2)
    await client.post(
        f"/api/v1/evidence/{evidence_id}/custody/transfer",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={"to_user_id": forensic_id, "reason": "Hardware bitstream acquisition"},
    )

    # 3. Transfer acknowledgement (Event 3)
    await client.post(
        f"/api/v1/evidence/{evidence_id}/custody/acknowledge",
        headers={"Authorization": f"Bearer {forensic_token}"},
        json={"notes": "Received drive in electrostatic bag"},
    )

    # 4. Status change (Event 4)
    await client.post(
        f"/api/v1/evidence/{evidence_id}/status",
        headers={"Authorization": f"Bearer {forensic_token}"},
        json={"target_status": "in_analysis", "reason": "Mounting read-only forensic image"},
    )

    # 5. Verify Custody Chain
    verify_res = await client.get(
        f"/api/v1/evidence/{evidence_id}/custody/verify",
        headers={"Authorization": f"Bearer {inv_token}"},
    )
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["valid"] is True
    assert v_data["events_checked"] == 4
    assert v_data["first_invalid_event"] is None
    assert v_data["genesis_hash"] is not None
    assert v_data["tip_hash"] is not None


@pytest.mark.asyncio
async def test_custody_tampering_detection(client: AsyncClient):
    """
    Verifies that if an attacker tampers with a historical custody ledger record in PostgreSQL,
    verify_custody_chain immediately detects the corrupted link.
    """
    inv_token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    forensic_token = await get_auth_token(client, "forensic@ncrb.gov.in", "ForensicExpert@2026!")
    forensic_id = await get_user_id(client, forensic_token)

    case = await create_test_case(client, inv_token)
    case_id = case["id"]

    await client.post(
        f"/api/v1/cases/{case_id}/members",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={"user_id": forensic_id, "role_in_case": "forensic_analyst"},
    )

    # Register evidence and transfer
    reg = await client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={"title": "Encrypted Memory Card", "evidence_type": "device"},
    )
    evidence_id = reg.json()["id"]

    await client.post(
        f"/api/v1/evidence/{evidence_id}/custody/transfer",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={"to_user_id": forensic_id, "reason": "Flash chip dump"},
    )
    await client.post(
        f"/api/v1/evidence/{evidence_id}/custody/acknowledge",
        headers={"Authorization": f"Bearer {forensic_token}"},
        json={"notes": "Acknowledged"},
    )

    # Simulate direct PostgreSQL database tampering on historical event
    async with AsyncSessionLocal() as db_session:
        # Corrupt the reason text of the genesis event without updating the cryptographic hash
        await db_session.execute(
            text(
                "UPDATE evidence_custody_events SET reason = 'TAMPERED REASON HERE' "
                "WHERE evidence_id = :evidence_id AND event_type = 'registered'"
            ),
            {"evidence_id": evidence_id},
        )
        await db_session.commit()

    # Now verify chain -> Must detect tampering!
    verify_res = await client.get(
        f"/api/v1/evidence/{evidence_id}/custody/verify",
        headers={"Authorization": f"Bearer {inv_token}"},
    )
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["valid"] is False
    assert v_data["first_invalid_event"] is not None
    assert "tampering" in v_data["reason"].lower() or "mismatch" in v_data["reason"].lower()


@pytest.mark.asyncio
async def test_evidence_digital_integrity_verification(client: AsyncClient):
    """
    Verifies that digital evidence integrity checking detects modifications in S3/MinIO
    and raises an audit alert without overwriting the authoritative original hash.
    """
    token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    case = await create_test_case(client, token)
    case_id = case["id"]

    # Upload document
    doc_res = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("intercept.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")},
        data={"title": "Wiretap Intercept Transcript", "document_type": "supporting_document"},
    )
    assert doc_res.status_code == 201
    doc = doc_res.json()
    doc_id = doc["id"]
    original_hash = doc["file_hash_sha256"]

    # Register evidence linked to document
    ev_res = await client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Wiretap Audio & Transcript Evidence",
            "evidence_type": "digital_document",
            "document_id": doc_id,
        },
    )
    assert ev_res.status_code == 201
    evidence_id = ev_res.json()["id"]

    # 1. Initial live integrity verification -> Verified
    v1 = await client.get(
        f"/api/v1/evidence/{evidence_id}/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert v1.status_code == 200
    assert v1.json()["match"] is True
    assert v1.json()["integrity_status"] == "verified"

    # 2. Simulate object corruption in S3 / MinIO storage
    from app.modules.documents.dependencies import get_storage_service
    storage = get_storage_service()
    ver_obj = doc["current_version"]
    storage.upload(
        file_data=b"%PDF-1.5\nCORRUPTED_TAMPERED_BYTES",
        key=f"cases/{case_id}/documents/{doc_id}/versions/{ver_obj['id']}",
        bucket="sih190-documents",
    )

    # 3. Subsequent live integrity verification -> Compromised
    v2 = await client.get(
        f"/api/v1/evidence/{evidence_id}/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert v2.status_code == 200
    v2_data = v2.json()
    assert v2_data["match"] is False
    assert v2_data["integrity_status"] == "compromised"
    # Crucial: Authoritative original hash was NOT overwritten!
    assert v2_data["original_hash"] == original_hash
