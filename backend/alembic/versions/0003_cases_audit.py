"""Create cases, case_members, and audit_events tables

Revision ID: 0003_cases_audit
Revises: 0002_auth_rbac
Create Date: 2026-09-12 01:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0003_cases_audit'
down_revision: str | None = '0002_auth_rbac'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. cases table
    op.create_table(
        'cases',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('case_number', sa.String(100), nullable=False, unique=True),
        sa.Column('fir_number', sa.String(100), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='open'),
        sa.Column('priority', sa.String(20), nullable=False, server_default='medium'),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('police_station', sa.String(255), nullable=True),
        sa.Column('district', sa.String(100), nullable=True),
        sa.Column('state', sa.String(100), nullable=True),
        sa.Column('investigating_officer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('open', 'under_investigation', 'pending_review', 'pending_legal', 'closed', 'archived')",
            name='chk_cases_status',
        ),
        sa.CheckConstraint(
            "priority IN ('critical', 'high', 'medium', 'low')",
            name='chk_cases_priority',
        ),
    )
    op.create_index('ix_cases_case_number', 'cases', ['case_number'], unique=True)
    op.create_index('ix_cases_fir_number', 'cases', ['fir_number'])
    op.create_index('ix_cases_status', 'cases', ['status'])
    op.create_index('ix_cases_priority', 'cases', ['priority'])
    op.create_index('ix_cases_created_by', 'cases', ['created_by'])
    op.create_index('ix_cases_investigating_officer_id', 'cases', ['investigating_officer_id'])

    # 2. case_members table
    op.create_table(
        'case_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role_in_case', sa.String(50), nullable=False),
        sa.Column('added_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('added_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('removed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "role_in_case IN ('lead_investigator', 'investigator', 'forensic_analyst', 'legal_counsel', 'supervisor', 'reviewer')",
            name='chk_case_members_role',
        ),
    )
    op.create_index('ix_case_members_case_id', 'case_members', ['case_id'])
    op.create_index('ix_case_members_user_id', 'case_members', ['user_id'])
    op.create_index('ix_case_members_is_active', 'case_members', ['is_active'])
    op.create_index('idx_case_members_user_active', 'case_members', ['user_id', 'is_active'])
    # Partial unique index for active membership
    op.create_index(
        'uq_active_case_member',
        'case_members',
        ['case_id', 'user_id'],
        unique=True,
        postgresql_where=sa.text('is_active = true'),
    )

    # 3. audit_events table
    op.create_table(
        'audit_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cases.id', ondelete='SET NULL'), nullable=True),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.Column('result', sa.String(20), nullable=False, server_default='success'),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('session_id', sa.String(255), nullable=True),
        sa.Column('previous_event_hash', sa.String(64), nullable=True),
        sa.Column('event_hash', sa.String(64), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "result IN ('success', 'failure', 'denied')",
            name='chk_audit_events_result',
        ),
    )
    op.create_index('ix_audit_events_actor_id', 'audit_events', ['actor_id'])
    op.create_index('ix_audit_events_action', 'audit_events', ['action'])
    op.create_index('ix_audit_events_resource_type', 'audit_events', ['resource_type'])
    op.create_index('ix_audit_events_resource_id', 'audit_events', ['resource_id'])
    op.create_index('ix_audit_events_case_id', 'audit_events', ['case_id'])
    op.create_index('ix_audit_events_event_hash', 'audit_events', ['event_hash'])
    op.create_index('ix_audit_events_timestamp', 'audit_events', ['timestamp'])
    op.create_index('idx_audit_resource', 'audit_events', ['resource_type', 'resource_id'])
    op.create_index('idx_audit_case_time', 'audit_events', ['case_id', 'timestamp'])


def downgrade() -> None:
    op.drop_table('audit_events')
    op.drop_table('case_members')
    op.drop_table('cases')

