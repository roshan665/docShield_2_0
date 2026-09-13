"""
Tests for Case Membership Operations: Add, Remove, Duplicates, and Inactive Users
"""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_case_membership_lifecycle(client: AsyncClient):
    # 1. Login as Admin to provision users
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ncrb.gov.in", "password": "Admin@DocShield2026!"},
    )
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Ensure Forensic Expert user exists
    fe_email = f"fe_{uuid.uuid4().hex[:6]}@ncrb.gov.in"
    fe_create = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "employee_id": f"EMP-FE-{uuid.uuid4().hex[:4].upper()}",
            "email": fe_email,
            "full_name": "Forensic Specialist",
            "password": "ForensicPass@2026!",
            "role_name": "forensic_expert",
            "department": "Digital Forensics",
        },
    )
    assert fe_create.status_code == 201
    fe_user_id = fe_create.json()["id"]

    # 2. Login as Investigator
    inv_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "officer@ncrb.gov.in", "password": "Investigator@2026!"},
    )
    inv_token = inv_login.json()["access_token"]
    inv_headers = {"Authorization": f"Bearer {inv_token}"}

    # 3. Create a case
    case_num = f"CR-MEM-{uuid.uuid4().hex[:6].upper()}"
    case_create = await client.post(
        "/api/v1/cases",
        headers=inv_headers,
        json={
            "case_number": case_num,
            "title": "Digital Artifact Analysis Case",
            "priority": "high",
        },
    )
    assert case_create.status_code == 201
    case_id = case_create.json()["id"]

    # 4. Forensic Expert currently cannot access the case (receives 404)
    fe_login = await client.post(
        "/api/v1/auth/login",
        json={"email": fe_email, "password": "ForensicPass@2026!"},
    )
    fe_token = fe_login.json()["access_token"]
    fe_headers = {"Authorization": f"Bearer {fe_token}"}

    unauth_get = await client.get(f"/api/v1/cases/{case_id}", headers=fe_headers)
    assert unauth_get.status_code == 404

    # 5. Investigator adds Forensic Expert as member
    add_member_resp = await client.post(
        f"/api/v1/cases/{case_id}/members",
        headers=inv_headers,
        json={
            "user_id": fe_user_id,
            "role_in_case": "forensic_analyst",
        },
    )
    assert add_member_resp.status_code == 201
    assert add_member_resp.json()["role_in_case"] == "forensic_analyst"

    # 6. Forensic Expert can now access the case
    auth_get = await client.get(f"/api/v1/cases/{case_id}", headers=fe_headers)
    assert auth_get.status_code == 200
    assert auth_get.json()["id"] == case_id

    # 7. Attempting to add duplicate active member fails
    dup_member = await client.post(
        f"/api/v1/cases/{case_id}/members",
        headers=inv_headers,
        json={
            "user_id": fe_user_id,
            "role_in_case": "forensic_analyst",
        },
    )
    assert dup_member.status_code == 409

    # 8. List members
    members_resp = await client.get(f"/api/v1/cases/{case_id}/members", headers=inv_headers)
    assert members_resp.status_code == 200
    members_list = members_resp.json()
    assert len(members_list) == 2

    # 9. Remove member
    remove_resp = await client.delete(
        f"/api/v1/cases/{case_id}/members/{fe_user_id}",
        headers=inv_headers,
    )
    assert remove_resp.status_code == 200

    # 10. Forensic Expert can no longer access case (receives 404)
    fe_removed_get = await client.get(f"/api/v1/cases/{case_id}", headers=fe_headers)
    assert fe_removed_get.status_code == 404

