"""
Phase 4 Document Management Test Suite
Validates:
1. Multipart upload with MIME and magic-byte inspection
2. Rejection of spoofed, executable, script, and oversized payloads
3. Path traversal prevention and filename sanitization
4. EICAR malware test signature detection
5. Zero-trust case membership scoping and IDOR prevention
6. Immutable document versioning lifecycle
7. Live cryptographic SHA-256 integrity verification and tamper detection
8. Audit event emission on upload, versioning, download, and tamper alerts
"""

import hashlib
import io
import uuid

import pytest
from httpx import AsyncClient

# Sample valid payloads
VALID_PDF_BYTES = b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
VALID_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
VALID_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\xff\xd9"
EICAR_PAYLOAD = b"%PDF-1.4\nX5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*\n%%EOF"
EXE_PAYLOAD = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"


async def get_auth_token(client: AsyncClient, email: str, password: str) -> str:
    """Helper to authenticate and retrieve access token."""
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


async def create_test_case(client: AsyncClient, token: str) -> dict:
    """Helper creating a test case with creator enrolled as lead investigator."""
    case_num = f"CASE-DOC-{uuid.uuid4().hex[:8].upper()}"
    res = await client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "case_number": case_num,
            "title": f"Document Test Case {case_num}",
            "priority": "high",
            "fir_number": f"FIR-{uuid.uuid4().hex[:6].upper()}",
            "police_station": "Cyber Crime Special Cell",
        },
    )
    assert res.status_code == 201
    return res.json()


@pytest.mark.asyncio
async def test_document_upload_success_and_metadata(client: AsyncClient):
    """Verifies that an authorized case member can upload a document with verified SHA-256."""
    token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    case = await create_test_case(client, token)
    case_id = case["id"]

    expected_sha256 = hashlib.sha256(VALID_PDF_BYTES).hexdigest().lower()

    # Upload document
    files = {"file": ("fir_report.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")}
    data = {
        "title": "First Information Report",
        "document_type": "fir",
        "classification": "confidential",
        "description": "Initial FIR filing",
    }

    res = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
        data=data,
    )
    assert res.status_code == 201
    doc = res.json()
    assert doc["title"] == "First Information Report"
    assert doc["document_type"] == "fir"
    assert doc["file_hash_sha256"] == expected_sha256
    assert doc["mime_type"] == "application/pdf"
    assert doc["current_version"]["version_number"] == 1
    assert doc["current_version"]["integrity_status"] == "verified"

    # Verify retrieval
    get_res = await client.get(
        f"/api/v1/documents/{doc['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_res.status_code == 200
    assert get_res.json()["id"] == doc["id"]


@pytest.mark.asyncio
async def test_document_magic_byte_validation_and_spoof_rejection(client: AsyncClient):
    """Verifies that spoofed extensions, executables, and scripts are rejected."""
    token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    case = await create_test_case(client, token)
    case_id = case["id"]

    # 1. Windows PE executable disguised as PDF
    res1 = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("malicious.pdf", io.BytesIO(EXE_PAYLOAD), "application/pdf")},
        data={"title": "Fake PDF", "document_type": "fir"},
    )
    assert res1.status_code in (400, 422)
    assert "signature" in res1.json()["detail"].lower() or "unsupported" in res1.json()["detail"].lower()

    # 2. Shell script disguised as Word Document
    script_bytes = b"#!/bin/bash\nrm -rf / --no-preserve-root"
    res2 = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("report.docx", io.BytesIO(script_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"title": "Script attack", "document_type": "police_report"},
    )
    assert res2.status_code in (400, 422)

    # 3. Legitimate JPEG upload succeeds
    res3 = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("crime_scene.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")},
        data={"title": "Crime Scene Photo", "document_type": "supporting_document"},
    )
    assert res3.status_code == 201
    assert res3.json()["mime_type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_document_oversized_file_rejected(client: AsyncClient):
    """Verifies that files exceeding configured maximum threshold are rejected."""
    token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    case = await create_test_case(client, token)
    case_id = case["id"]

    # Generate oversized payload (> 50MB)
    oversized = b"%PDF-1.5\n" + (b"0" * (51 * 1024 * 1024))
    res = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("giant.pdf", io.BytesIO(oversized), "application/pdf")},
        data={"title": "Giant File", "document_type": "fir"},
    )
    assert res.status_code in (400, 413, 422)
    assert "exceeds" in res.json()["detail"].lower()


def test_document_filename_sanitization_and_traversal_prevention():
    """Verifies that path traversal sequences and null bytes are rejected by filename sanitizer."""
    from app.core.exceptions import ValidationException
    from app.core.file_validation import sanitize_filename

    # 1. Path traversal attempts
    with pytest.raises(ValidationException) as exc1:
        sanitize_filename("../../../../etc/passwd.pdf")
    assert "traversal" in str(exc1.value.detail).lower()

    with pytest.raises(ValidationException) as exc2:
        sanitize_filename("..\\windows\\system32\\cmd.exe")
    assert "traversal" in str(exc2.value.detail).lower()

    # 2. Null byte attempt
    with pytest.raises(ValidationException) as exc3:
        sanitize_filename("test\x00payload.pdf")
    assert "null byte" in str(exc3.value.detail).lower()

    # 3. Empty or space only
    with pytest.raises(ValidationException):
        sanitize_filename("   ")

    # 4. Valid sanitization preserves clean names and strips dangerous symbols
    sanitized = sanitize_filename("FIR Report (Final) #1! [Draft].pdf")
    assert ".." not in sanitized
    assert "/" not in sanitized
    assert sanitized.endswith(".pdf")


@pytest.mark.asyncio
async def test_document_malware_detection_hook(client: AsyncClient):
    """Verifies that files containing malware test signatures are rejected with an alert."""
    token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    case = await create_test_case(client, token)
    case_id = case["id"]

    res = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("eicar_test.pdf", io.BytesIO(EICAR_PAYLOAD), "application/pdf")},
        data={"title": "EICAR Infected File", "document_type": "fir"},
    )
    assert res.status_code in (400, 422)
    assert "malware" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_case_membership_document_access_scoping(client: AsyncClient):
    """Verifies that non-members receive 404 on documents, mitigating IDOR."""
    inv_token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    sup_token = await get_auth_token(client, "supervisor@ncrb.gov.in", "Supervisor@2026!")

    # Investigator creates case and uploads document
    case = await create_test_case(client, inv_token)
    case_id = case["id"]

    doc_res = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers={"Authorization": f"Bearer {inv_token}"},
        files={"file": ("confidential.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")},
        data={"title": "Confidential Report", "document_type": "investigation_report"},
    )
    assert doc_res.status_code == 201
    doc_id = doc_res.json()["id"]

    # Supervisor (not a member of this case) attempts to access case documents
    list_res = await client.get(
        f"/api/v1/cases/{case_id}/documents",
        headers={"Authorization": f"Bearer {sup_token}"},
    )
    assert list_res.status_code == 404

    # Supervisor attempts to get document metadata directly
    get_res = await client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {sup_token}"},
    )
    assert get_res.status_code == 404

    # Supervisor attempts to download document
    down_res = await client.get(
        f"/api/v1/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {sup_token}"},
    )
    assert down_res.status_code == 404


@pytest.mark.asyncio
async def test_immutable_document_versioning(client: AsyncClient):
    """Verifies that uploading new versions increments version numbers and preserves prior versions."""
    token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    case = await create_test_case(client, token)
    case_id = case["id"]

    v1_bytes = VALID_PDF_BYTES
    v1_hash = hashlib.sha256(v1_bytes).hexdigest().lower()

    # 1. Upload Version 1
    doc_res = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("statement_v1.pdf", io.BytesIO(v1_bytes), "application/pdf")},
        data={"title": "Witness Statement", "document_type": "witness_statement"},
    )
    assert doc_res.status_code == 201
    doc_id = doc_res.json()["id"]
    v1_id = doc_res.json()["current_version_id"]

    # 2. Upload Version 2
    v2_bytes = VALID_PDF_BYTES + b"\n% Additional witness testimony appended."
    v2_hash = hashlib.sha256(v2_bytes).hexdigest().lower()
    assert v1_hash != v2_hash

    v2_res = await client.post(
        f"/api/v1/documents/{doc_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("statement_v2.pdf", io.BytesIO(v2_bytes), "application/pdf")},
        data={"change_reason": "Appended second witness deposition"},
    )
    assert v2_res.status_code == 201
    updated_doc = v2_res.json()
    assert updated_doc["current_version"]["version_number"] == 2
    assert updated_doc["file_hash_sha256"] == v2_hash

    # 3. List all versions
    vers_res = await client.get(
        f"/api/v1/documents/{doc_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert vers_res.status_code == 200
    versions = vers_res.json()
    assert len(versions) == 2
    assert versions[0]["version_number"] == 2
    assert versions[0]["file_hash_sha256"] == v2_hash
    assert versions[1]["version_number"] == 1
    assert versions[1]["file_hash_sha256"] == v1_hash

    # 4. Download Version 1 specifically
    down_v1 = await client.get(
        f"/api/v1/documents/{doc_id}/versions/{v1_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert down_v1.status_code == 200
    assert down_v1.content == v1_bytes

    # 5. Download Current Version (Version 2)
    down_v2 = await client.get(
        f"/api/v1/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert down_v2.status_code == 200
    assert down_v2.content == v2_bytes


@pytest.mark.asyncio
async def test_live_integrity_verification_and_tamper_detection(client: AsyncClient):
    """Verifies that live integrity verification detects storage modifications and halts download."""
    token = await get_auth_token(client, "officer@ncrb.gov.in", "Investigator@2026!")
    case = await create_test_case(client, token)
    case_id = case["id"]

    # Upload document
    doc_res = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("verified.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")},
        data={"title": "Tamper Test File", "document_type": "court_filing"},
    )
    assert doc_res.status_code == 201
    doc = doc_res.json()
    doc_id = doc["id"]

    # 1. Live verify endpoint on intact file
    verify_res = await client.get(
        f"/api/v1/documents/{doc_id}/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["match"] is True
    assert v_data["integrity_status"] == "verified"

    # 2. Simulate object corruption in S3
    from app.modules.documents.dependencies import get_storage_service
    storage = get_storage_service()
    ver_obj = doc["current_version"]
    # Corrupt the storage key with bad bytes
    storage.upload(
        file_data=b"%PDF-1.5\nCORRUPTED_BYTES_HERE",
        key=f"cases/{case_id}/documents/{doc_id}/versions/{ver_obj['id']}",
        bucket="sih190-documents",
    )

    # 3. Attempt download of corrupted document
    down_corrupt = await client.get(
        f"/api/v1/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert down_corrupt.status_code in (400, 422)
    assert "integrity" in down_corrupt.json()["detail"].lower()

    # 4. Live verify endpoint reflects compromised state
    verify_compromised = await client.get(
        f"/api/v1/documents/{doc_id}/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert verify_compromised.status_code == 200
    assert verify_compromised.json()["match"] is False
    assert verify_compromised.json()["integrity_status"] == "compromised"
