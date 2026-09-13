"""Create AI pipeline tables and columns for metadata, entities, and vector embeddings

Revision ID: 0006_ai_pipeline
Revises: 0005_evidence_custody
Create Date: 2026-09-12 11:30:00.000000

"""
from collections.abc import Sequence

from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0006_ai_pipeline'
down_revision: str | None = '0005_evidence_custody'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add AI pipeline columns to documents table
    op.add_column('documents', sa.Column('ai_classification', sa.String(100), nullable=True))
    op.add_column('documents', sa.Column('ai_confidence', sa.Float(), nullable=True))
    op.add_column('documents', sa.Column('ocr_text', sa.Text(), nullable=True))
    op.add_column('documents', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('documents', sa.Column('ai_processing_error', sa.Text(), nullable=True))

    # 2. Create document_metadata table
    op.create_table(
        'document_metadata',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('key', sa.String(255), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('source', sa.String(50), nullable=False, server_default='ai_extracted'),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('verified_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint(
            "source IN ('manual', 'ai_extracted', 'system')",
            name='chk_document_metadata_source',
        ),
    )
    op.create_index('ix_document_metadata_doc_key', 'document_metadata', ['document_id', 'key'])
    op.create_index('ix_document_metadata_source', 'document_metadata', ['source'])

    # 3. Create extracted_entities table
    op.create_table(
        'extracted_entities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entity_type', sa.String(100), nullable=False),
        sa.Column('entity_value', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('start_offset', sa.Integer(), nullable=True),
        sa.Column('end_offset', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(50), nullable=False, server_default='ai'),
        sa.Column('verified', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint(
            "entity_type IN ('person', 'organization', 'location', 'date', 'law_section', 'case_number', 'fir_number', 'police_station', 'evidence_ref', 'phone_number', 'vehicle_number')",
            name='chk_extracted_entity_type',
        ),
    )
    op.create_index('ix_extracted_entities_document_id', 'extracted_entities', ['document_id'])
    op.create_index('ix_extracted_entities_type', 'extracted_entities', ['entity_type'])
    op.create_index('ix_extracted_entities_type_value', 'extracted_entities', ['entity_type', 'entity_value'])

    # 4. Create document_embeddings table with VECTOR(768)
    op.create_table(
        'document_embeddings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(768), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_document_embeddings_case_id', 'document_embeddings', ['case_id'])
    op.create_index('ix_document_embeddings_doc_chunk', 'document_embeddings', ['document_id', 'chunk_index'])

    # 5. HNSW Cosine Distance Index on embedding column
    op.execute(
        "CREATE INDEX ix_document_embeddings_vector ON document_embeddings "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);"
    )


def downgrade() -> None:
    op.drop_table('document_embeddings')
    op.drop_table('extracted_entities')
    op.drop_table('document_metadata')
    op.drop_column('documents', 'ai_processing_error')
    op.drop_column('documents', 'summary')
    op.drop_column('documents', 'ocr_text')
    op.drop_column('documents', 'ai_confidence')
    op.drop_column('documents', 'ai_classification')

