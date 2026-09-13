"""
Phase 8 Tests: Security Monitoring & Incident Response
Validates security metrics, security event auditing, administrative access control,
and resolution workflows.
"""

import pytest
from httpx import AsyncClient


async def get_token(client: AsyncClient, email: str, pwd: str) -> str:
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_security_metrics_and_admin_rbac(client: AsyncClient):
    """
    Verifies that only System Administrator (and Supervisor) can access security metrics,
    and normal officers are denied.
    """
    admin_token = await get_token(client, "admin@ncrb.gov.in", "Admin@DocShield2026!")
    officer_token = await get_token(client, "officer@ncrb.gov.in", "Investigator@2026!")

    # 1. Non-admin cannot access metrics -> 403 Forbidden
    unauth_res = await client.get(
        "/api/v1/security/metrics",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert unauth_res.status_code == 403

    # 2. Admin can access metrics
    admin_res = await client.get(
        "/api/v1/security/metrics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_res.status_code == 200
    data = admin_res.json()

    assert "total_events" in data
    assert "critical_events" in data
    assert "high_events" in data
    assert "failed_logins" in data
    assert "category_breakdown" in data
    assert "recent_critical_events" in data


@pytest.mark.asyncio
async def test_security_events_list_and_resolution(client: AsyncClient):
    """
    Verifies listing, filtering, and resolving security events.
    """
    admin_token = await get_token(client, "admin@ncrb.gov.in", "Admin@DocShield2026!")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Trigger a failed login to produce a security event
    await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@ncrb.gov.in", "password": "WrongPassword123!"},
    )

    # List security events
    list_res = await client.get("/api/v1/security/events?limit=10", headers=headers)
    assert list_res.status_code == 200
    events_data = list_res.json()
    assert events_data["total"] >= 1
    assert len(events_data["items"]) > 0

    first_event = events_data["items"][0]
    event_id = first_event["id"]

    # Get single event
    detail_res = await client.get(f"/api/v1/security/events/{event_id}", headers=headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == event_id

    # Resolve event
    resolve_res = await client.post(f"/api/v1/security/events/{event_id}/resolve", headers=headers)
    assert resolve_res.status_code == 200
    assert resolve_res.json()["resolved"] is True
    assert resolve_res.json()["resolved_by"] is not None

