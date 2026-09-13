"""
Chain of Custody Handover Protocol Integration Tests
Verifies two-phase transfer (Initiate -> Pending -> Acknowledge), recipient validation,
custodian enforcement, and cancellation.
"""

import uuid

import pytest
from httpx import AsyncClient


async def get_auth_token(client: AsyncClient, email: str, password: str) -> str:
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


async def get_user_id(client: AsyncClient, token: str) -> str:
    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    return res.json()["id"]


async def create_test_case(client: AsyncClient, token: str) -> dict:
    case_num = f"CASE-CUST-{uuid.uuid4().hex[:8].upper()}"
    res = await client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "case_number": case_num,
            "title": f"Custody Test Case {case_num}",
            "priority": "high",
            "fir_number": f"FIR-{uuid.uuid4().hex[:6].upper()}",
            "police_station": "Crime Branch Special Cell",
        },
    )
    assert res.status_code == 201
    return res.json()


@pytest.mark.asyncio
async def test_two_phase_custody_transfer(client: AsyncClient):
    """
    Verifies complete two-phase custody handover flow:
    1. Current custodian initiates transfer.
    2. Status is marked pending; current custodian remains responsible.
    3. Unauthorized parties cannot acknowledge.
    4. Intended recipient acknowledges; custody shifts to new officer.
    5. Prior custodian loses transfer authority.
    """
    inv_token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    forensic_token = await get_auth_token(client, "forensic@ncrb.gov.in", "ForensicExpert@2026!")
    legal_token = await get_auth_token(client, "legal@ncrb.gov.in", "Legal@2026!")

    inv_id = await get_user_id(client, inv_token)
    forensic_id = await get_user_id(client, forensic_token)
    legal_id = await get_user_id(client, legal_token)

    # 1. Investigator creates case
    case = await create_test_case(client, inv_token)
    case_id = case["id"]

    # 2. Enroll Forensic Expert and Legal Officer into the case team
    add_f = await client.post(
        f"/api/v1/cases/{case_id}/members",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={"user_id": forensic_id, "role_in_case": "forensic_analyst"},
    )
    assert add_f.status_code in (200, 201)

    add_l = await client.post(
        f"/api/v1/cases/{case_id}/members",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={"user_id": legal_id, "role_in_case": "legal_counsel"},
    )
    assert add_l.status_code in (200, 201)

    # 3. Register evidence (Initial custodian = Investigator)
    reg_res = await client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={"title": "Encrypted USB Drive", "evidence_type": "device"},
    )
    assert reg_res.status_code == 201
    evidence_id = reg_res.json()["id"]
    assert reg_res.json()["current_custodian_id"] == inv_id

    # 4. Phase 1: Investigator initiates transfer to Forensic Expert
    transfer_res = await client.post(
        f"/api/v1/evidence/{evidence_id}/custody/transfer",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={
            "to_user_id": forensic_id,
            "reason": "Handover to CFSL for forensic imaging and artifact analysis",
            "location": "Central Forensic Science Laboratory, CBI Complex",
        },
    )
    assert transfer_res.status_code == 200
    t_data = transfer_res.json()
    assert t_data["transfer_pending"] is True
    assert t_data["pending_custodian_id"] == forensic_id
    # Crucial: Current custodian remains Investigator until acknowledged!
    assert t_data["current_custodian_id"] == inv_id

    # 5. Non-recipient (Legal Officer) attempts to acknowledge -> Rejected (403)
    unauth_ack = await client.post(
        f"/api/v1/evidence/{evidence_id}/custody/acknowledge",
        headers={"Authorization": f"Bearer {legal_token}"},
        json={"notes": "Illegal intercept attempt"},
    )
    assert unauth_ack.status_code == 403
    assert "recipient" in unauth_ack.json()["detail"].lower()

    # 6. Designated recipient (Forensic Expert) acknowledges receipt
    ack_res = await client.post(
        f"/api/v1/evidence/{evidence_id}/custody/acknowledge",
        headers={"Authorization": f"Bearer {forensic_token}"},
        json={
            "location": "CFSL Digital Evidence Locker Room A",
            "notes": "Evidence parcel tamper seals verified intact",
        },
    )
    assert ack_res.status_code == 200
    ack_data = ack_res.json()
    assert ack_data["transfer_pending"] is False
    assert ack_data["pending_custodian_id"] is None
    # Custody has now officially transitioned to Forensic Expert
    assert ack_data["current_custodian_id"] == forensic_id

    # 7. Old custodian (Investigator) tries to transfer again -> Rejected (403)
    old_transfer = await client.post(
        f"/api/v1/evidence/{evidence_id}/custody/transfer",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={"to_user_id": legal_id, "reason": "Unauthorized transfer attempt"},
    )
    assert old_transfer.status_code == 403
    assert "custodian" in old_transfer.json()["detail"].lower()


@pytest.mark.asyncio
async def test_custody_transfer_non_member_rejected(client: AsyncClient):
    """Verifies that custody cannot be transferred to a user who is not a member of the case."""
    inv_token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    forensic_token = await get_auth_token(client, "forensic@ncrb.gov.in", "ForensicExpert@2026!")

    forensic_id = await get_user_id(client, forensic_token)

    case = await create_test_case(client, inv_token)
    case_id = case["id"]

    reg_res = await client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={"title": "Sim Card Extracted", "evidence_type": "device"},
    )
    evidence_id = reg_res.json()["id"]

    # Forensic expert was NEVER added to this case
    bad_transfer = await client.post(
        f"/api/v1/evidence/{evidence_id}/custody/transfer",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={"to_user_id": forensic_id, "reason": "Transfer to non-case officer"},
    )
    assert bad_transfer.status_code in (400, 422)
    assert "assigned" in bad_transfer.json()["detail"].lower() or "member" in bad_transfer.json()["detail"].lower()


@pytest.mark.asyncio
async def test_custody_transfer_cancellation(client: AsyncClient):
    """Verifies that an active custodian can retract a pending transfer before it is acknowledged."""
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

    reg_res = await client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={"title": "Notebook of Accounts", "evidence_type": "physical_evidence"},
    )
    evidence_id = reg_res.json()["id"]

    # Initiate transfer
    await client.post(
        f"/api/v1/evidence/{evidence_id}/custody/transfer",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={"to_user_id": forensic_id, "reason": "For handwriting analysis"},
    )

    # Cancel transfer
    cancel_res = await client.post(
        f"/api/v1/evidence/{evidence_id}/custody/cancel",
        headers={"Authorization": f"Bearer {inv_token}"},
    )
    assert cancel_res.status_code == 200
    c_data = cancel_res.json()
    assert c_data["transfer_pending"] is False
    assert c_data["pending_custodian_id"] is None
