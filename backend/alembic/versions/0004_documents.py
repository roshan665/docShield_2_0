"""Create documents and document_versions tables

Revision ID: 0004_documents
Revises: 0003_cases_audit
Create Date: 2026-09-12 02:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0004_documents'
down_revision: str | None = '0003_cases_audit'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. documents table (without current_version_id FK initially to break circularity)
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('document_type', sa.String(100), nullable=False, server_default='other'),
        sa.Column('classification', sa.String(50), nullable=False, server_default='internal'),
        sa.Column('status', sa.String(50), nullable=False, server_default='processed'),
        sa.Column('current_version_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('original_filename', sa.String(500), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('is_evidence', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('evidence_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ai_processed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "document_type IN ('fir', 'police_report', 'investigation_report', 'witness_statement', 'charge_sheet', 'court_filing', 'evidence_record', 'forensic_report', 'legal_notice', 'judgment', 'supporting_document', 'other')",
            name='chk_documents_type',
        ),
        sa.CheckConstraint(
            "classification IN ('public', 'internal', 'confidential', 'secret', 'top_secret')",
            name='chk_documents_classification',
        ),
        sa.CheckConstraint(
            "status IN ('uploading', 'processing', 'processed', 'failed', 'archived')",
            name='chk_documents_status',
        ),
    )
    op.create_index('ix_documents_case_id', 'documents', ['case_id'])
    op.create_index('ix_documents_type', 'documents', ['document_type'])
    op.create_index('ix_documents_status', 'documents', ['status'])
    op.create_index('ix_documents_created_at', 'documents', ['created_at'])

    # 2. document_versions table
    op.create_table(
        'document_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('storage_key', sa.String(500), nullable=False),
        sa.Column('storage_bucket', sa.String(100), nullable=False),
        sa.Column('file_hash_sha256', sa.String(64), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('original_filename', sa.String(500), nullable=False),
        sa.Column('sanitized_filename', sa.String(500), nullable=False),
        sa.Column('change_reason', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('is_original', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('integrity_status', sa.String(20), nullable=False, server_default='verified'),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('document_id', 'version_number', name='uq_document_version_number'),
        sa.CheckConstraint("integrity_status IN ('verified', 'compromised', 'pending')", name='chk_doc_version_integrity'),
    )
    op.create_index('ix_document_versions_document_id', 'document_versions', ['document_id'])
    op.create_index('ix_document_versions_file_hash', 'document_versions', ['file_hash_sha256'])
    op.create_index('ix_document_versions_integrity', 'document_versions', ['integrity_status'])

    # 3. Add circular foreign key documents.current_version_id -> document_versions.id
    op.create_foreign_key(
        'fk_documents_current_version_id',
        'documents',
        'document_versions',
        ['current_version_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_documents_current_version_id', 'documents', type_='foreignkey')
    op.drop_table('document_versions')
    op.drop_table('documents')
