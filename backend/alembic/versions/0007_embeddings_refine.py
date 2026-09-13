"""Phase 7: Refine document_embeddings for version-isolation, stable chunk IDs, and searchability

Revision ID: 0007_phase7_embeddings_refinement
Revises: 0006_ai_pipeline
Create Date: 2026-09-12 12:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0007_embeddings_refine'
down_revision: str | None = '0006_ai_pipeline'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add version_id, chunk_id, model_name, vector_dimensions, is_searchable
    op.add_column(
        'document_embeddings',
        sa.Column(
            'version_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('document_versions.id', ondelete='CASCADE'),
            nullable=True,
        ),
    )
    op.add_column(
        'document_embeddings',
        sa.Column('chunk_id', sa.String(120), nullable=True),
    )
    op.add_column(
        'document_embeddings',
        sa.Column('model_name', sa.String(100), nullable=False, server_default='models/text-embedding-004'),
    )
    op.add_column(
        'document_embeddings',
        sa.Column('vector_dimensions', sa.Integer(), nullable=False, server_default='768'),
    )
    op.add_column(
        'document_embeddings',
        sa.Column('is_searchable', sa.Boolean(), nullable=False, server_default=sa.text('true')),
    )

    # 2. Backfill existing rows if any from document_versions
    op.execute("""
        UPDATE document_embeddings de
        SET version_id = dv.id,
            chunk_id = 'DOC-' || UPPER(SUBSTRING(de.document_id::text, 1, 8)) || '-V' || dv.version_number::text || '-C' || de.chunk_index::text
        FROM (
            SELECT DISTINCT ON (document_id) id, document_id, version_number
            FROM document_versions
            ORDER BY document_id, version_number DESC
        ) dv
        WHERE de.document_id = dv.document_id AND de.version_id IS NULL;
    """)

    # 3. Add indexes and unique constraint
    op.create_index('ix_document_embeddings_version_id', 'document_embeddings', ['version_id'])
    op.create_index('ix_document_embeddings_is_searchable', 'document_embeddings', ['is_searchable'])
    op.create_index('ix_document_embeddings_chunk_id', 'document_embeddings', ['chunk_id'])
    op.create_unique_constraint(
        'uq_version_chunk_model',
        'document_embeddings',
        ['version_id', 'chunk_index', 'model_name'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_version_chunk_model', 'document_embeddings', type_='unique')
    op.drop_index('ix_document_embeddings_chunk_id', table_name='document_embeddings')
    op.drop_index('ix_document_embeddings_is_searchable', table_name='document_embeddings')
    op.drop_index('ix_document_embeddings_version_id', table_name='document_embeddings')
    op.drop_column('document_embeddings', 'is_searchable')
    op.drop_column('document_embeddings', 'vector_dimensions')
    op.drop_column('document_embeddings', 'model_name')
    op.drop_column('document_embeddings', 'chunk_id')
    op.drop_column('document_embeddings', 'version_id')
