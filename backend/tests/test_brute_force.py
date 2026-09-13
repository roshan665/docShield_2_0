"""Tests for Account Lockout and Brute-Force Throttling."""

import uuid

import pytest


@pytest.mark.asyncio
async def test_account_lockout_after_five_failed_attempts(client):
    """Verifies that an account is locked after 5 consecutive failed passwords."""
    # 1. Provision a test user via Admin
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ncrb.gov.in", "password": "Admin@DocShield2026!"},
    )
    admin_token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    roles_res = await client.get("/api/v1/roles", headers=headers)
    inv_role = next(r for r in roles_res.json() if r["name"] == "investigator")

    test_suffix = uuid.uuid4().hex[:6]
    test_email = f"lockout_test_{test_suffix}@ncrb.gov.in"
    create_res = await client.post(
        "/api/v1/users",
        json={
            "employee_id": f"EMP-LOCK-{test_suffix}",
            "email": test_email,
            "full_name": "Lockout Test Officer",
            "password": "OriginalPassword@2026!",
            "role_id": inv_role["id"],
        },
        headers=headers,
    )
    assert create_res.status_code == 201

    # 2. Attempt 4 failed logins (should return 401)
    for _ in range(4):
        res = await client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": "WrongPassword!"},
        )
        assert res.status_code == 401
        assert res.json()["error_code"] == "AUTH_001"

    # 3. 5th failed attempt triggers account lockout (returns 403)
    fifth_res = await client.post(
        "/api/v1/auth/login",
        json={"email": test_email, "password": "WrongPassword!"},
    )
    assert fifth_res.status_code == 403
    assert fifth_res.json()["error_code"] == "AUTH_003"
    assert "locked" in fifth_res.json()["detail"].lower()

    # 4. Subsequent attempt even with CORRECT password is rejected while locked
    correct_attempt = await client.post(
        "/api/v1/auth/login",
        json={"email": test_email, "password": "OriginalPassword@2026!"},
    )
    assert correct_attempt.status_code == 403
    assert correct_attempt.json()["error_code"] == "AUTH_003"
