"""
Phase 7 Tests: Search and RAG Rate Limiting
Validates that rapid query submission triggers HTTP 429 Too Many Requests with Retry-After header.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.rate_limit import is_rate_limited, reset_rate_limits


@pytest.mark.asyncio
async def test_rate_limiting_helper_function():
    """Verify is_rate_limited accurately tracks sliding window counts."""
    await reset_rate_limits()
    test_key = f"user_{uuid4().hex}"
    max_reqs = 3

    # First 3 requests should succeed
    for _ in range(max_reqs):
        limited, _ = await is_rate_limited(test_key, max_requests=max_reqs, window_seconds=60)
        assert limited is False

    # 4th request must be rate-limited
    limited, retry_after = await is_rate_limited(test_key, max_requests=max_reqs, window_seconds=60)
    assert limited is True
    assert retry_after > 0


@pytest.mark.asyncio
async def test_search_api_rate_limiting(
    client: AsyncClient,
    monkeypatch,
):
    """Verify FastAPI search endpoint enforces 429 when max requests are exceeded."""
    await reset_rate_limits()

    # Lower threshold temporarily for testing
    monkeypatch.setattr(settings, "SEARCH_RATE_LIMIT_PER_MINUTE", 3)

    # Admin provisions a dedicated fresh user
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ncrb.gov.in", "password": "Admin@DocShield2026!"},
    )
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    unique_email = f"ratelimit_{uuid4().hex[:6]}@ncrb.gov.in"
    await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "employee_id": f"EMP-RL-{uuid4().hex[:4].upper()}",
            "email": unique_email,
            "full_name": "Rate Limit Test User",
            "password": "Password123!",
            "role_name": "investigator",
        },
    )

    # Login as dedicated user
    res_login = await client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": "Password123!"},
    )
    assert res_login.status_code == 200
    token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create case
    case_num = f"CASE-RL-{uuid4().hex[:8].upper()}"
    res_case = await client.post(
        "/api/v1/cases",
        headers=headers,
        json={
            "case_number": case_num,
            "title": f"Rate Limit Test Case {case_num}",
            "priority": "medium",
            "fir_number": f"FIR-{uuid4().hex[:6].upper()}",
            "police_station": "Cyber Police Station",
        },
    )
    assert res_case.status_code == 201
    case_id = res_case.json()["id"]

    payload = {"query": "test rate limiting query", "case_id": case_id}

    # Send requests up to limit (3 allowed)
    for _ in range(3):
        resp = await client.post("/api/v1/search/semantic", json=payload, headers=headers)
        assert resp.status_code == 200

    # 4th request must receive 429
    resp_limited = await client.post("/api/v1/search/semantic", json=payload, headers=headers)
    assert resp_limited.status_code == 429
    assert "retry-after" in resp_limited.headers
    assert "rate limit exceeded" in resp_limited.json()["detail"].lower()
