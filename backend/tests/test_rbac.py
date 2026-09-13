"""Tests for Role-Based Access Control and Administrative boundaries."""

import uuid

import pytest


@pytest.mark.asyncio
async def test_unauthenticated_access_rejected(client):
    """Verifies that protected routes reject unauthenticated requests with 401."""
    response = await client.get("/api/v1/users")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_investigator_forbidden_from_admin_routes(client):
    """Verifies that non-admin officers (e.g. investigator) receive 403 on administrative endpoints."""
    # 1. Login as investigator
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "officer@ncrb.gov.in", "password": "Investigator@2026!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Attempt to list all users (admin only)
    users_res = await client.get("/api/v1/users", headers=headers)
    assert users_res.status_code == 403
    assert users_res.json()["error_code"] in ("AUTHZ_001", "AUTHZ_002")

    # 3. Attempt to inspect roles (admin only)
    roles_res = await client.get("/api/v1/roles", headers=headers)
    assert roles_res.status_code == 403


@pytest.mark.asyncio
async def test_admin_full_access(client):
    """Verifies that system administrators can access administrative endpoints."""
    # 1. Login as system admin
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ncrb.gov.in", "password": "Admin@DocShield2026!"},
    )
    admin_token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. List roles
    roles_res = await client.get("/api/v1/roles", headers=headers)
    assert roles_res.status_code == 200
    roles = roles_res.json()
    assert len(roles) >= 5

    # 3. List permissions
    perms_res = await client.get("/api/v1/permissions", headers=headers)
    assert perms_res.status_code == 200
    perms = perms_res.json()
    assert len(perms) >= 30

    # 4. List users
    users_res = await client.get("/api/v1/users", headers=headers)
    assert users_res.status_code == 200
    users = users_res.json()
    assert len(users) >= 2


@pytest.mark.asyncio
async def test_admin_create_and_manage_user(client):
    """Verifies administrative user provisioning and status management."""
    # 1. Login as system admin
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ncrb.gov.in", "password": "Admin@DocShield2026!"},
    )
    admin_token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Get roles to obtain a role_id
    roles_res = await client.get("/api/v1/roles", headers=headers)
    fe_role = next(r for r in roles_res.json() if r["name"] == "forensic_expert")

    # 2. Create new Forensic Expert user
    unique_suffix = uuid.uuid4().hex[:6]
    new_user_payload = {
        "employee_id": f"EMP-FE-{unique_suffix}",
        "email": f"forensic_{unique_suffix}@ncrb.gov.in",
        "full_name": "Dr. Sunita Rao",
        "password": "ForensicPass@2026!",
        "role_id": fe_role["id"],
        "department": "Central Forensic Science Laboratory",
        "designation": "Digital Forensics Lead",
    }
    create_res = await client.post("/api/v1/users", json=new_user_payload, headers=headers)
    assert create_res.status_code == 201
    created_user = create_res.json()
    assert created_user["email"] == new_user_payload["email"].lower()
    assert created_user["role"] == "forensic_expert"

    # 3. Deactivate user account
    status_res = await client.patch(
        f"/api/v1/users/{created_user['id']}/status",
        json={"is_active": False},
        headers=headers,
    )
    assert status_res.status_code == 200
    assert status_res.json()["is_active"] is False

    # 4. Verify deactivated user cannot log in
    attempt_login = await client.post(
        "/api/v1/auth/login",
        json={"email": created_user["email"], "password": "ForensicPass@2026!"},
    )
    assert attempt_login.status_code == 403
    assert attempt_login.json()["error_code"] == "AUTH_005"

    # 5. Reactivate user
    reactivate_res = await client.patch(
        f"/api/v1/users/{created_user['id']}/status",
        json={"is_active": True},
        headers=headers,
    )
    assert reactivate_res.status_code == 200
    assert reactivate_res.json()["is_active"] is True

    # 6. Admin Password Reset
    reset_res = await client.post(
        f"/api/v1/admin/users/{created_user['id']}/reset-password",
        headers=headers,
    )
    assert reset_res.status_code == 200
    temp_pass = reset_res.json()["temporary_password"]
    assert len(temp_pass) >= 12

    # 7. Login with Temporary Password
    login_temp = await client.post(
        "/api/v1/auth/login",
        json={"email": created_user["email"], "password": temp_pass},
    )
    assert login_temp.status_code == 200
