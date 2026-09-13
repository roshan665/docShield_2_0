"""
Phase 7 Tests: Cryptographic Integrity Gating & Tamper Detection
Ensures documents failing SHA-256 validation are rejected from embedding generation and search indexing,
generating a security audit event.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import DocumentEmbedding
from app.models.audit import AuditEvent
from app.models.auth import User
from app.models.case import Case, CaseMember
from app.models.document import Document, DocumentVersion
from app.modules.ai.service import AIService


@pytest.mark.asyncio
async def test_sha256_mismatch_blocks_embedding_and_logs_audit(db_session: AsyncSession):
    """
    Simulates a tampered file payload in object storage where the SHA-256 does not
    match the recorded version hash. Verifies the AI pipeline aborts, sets
    integrity_status='compromised', and emits an audit event.
    """
    # 1. User & Case setup
    officer = (await db_session.execute(select(User).limit(1))).scalar_one()

    case = Case(
        title="Tamper Detection Case",
        case_number=f"CR-TAMPER-{uuid4().hex[:6].upper()}",
        category="cyber_fraud",
        status="under_investigation",
        created_by=officer.id,
        investigating_officer_id=officer.id,
    )
    db_session.add(case)
    await db_session.flush()

    db_session.add(
        CaseMember(
            case_id=case.id,
            user_id=officer.id,
            role_in_case="lead_investigator",
            added_at=datetime.now(UTC),
        )
    )

    # 2. Create Document and Version with a specific SHA-256
    doc = Document(
        case_id=case.id,
        title="Seized Hard Drive Ledger",
        document_type="evidence_record",
        original_filename="ledger.txt",
        uploaded_by=officer.id,
        status="uploading",
    )
    db_session.add(doc)
    await db_session.flush()

    genuine_hash = "0" * 64  # Recorded expected hash
    ver = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        storage_key=f"cases/{case.id}/ledger.txt",
        storage_bucket="sih190-documents",
        file_hash_sha256=genuine_hash,
        file_size_bytes=100,
        mime_type="text/plain",
        original_filename="ledger.txt",
        sanitized_filename="ledger.txt",
        created_by=officer.id,
    )
    db_session.add(ver)
    await db_session.flush()

    doc.current_version_id = ver.id
    doc.status = "processed"
    await db_session.commit()

    # 3. Mock Storage returning tampered bytes (whose SHA-256 does NOT equal genuine_hash)
    tampered_bytes = b"CORRUPTED OR TAMPERED EVIDENCE CONTENT"
    mock_storage = MagicMock()
    mock_storage.download.return_value = tampered_bytes

    ai_service = AIService(session=db_session, storage=mock_storage)

    # 4. Processing must raise ValueError due to integrity failure
    with pytest.raises(ValueError, match="integrity check failed"):
        await ai_service.process_document(document_id=doc.id, actor_id=officer.id)

    # 5. Verify database state
    await db_session.refresh(ver)
    assert ver.integrity_status == "compromised"

    # Verify no embeddings were created
    emb_stmt = select(DocumentEmbedding).where(DocumentEmbedding.document_id == doc.id)
    embeddings = (await db_session.execute(emb_stmt)).scalars().all()
    assert len(embeddings) == 0

    # Verify audit event was logged
    audit_stmt = select(AuditEvent).where(
        AuditEvent.action == "embedding.integrity_rejected",
        AuditEvent.resource_id == str(ver.id),
    )
    audit_logs = (await db_session.execute(audit_stmt)).scalars().all()
    assert len(audit_logs) >= 1
    assert audit_logs[0].result == "failure"
    assert "SHA-256 payload tampering" in audit_logs[0].details.get("reason", "")
