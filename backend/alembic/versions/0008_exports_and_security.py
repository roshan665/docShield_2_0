"""Phase 8: Create case_exports table and enhance security_events

Revision ID: 0008_exports_and_security
Revises: 0007_embeddings_refine
Create Date: 2026-09-12 14:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0008_exports_and_security'
down_revision: str | None = '0007_embeddings_refine'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Enhance security_events table with category, case_id, resource_type, resource_id
    op.add_column('security_events', sa.Column('category', sa.String(50), nullable=True))
    op.add_column(
        'security_events',
        sa.Column(
            'case_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('cases.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.add_column('security_events', sa.Column('resource_type', sa.String(50), nullable=True))
    op.add_column('security_events', sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True))

    op.create_index('ix_security_events_category', 'security_events', ['category'])
    op.create_index('ix_security_events_case_id', 'security_events', ['case_id'])

    # 2. Create case_exports table
    op.create_table(
        'case_exports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'case_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('cases.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'requested_by_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('storage_path', sa.String(512), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('file_hash_sha256', sa.String(64), nullable=False),
        sa.Column('manifest_hash_sha256', sa.String(64), nullable=False),
        sa.Column('integrity_status', sa.String(32), nullable=False, server_default='verified'),
        sa.Column('export_status', sa.String(32), nullable=False, server_default='completed'),
        sa.Column('verification_summary', postgresql.JSONB(), nullable=True),
        sa.Column('manifest_data', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_case_exports_case_id', 'case_exports', ['case_id'])
    op.create_index('ix_case_exports_requested_by_id', 'case_exports', ['requested_by_id'])
    op.create_index('ix_case_exports_integrity_status', 'case_exports', ['integrity_status'])
    op.create_index('ix_case_exports_export_status', 'case_exports', ['export_status'])
    op.create_index('ix_case_exports_created_at', 'case_exports', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_case_exports_created_at', table_name='case_exports')
    op.drop_index('ix_case_exports_export_status', table_name='case_exports')
    op.drop_index('ix_case_exports_integrity_status', table_name='case_exports')
    op.drop_index('ix_case_exports_requested_by_id', table_name='case_exports')
    op.drop_index('ix_case_exports_case_id', table_name='case_exports')
    op.drop_table('case_exports')

    op.drop_index('ix_security_events_case_id', table_name='security_events')
    op.drop_index('ix_security_events_category', table_name='security_events')
    op.drop_column('security_events', 'resource_id')
    op.drop_column('security_events', 'resource_type')
    op.drop_column('security_events', 'case_id')
    op.drop_column('security_events', 'category')

