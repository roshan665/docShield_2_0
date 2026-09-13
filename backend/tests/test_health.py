"""Tests for application health and discovery endpoints."""

import pytest


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Verifies root endpoint returns service metadata."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert data["api_v1"] == "/api/v1"


@pytest.mark.asyncio
async def test_liveness_check(client):
    """Verifies basic /health returns healthy status."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["environment"] == "development"


@pytest.mark.asyncio
async def test_api_v1_liveness_check(client):
    """Verifies /api/v1/health conforms to API specification."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_readiness_check(client):
    """Verifies /health/ready returns service diagnostic status structure."""
    response = await client.get("/health/ready")
    # Response can be 200 (all up) or 503 (some external service down in test environment)
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert "database" in data["services"]
    assert "redis" in data["services"]
    assert "storage" in data["services"]
    assert "celery" in data["services"]
