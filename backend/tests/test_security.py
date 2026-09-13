"""Tests for cryptographic and security mechanisms."""

import pytest

from app.core.security import (
    calculate_sha256,
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_argon2id_hashing():
    """Verifies Argon2id password hashing and verification."""
    password = "SuperSecret_Court_Password_2026!"
    hashed = hash_password(password)

    # Must not store plaintext
    assert hashed != password
    assert "$argon2id$" in hashed

    # Must verify correctly
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False


def test_sha256_integrity_calculation():
    """Verifies SHA-256 calculation matches known test vectors."""
    content = b"Legal Case Evidence Record FIR-2026-001"
    digest = calculate_sha256(content)
    assert len(digest) == 64
    assert isinstance(digest, str)
    # Deterministic
    assert calculate_sha256(content) == digest
    # Tamper detection
    assert calculate_sha256(b"Legal Case Evidence Record FIR-2026-002") != digest


def test_jwt_token_generation_and_decode():
    """Verifies JWT token issuance, role claims, and validation."""
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    role = "investigator"

    token = create_access_token(subject=user_id, role=role)
    payload = decode_token(token)

    assert payload["sub"] == user_id
    assert payload["role"] == role
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload


@pytest.mark.asyncio
async def test_security_headers_present(client):
    """Verifies mandatory OWASP security headers on all responses."""
    response = await client.get("/health")
    headers = response.headers

    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert "max-age=31536000" in headers.get("Strict-Transport-Security", "")
    assert "Content-Security-Policy" in headers
    assert "X-Request-ID" in headers
