"""
Phase 8 Tests: Legal Court Export & Cryptographic Manifests
Validates case-scoped export package generation, deterministic ZIP structure,
SHA-256 manifests, pre-export integrity verification, and authorization boundaries.
"""

import io
import zipfile
from uuid import uuid4

import docx
import pytest
from httpx import AsyncClient


def make_docx(text: str) -> bytes:
    doc = docx.Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


async def get_token(client: AsyncClient, email: str = "officer@ncrb.gov.in", pwd: str = "Investigator@2026!") -> str:
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    assert res.status_code == 200
    return res.json()["access_token"]


async def create_case(client: AsyncClient, token: str) -> dict:
    case_num = f"CASE-EXP8-{uuid4().hex[:8].upper()}"
    res = await client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "case_number": case_num,
            "title": f"Phase 8 Legal Export Test {case_num}",
            "priority": "high",
            "fir_number": f"FIR-{uuid4().hex[:6].upper()}",
            "police_station": "Cyber Crime PS",
        },
    )
    assert res.status_code == 201
    return res.json()


@pytest.mark.asyncio
async def test_court_export_generation_and_manifest(client: AsyncClient):
    """
    Verifies that an authorized investigator can generate a court-ready export package.
    Tests deterministic ZIP layout, file inclusion, SHA-256 manifest calculation, and secure download.
    """
    token = await get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    case = await create_case(client, token)
    case_id = case["id"]

    # 1. Upload a test document into the case
    doc_bytes = make_docx("Confidential witness deposition regarding fraudulent wire transfers.")
    files = {"file": ("deposition_test.docx", doc_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {
        "case_id": case_id,
        "title": "Witness Deposition Alpha",
        "document_type": "witness_statement",
        "classification": "confidential",
    }
    upload_res = await client.post(f"/api/v1/cases/{case_id}/documents", headers=headers, data=data, files=files)
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 2. Register an evidence article
    ev_res = await client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers=headers,
        json={
            "title": "Seized Encrypted USB Drive",
            "evidence_type": "digital_document",
            "document_id": doc_id,
            "sensitivity_level": "confidential",
            "notes": "Recovered from suspect possession",
        },
    )
    assert ev_res.status_code == 201

    # 3. Generate Court Export
    export_res = await client.post(
        f"/api/v1/cases/{case_id}/exports",
        headers=headers,
        json={"include_files": True, "reason": "Production before Sessions Court"},
    )
    assert export_res.status_code == 201
    export_data = export_res.json()

    assert export_data["case_id"] == case_id
    assert export_data["integrity_status"] == "verified"
    assert export_data["export_status"] == "completed"
    assert "file_hash_sha256" in export_data
    assert "manifest_hash_sha256" in export_data
    export_id = export_data["id"]

    # 4. List Exports for Case
    list_res = await client.get(f"/api/v1/cases/{case_id}/exports", headers=headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(x["id"] == export_id for x in list_data["items"])

    # 5. Get Export Details
    detail_res = await client.get(f"/api/v1/cases/{case_id}/exports/{export_id}", headers=headers)
    assert detail_res.status_code == 200
    manifest = detail_res.json()["manifest_data"]
    assert manifest is not None
    assert manifest["case_id"] == case_id
    assert manifest["integrity_status"] == "verified"
    assert len(manifest["files"]) > 0

    # Verify manifest file entries
    file_paths = [f["path"] for f in manifest["files"]]
    assert "case/case_summary.json" in file_paths
    assert "documents/index.json" in file_paths
    assert "evidence/index.json" in file_paths
    assert "custody/custody_log.json" in file_paths
    assert "audit/audit_log.json" in file_paths

    # 6. Download Export Package ZIP
    dl_res = await client.get(f"/api/v1/cases/{case_id}/exports/{export_id}/download", headers=headers)
    assert dl_res.status_code == 200
    assert "application/zip" in dl_res.headers["content-type"]
    assert "attachment" in dl_res.headers["content-disposition"]

    # Verify ZIP contents
    zip_bytes = dl_res.content
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        namelist = zf.namelist()
        assert "README.txt" in namelist
        assert "integrity/manifest.json" in namelist
        assert "case/case_summary.json" in namelist
        assert "documents/index.json" in namelist

        # Inspect README certificate
        readme_content = zf.read("README.txt").decode("utf-8")
        assert "BHARATIYA SAKSHYA ADHINIYAM" in readme_content
        assert case["case_number"] in readme_content


@pytest.mark.asyncio
async def test_export_authorization_and_idor_defense(client: AsyncClient):
    """
    Verifies that a user cannot generate or access exports for a case where they lack membership.
    """
    officer_token = await get_token(client)
    case = await create_case(client, officer_token)
    case_id = case["id"]

    # Login as Forensic user (not a member of this case)
    forensic_token = await get_token(client, email="forensic@ncrb.gov.in", pwd="ForensicExpert@2026!")

    # Attempt export generation on unauthorized case -> 403 Forbidden
    unauth_res = await client.post(
        f"/api/v1/cases/{case_id}/exports",
        headers={"Authorization": f"Bearer {forensic_token}"},
        json={"include_files": False},
    )
    assert unauth_res.status_code in [403, 404]

    # Attempt list exports on unauthorized case
    unauth_list = await client.get(
        f"/api/v1/cases/{case_id}/exports",
        headers={"Authorization": f"Bearer {forensic_token}"},
    )
    assert unauth_list.status_code in [403, 404]
