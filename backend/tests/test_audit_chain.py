"""
Tests for Append-Only Audit Trail, Hash Chain, and Cryptographic Verification
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.database import AsyncSessionLocal


@pytest.mark.asyncio
async def test_audit_trail_and_chain_verification(client: AsyncClient):
    # 1. Login as Admin
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ncrb.gov.in", "password": "Admin@DocShield2026!"},
    )
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Verify initial chain is valid
    verify_resp = await client.get("/api/v1/admin/audit/verify", headers=admin_headers)
    assert verify_resp.status_code == 200
    assert verify_resp.json()["valid"] is True

    # 2. Login as Investigator and create a case to generate audit events
    inv_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "officer@ncrb.gov.in", "password": "Investigator@2026!"},
    )
    inv_token = inv_login.json()["access_token"]
    inv_headers = {"Authorization": f"Bearer {inv_token}"}

    case_num = f"CR-AUDIT-{uuid.uuid4().hex[:6].upper()}"
    case_resp = await client.post(
        "/api/v1/cases",
        headers=inv_headers,
        json={"case_number": case_num, "title": "Audit Chain Test Case"},
    )
    assert case_resp.status_code == 201
    case_id = case_resp.json()["id"]

    # 3. Update case status to generate another audit event
    update_resp = await client.patch(
        f"/api/v1/cases/{case_id}",
        headers=inv_headers,
        json={"status": "under_investigation"},
    )
    assert update_resp.status_code == 200

    # 4. Verify case timeline returns chronological events
    timeline_resp = await client.get(f"/api/v1/cases/{case_id}/timeline", headers=inv_headers)
    assert timeline_resp.status_code == 200
    timeline = timeline_resp.json()
    assert len(timeline) >= 2
    actions = [t["action"] for t in timeline]
    assert "CASE_CREATED" in actions
    assert "CASE_STATUS_CHANGED" in actions

    # 5. Cryptographically verify the audit hash chain
    verify_after = await client.get("/api/v1/admin/audit/verify", headers=admin_headers)
    assert verify_after.status_code == 200
    res_data = verify_after.json()
    assert res_data["valid"] is True
    assert res_data["events_checked"] >= 2
    assert res_data["first_invalid_event"] is None


@pytest.mark.asyncio
async def test_audit_tampering_detection(client: AsyncClient):
    """
    Simulates deliberate tampering with an audit record in the database.
    Verifies that the verification engine detects the break and flags the invalid event.
    """
    # 1. Login as Admin
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ncrb.gov.in", "password": "Admin@DocShield2026!"},
    )
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Fetch the latest audit event and tamper with its action directly in the DB
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT id, action, event_hash FROM audit_events ORDER BY timestamp DESC LIMIT 1")
        )
        row = result.fetchone()
        if row:
            tampered_id = row[0]
            # Mutate action without updating event_hash
            await session.execute(
                text("UPDATE audit_events SET action = 'TAMPERED_ACTION' WHERE id = :id"),
                {"id": tampered_id},
            )
            await session.commit()

            # 3. Run audit verification -> MUST detect tampering
            verify_resp = await client.get("/api/v1/admin/audit/verify", headers=admin_headers)
            assert verify_resp.status_code == 200
            res = verify_resp.json()
            assert res["valid"] is False
            assert res["first_invalid_event"] is not None
            assert "tampering" in res["reason"].lower() or "broken" in res["reason"].lower()

            # Restore original action
            await session.execute(
                text("UPDATE audit_events SET action = :act WHERE id = :id"),
                {"act": row[1], "id": tampered_id},
            )
            await session.commit()

