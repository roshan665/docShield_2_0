"""Create evidence and evidence_custody_events tables

Revision ID: 0005_evidence_custody
Revises: 0004_documents
Create Date: 2026-09-12 02:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0005_evidence_custody'
down_revision: str | None = '0004_documents'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create evidence table
    op.create_table(
        'evidence',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cases.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('evidence_number', sa.String(100), unique=True, nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('evidence_type', sa.String(100), nullable=False, server_default='digital_document'),
        sa.Column('status', sa.String(50), nullable=False, server_default='registered'),
        sa.Column('sensitivity_level', sa.String(50), nullable=False, server_default='standard'),
        sa.Column('original_file_hash', sa.String(64), nullable=True),
        sa.Column('current_file_hash', sa.String(64), nullable=True),
        sa.Column('integrity_status', sa.String(20), nullable=False, server_default='verified'),
        sa.Column('current_custodian_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('pending_custodian_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('transfer_pending', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('transfer_reason', sa.Text(), nullable=True),
        sa.Column('storage_key', sa.String(500), nullable=True),
        sa.Column('storage_bucket', sa.String(100), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('collection_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('collection_location', sa.Text(), nullable=True),
        sa.Column('source', sa.String(500), nullable=True),
        sa.Column('registered_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "evidence_type IN ('digital_document', 'image', 'video', 'audio', 'device', 'forensic_artifact', 'physical_evidence', 'other')",
            name='chk_evidence_type',
        ),
        sa.CheckConstraint(
            "status IN ('registered', 'in_custody', 'in_analysis', 'analyzed', 'submitted_to_court', 'archived')",
            name='chk_evidence_status',
        ),
        sa.CheckConstraint(
            "sensitivity_level IN ('standard', 'sensitive', 'highly_sensitive', 'confidential', 'secret', 'classified')",
            name='chk_evidence_sensitivity',
        ),
        sa.CheckConstraint(
            "integrity_status IN ('verified', 'compromised', 'pending')",
            name='chk_evidence_integrity',
        ),
    )
    op.create_index('ix_evidence_case_id', 'evidence', ['case_id'])
    op.create_index('ix_evidence_number', 'evidence', ['evidence_number'], unique=True)
    op.create_index('ix_evidence_current_custodian', 'evidence', ['current_custodian_id'])
    op.create_index('ix_evidence_status', 'evidence', ['status'])
    op.create_index('ix_evidence_integrity_status', 'evidence', ['integrity_status'])
    op.create_index('ix_evidence_type', 'evidence', ['evidence_type'])

    # 2. Create evidence_custody_events table
    op.create_table(
        'evidence_custody_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('evidence_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('evidence.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cases.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('from_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('to_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('location', sa.String(500), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('file_hash_at_event', sa.String(64), nullable=True),
        sa.Column('previous_event_hash', sa.String(64), nullable=False),
        sa.Column('event_hash', sa.String(64), nullable=False),
        sa.Column('acknowledgement_status', sa.String(50), nullable=False, server_default='acknowledged'),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('event_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint(
            "event_type IN ('registered', 'transfer_initiated', 'transfer_acknowledged', 'transfer_cancelled', 'in_analysis', 'analysis_completed', 'analyzed', 'submitted_to_court', 'archived', 'integrity_verified')",
            name='chk_custody_event_type',
        ),
        sa.CheckConstraint(
            "acknowledgement_status IN ('acknowledged', 'pending', 'cancelled')",
            name='chk_custody_ack_status',
        ),
    )
    op.create_index('ix_custody_evidence_id', 'evidence_custody_events', ['evidence_id'])
    op.create_index('ix_custody_case_id', 'evidence_custody_events', ['case_id'])
    op.create_index('ix_custody_from_user', 'evidence_custody_events', ['from_user_id'])
    op.create_index('ix_custody_to_user', 'evidence_custody_events', ['to_user_id'])
    op.create_index('ix_custody_created_at', 'evidence_custody_events', ['created_at'])
    op.create_index('ix_custody_event_hash', 'evidence_custody_events', ['event_hash'])


def downgrade() -> None:
    op.drop_table('evidence_custody_events')
    op.drop_table('evidence')
