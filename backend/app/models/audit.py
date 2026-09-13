"""
Immutable Audit Trail SQLAlchemy Models
Establishes append-only, tamper-evident hash-chained audit event storage.
Conforms strictly to DATABASE_DESIGN.md section 3.14.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class AuditEvent(BaseModel):
    """
    Append-only tamper-evident audit record cryptographically linked to predecessor.
    H_n = SHA-256(canonical_data || H_(n-1))
    """

    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(
            "result IN ('success', 'failure', 'denied')",
            name="chk_audit_events_result",
        ),
        Index("idx_audit_resource", "resource_type", "resource_id"),
        Index("idx_audit_case_time", "case_id", "timestamp"),
    )

    actor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False, index=True)
    resource_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    details = Column(JSONB, nullable=True)
    result = Column(String(20), default="success", nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    session_id = Column(String(255), nullable=True)
    previous_event_hash = Column(String(64), nullable=True)
    event_hash = Column(String(64), nullable=False, index=True)
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    # Relationships
    actor = relationship("User", foreign_keys=[actor_id], lazy="selectin")
    case = relationship("Case", back_populates="audit_events", foreign_keys=[case_id])

