"""
Tests for Case Management CRUD & Lifecycle State Transitions
"""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_case_creation_and_retrieval(client: AsyncClient):
    # 1. Login as investigator
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "officer@ncrb.gov.in", "password": "Investigator@2026!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create case
    case_num = f"CR-2026-{uuid.uuid4().hex[:6].upper()}"
    create_resp = await client.post(
        "/api/v1/cases",
        headers=headers,
        json={
            "case_number": case_num,
            "fir_number": "FIR-2026-901",
            "title": "Cyber Extortion via Social Media",
            "description": "Investigation into organized extortion gang",
            "priority": "high",
            "category": "cybercrime",
            "police_station": "Cyber PS South",
            "district": "New Delhi",
            "state": "Delhi",
        },
    )
    assert create_resp.status_code == 201
    case_data = create_resp.json()
    assert case_data["case_number"] == case_num
    assert case_data["status"] == "open"
    assert case_data["user_role_in_case"] == "lead_investigator"
    case_id = case_data["id"]

    # 3. Retrieve case by ID
    get_resp = await client.get(f"/api/v1/cases/{case_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == case_id

    # 4. Duplicate case number should be rejected
    dup_resp = await client.post(
        "/api/v1/cases",
        headers=headers,
        json={
            "case_number": case_num,
            "title": "Another title",
            "priority": "low",
        },
    )
    assert dup_resp.status_code == 409


@pytest.mark.asyncio
async def test_case_lifecycle_state_machine(client: AsyncClient):
    # 1. Login as investigator
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "officer@ncrb.gov.in", "password": "Investigator@2026!"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create case
    case_num = f"CR-STATE-{uuid.uuid4().hex[:6].upper()}"
    create_resp = await client.post(
        "/api/v1/cases",
        headers=headers,
        json={
            "case_number": case_num,
            "title": "State Transition Test Case",
            "priority": "medium",
        },
    )
    assert create_resp.status_code == 201
    case_id = create_resp.json()["id"]

    # 3. Invalid transition directly from open -> closed should fail
    bad_transition = await client.patch(
        f"/api/v1/cases/{case_id}",
        headers=headers,
        json={"status": "closed"},
    )
    assert bad_transition.status_code == 422 or bad_transition.status_code == 400

    # 4. Valid transition: open -> under_investigation
    step1 = await client.patch(
        f"/api/v1/cases/{case_id}",
        headers=headers,
        json={"status": "under_investigation"},
    )
    assert step1.status_code == 200
    assert step1.json()["status"] == "under_investigation"

    # 5. Valid transition: under_investigation -> pending_review
    step2 = await client.patch(
        f"/api/v1/cases/{case_id}",
        headers=headers,
        json={"status": "pending_review"},
    )
    assert step2.status_code == 200
    assert step2.json()["status"] == "pending_review"

    # 6. Valid transition: pending_review -> pending_legal
    step3 = await client.patch(
        f"/api/v1/cases/{case_id}",
        headers=headers,
        json={"status": "pending_legal"},
    )
    assert step3.status_code == 200
    assert step3.json()["status"] == "pending_legal"

    # 7. Valid transition: pending_legal -> closed
    step4 = await client.patch(
        f"/api/v1/cases/{case_id}",
        headers=headers,
        json={"status": "closed"},
    )
    assert step4.status_code == 200
    assert step4.json()["status"] == "closed"
    assert step4.json()["closed_at"] is not None

