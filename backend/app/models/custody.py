"""
Evidence Custody Event SQLAlchemy Model
Implements immutable, cryptographically hash-chained chain of custody ledger events.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

CUSTODY_EVENT_TYPES = [
    "registered",
    "transfer_initiated",
    "transfer_acknowledged",
    "transfer_cancelled",
    "in_analysis",
    "analysis_completed",
    "submitted_to_court",
    "archived",
    "integrity_verified",
]

CUSTODY_ACKNOWLEDGEMENT_STATUSES = [
    "acknowledged",
    "pending",
    "cancelled",
]


class EvidenceCustodyEvent(Base, UUIDPrimaryKeyMixin):
    """
    Immutable custody ledger event.
    Linked in a sequential cryptographic hash chain per evidence item.
    """

    __tablename__ = "evidence_custody_events"
    __table_args__ = (
        CheckConstraint(
            f"event_type IN ({', '.join(f"'{t}'" for t in CUSTODY_EVENT_TYPES)})",
            name="chk_custody_event_type",
        ),
        CheckConstraint(
            f"acknowledgement_status IN ({', '.join(f"'{s}'" for s in CUSTODY_ACKNOWLEDGEMENT_STATUSES)})",
            name="chk_custody_ack_status",
        ),
        Index("ix_custody_evidence_id", "evidence_id"),
        Index("ix_custody_case_id", "case_id"),
        Index("ix_custody_from_user", "from_user_id"),
        Index("ix_custody_to_user", "to_user_id"),
        Index("ix_custody_created_at", "created_at"),
        Index("ix_custody_event_hash", "event_hash"),
    )

    evidence_id = Column(
        UUID(as_uuid=True),
        ForeignKey("evidence.id", ondelete="RESTRICT"),
        nullable=False,
    )
    case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="RESTRICT"),
        nullable=False,
    )

    event_type = Column(String(50), nullable=False)
    from_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,  # None for initial evidence registration
    )
    to_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    reason = Column(Text, nullable=False)
    location = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)

    # Cryptographic Fingerprints & Chain
    file_hash_at_event = Column(String(64), nullable=True)
    previous_event_hash = Column(String(64), nullable=False)
    event_hash = Column(String(64), nullable=False)

    # Handover Status
    acknowledgement_status = Column(String(50), nullable=False, default="acknowledged")
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    event_metadata = Column(JSONB, nullable=False, default=dict)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    evidence = relationship("Evidence", back_populates="custody_events")
    case = relationship("Case")
    from_user = relationship("User", foreign_keys=[from_user_id])
    to_user = relationship("User", foreign_keys=[to_user_id])

