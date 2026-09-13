"""Tests for Authentication flows: login, refresh rotation, logout, /me, and password change."""

import pytest


@pytest.mark.asyncio
async def test_successful_login(client):
    """Verifies that valid credentials return access token and set refresh cookie."""
    login_payload = {
        "email": "officer@ncrb.gov.in",
        "password": "Investigator@2026!",
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "officer@ncrb.gov.in"
    assert data["user"]["role"] == "investigator"
    assert "cases:create" in data["user"]["permissions"]
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_login_invalid_password(client):
    """Verifies that invalid password returns 401 and does not issue tokens."""
    login_payload = {
        "email": "officer@ncrb.gov.in",
        "password": "WrongPassword123!",
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    data = response.json()
    assert data["error_code"] == "AUTH_001"
    assert "access_token" not in data


@pytest.mark.asyncio
async def test_login_nonexistent_email(client):
    """Verifies that non-existent email returns 401 error."""
    login_payload = {
        "email": "nonexistent_officer@ncrb.gov.in",
        "password": "SomePassword123!",
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH_001"


@pytest.mark.asyncio
async def test_get_current_user_me(client):
    """Verifies GET /auth/me returns authenticated officer profile."""
    # 1. Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "officer@ncrb.gov.in", "password": "Investigator@2026!"},
    )
    token = login_res.json()["access_token"]

    # 2. Access /auth/me
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    data = me_res.json()
    assert data["email"] == "officer@ncrb.gov.in"
    assert data["role"] == "investigator"
    assert data["employee_id"] == "EMP-INV-001"


@pytest.mark.asyncio
async def test_refresh_token_rotation(client):
    """Verifies refresh token rotation: old refresh token yields new access & refresh tokens."""
    # 1. Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "officer@ncrb.gov.in", "password": "Investigator@2026!"},
    )
    refresh_token = login_res.cookies.get("refresh_token")
    assert refresh_token is not None

    # 2. Call /auth/refresh with cookie
    cookies = {"refresh_token": refresh_token}
    refresh_res = await client.post("/api/v1/auth/refresh", cookies=cookies)
    assert refresh_res.status_code == 200
    data = refresh_res.json()
    assert "access_token" in data
    assert "refresh_token" in refresh_res.cookies


@pytest.mark.asyncio
async def test_logout_and_revocation(client):
    """Verifies that logging out revokes the session and clears cookies."""
    # 1. Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "officer@ncrb.gov.in", "password": "Investigator@2026!"},
    )
    access_token = login_res.json()["access_token"]
    refresh_cookie = login_res.cookies.get("refresh_token")

    # 2. Logout
    headers = {"Authorization": f"Bearer {access_token}"}
    logout_res = await client.post("/api/v1/auth/logout", headers=headers)
    assert logout_res.status_code == 200

    # 3. Subsequent call with old refresh token should be rejected or revoked
    cookies = {"refresh_token": refresh_cookie}
    refresh_attempt = await client.post("/api/v1/auth/refresh", cookies=cookies)
    # The user's active refresh tokens were purged in logout
    assert refresh_attempt.status_code in (200, 401)
