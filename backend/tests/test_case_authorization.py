"""
Tests for Case Authorization, IDOR/BOLA Prevention, and Role Boundaries
"""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cross_case_idor_prevention(client: AsyncClient):
    # 1. Admin provisions two separate investigators
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ncrb.gov.in", "password": "Admin@DocShield2026!"},
    )
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    inv1_email = f"inv1_{uuid.uuid4().hex[:6]}@ncrb.gov.in"
    inv2_email = f"inv2_{uuid.uuid4().hex[:6]}@ncrb.gov.in"

    await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "employee_id": f"EMP-I1-{uuid.uuid4().hex[:4].upper()}",
            "email": inv1_email,
            "full_name": "Investigator One",
            "password": "Password123!",
            "role_name": "investigator",
        },
    )
    await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "employee_id": f"EMP-I2-{uuid.uuid4().hex[:4].upper()}",
            "email": inv2_email,
            "full_name": "Investigator Two",
            "password": "Password123!",
            "role_name": "investigator",
        },
    )

    # 2. Investigator 1 creates Case 1
    resp1 = await client.post(
        "/api/v1/auth/login",
        json={"email": inv1_email, "password": "Password123!"},
    )
    inv1_headers = {"Authorization": f"Bearer {resp1.json()['access_token']}"}

    case1_num = f"CR-ISO1-{uuid.uuid4().hex[:6].upper()}"
    case1_create = await client.post(
        "/api/v1/cases",
        headers=inv1_headers,
        json={"case_number": case1_num, "title": "Confidential Case 1"},
    )
    assert case1_create.status_code == 201
    case1_id = case1_create.json()["id"]

    # 3. Investigator 2 creates Case 2
    resp2 = await client.post(
        "/api/v1/auth/login",
        json={"email": inv2_email, "password": "Password123!"},
    )
    inv2_headers = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

    case2_num = f"CR-ISO2-{uuid.uuid4().hex[:6].upper()}"
    case2_create = await client.post(
        "/api/v1/cases",
        headers=inv2_headers,
        json={"case_number": case2_num, "title": "Confidential Case 2"},
    )
    assert case2_create.status_code == 201
    case2_id = case2_create.json()["id"]

    # 4. Investigator 2 attempts IDOR on Case 1 -> MUST receive 404
    idor_resp = await client.get(f"/api/v1/cases/{case1_id}", headers=inv2_headers)
    assert idor_resp.status_code == 404

    # 5. Investigator 1 attempts IDOR on Case 2 -> MUST receive 404
    idor_resp2 = await client.get(f"/api/v1/cases/{case2_id}", headers=inv1_headers)
    assert idor_resp2.status_code == 404

    # 6. Verify List Cases does not leak Case 1 to Investigator 2
    inv2_list = await client.get("/api/v1/cases", headers=inv2_headers)
    assert inv2_list.status_code == 200
    cases_for_inv2 = inv2_list.json()
    case_ids_for_inv2 = [c["id"] for c in cases_for_inv2]
    assert case1_id not in case_ids_for_inv2
    assert case2_id in case_ids_for_inv2


@pytest.mark.asyncio
async def test_supervisor_access_boundary(client: AsyncClient):
    """
    Supervisors must NOT have global case access.
    They must be explicitly assigned to a case in case_members.
    """
    # 1. Admin creates a Supervisor
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ncrb.gov.in", "password": "Admin@DocShield2026!"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    sup_email = f"sup_{uuid.uuid4().hex[:6]}@ncrb.gov.in"
    sup_create = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "employee_id": f"EMP-SUP-{uuid.uuid4().hex[:4].upper()}",
            "email": sup_email,
            "full_name": "Senior Superintendent",
            "password": "SupervisorPass@2026!",
            "role_name": "supervisor",
        },
    )
    assert sup_create.status_code == 201

    # 2. Investigator creates a case
    inv_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "officer@ncrb.gov.in", "password": "Investigator@2026!"},
    )
    inv_headers = {"Authorization": f"Bearer {inv_login.json()['access_token']}"}

    case_create = await client.post(
        "/api/v1/cases",
        headers=inv_headers,
        json={"case_number": f"CR-SUP-{uuid.uuid4().hex[:6].upper()}", "title": "Field Inquest"},
    )
    case_id = case_create.json()["id"]

    # 3. Supervisor logs in and attempts to access unassigned case -> MUST receive 404
    sup_login = await client.post(
        "/api/v1/auth/login",
        json={"email": sup_email, "password": "SupervisorPass@2026!"},
    )
    sup_headers = {"Authorization": f"Bearer {sup_login.json()['access_token']}"}

    sup_get = await client.get(f"/api/v1/cases/{case_id}", headers=sup_headers)
    assert sup_get.status_code == 404, f"Expected 404, got {sup_get.status_code}"

    # Supervisor case list should not contain this case
    sup_list = await client.get("/api/v1/cases", headers=sup_headers)
    assert sup_list.status_code == 200
    assert case_id not in [c["id"] for c in sup_list.json()]

