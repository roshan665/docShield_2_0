"""
Phase 7 Tests: pgvector Embeddings, Version Isolation & Idempotency
Validates 768-dim embeddings, unique constraint handling, version-isolation, and upsert idempotency.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ai import DocumentEmbedding
from app.models.auth import User
from app.models.case import Case, CaseMember
from app.models.document import Document, DocumentVersion
from app.modules.ai.embeddings import (
    generate_embeddings_for_chunks,
    generate_query_embedding,
)
from app.modules.ai.repository import AIRepository


@pytest.mark.asyncio
async def test_embeddings_vector_dimensions_and_consistency():
    """Verify generated embeddings strictly adhere to 768 dimensions."""
    text = "First Information Report registered under Section 302 IPC at Cyber Crime Police Station."
    embedding = generate_query_embedding(text)
    assert len(embedding) == settings.EMBEDDING_DIMENSIONS
    assert len(embedding) == 768

    chunks = [
        "Chunk 1: Accused was intercepted at checkpost.",
        "Chunk 2: Seizure memo prepared in presence of independent panch witnesses.",
    ]
    batch_embeddings = generate_embeddings_for_chunks(chunks)
    assert len(batch_embeddings) == 2
    for emb in batch_embeddings:
        assert len(emb) == 768


@pytest.mark.asyncio
async def test_embeddings_version_isolation_and_idempotency(db_session: AsyncSession):
    """
    Verify that embeddings are strictly tied to a DocumentVersion and that
    upserting embeddings for the same version and chunk index is idempotent.
    """
    repo = AIRepository(db_session)

    # 1. Fetch an existing officer user from DB
    user_stmt = select(User).where(User.role.has(name="investigator"))
    res_user = await db_session.execute(user_stmt)
    user = res_user.scalars().first()
    if not user:
        user = (await db_session.execute(select(User).limit(1))).scalar_one()

    # 2. Create Case and Member
    case = Case(
        title="Cyber Fraud Investigation 2026",
        case_number=f"CR-2026-EMB-{user.id.hex[:6].upper()}",
        category="cyber_fraud",
        status="under_investigation",
        created_by=user.id,
        investigating_officer_id=user.id,
    )
    db_session.add(case)
    await db_session.flush()

    member = CaseMember(
        case_id=case.id,
        user_id=user.id,
        role_in_case="lead_investigator",
        added_at=datetime.now(UTC),
    )
    db_session.add(member)

    # 3. Create Document with Version 1 and Version 2
    doc = Document(
        case_id=case.id,
        title="Charge Sheet Draft",
        document_type="charge_sheet",
        original_filename="chargesheet.pdf",
        uploaded_by=user.id,
        status="processed",
    )
    db_session.add(doc)
    await db_session.flush()

    v1 = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        storage_key=f"cases/{case.id}/chargesheet_v1.pdf",
        storage_bucket="sih190-documents",
        file_hash_sha256="a" * 64,
        file_size_bytes=1024,
        mime_type="application/pdf",
        original_filename="chargesheet_v1.pdf",
        sanitized_filename="chargesheet_v1.pdf",
        created_by=user.id,
    )
    v2 = DocumentVersion(
        document_id=doc.id,
        version_number=2,
        storage_key=f"cases/{case.id}/chargesheet_v2.pdf",
        storage_bucket="sih190-documents",
        file_hash_sha256="b" * 64,
        file_size_bytes=2048,
        mime_type="application/pdf",
        original_filename="chargesheet_v2.pdf",
        sanitized_filename="chargesheet_v2.pdf",
        created_by=user.id,
    )
    db_session.add_all([v1, v2])
    await db_session.flush()

    # 4. Save embeddings for Version 1
    chunks_v1 = ["Version 1 primary allegation: fund misappropriation."]
    emb_v1 = generate_embeddings_for_chunks(chunks_v1)
    v1_records = await repo.save_embeddings(
        document_id=doc.id,
        case_id=case.id,
        chunks=chunks_v1,
        embeddings=emb_v1,
        version_id=v1.id,
        version_number=1,
    )
    assert len(v1_records) == 1
    assert v1_records[0].version_id == v1.id
    assert v1_records[0].chunk_id == f"DOC-{str(doc.id)[:8].upper()}-V1-C0"
    assert v1_records[0].is_searchable is True

    # 5. Save embeddings for Version 2 (Version isolation)
    chunks_v2 = ["Version 2 amended allegation: cyber laundering across offshore nodes."]
    emb_v2 = generate_embeddings_for_chunks(chunks_v2)
    v2_records = await repo.save_embeddings(
        document_id=doc.id,
        case_id=case.id,
        chunks=chunks_v2,
        embeddings=emb_v2,
        version_id=v2.id,
        version_number=2,
    )
    assert len(v2_records) == 1
    assert v2_records[0].version_id == v2.id
    assert v2_records[0].chunk_id == f"DOC-{str(doc.id)[:8].upper()}-V2-C0"

    # 6. Idempotent Upsert: re-saving embeddings for Version 1 updates existing record without duplicate key error
    chunks_v1_updated = ["Version 1 updated allegation: fund misappropriation confirmed."]
    emb_v1_updated = generate_embeddings_for_chunks(chunks_v1_updated)
    upserted_records = await repo.save_embeddings(
        document_id=doc.id,
        case_id=case.id,
        chunks=chunks_v1_updated,
        embeddings=emb_v1_updated,
        version_id=v1.id,
        version_number=1,
    )
    assert len(upserted_records) == 1
    assert upserted_records[0].chunk_text == chunks_v1_updated[0]

    # Verify database count for doc is 2 (1 for V1, 1 for V2)
    count_stmt = select(DocumentEmbedding).where(DocumentEmbedding.document_id == doc.id)
    all_embeddings = (await db_session.execute(count_stmt)).scalars().all()
    assert len(all_embeddings) == 2
