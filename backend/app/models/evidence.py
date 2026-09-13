"""
Evidence SQLAlchemy Model
Implements evidence entity, metadata, integrity states, and custodian tracking.
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel

# Controlled Evidence Categories
EVIDENCE_TYPES = [
    "digital_document",
    "image",
    "video",
    "audio",
    "device",
    "forensic_artifact",
    "physical_evidence",
    "other",
]

# Strict Evidence Lifecycle States
EVIDENCE_STATUSES = [
    "registered",
    "in_custody",
    "in_analysis",
    "analyzed",
    "submitted_to_court",
    "archived",
]

EVIDENCE_SENSITIVITY = [
    "standard",
    "sensitive",
    "highly_sensitive",
    "confidential",
    "secret",
    "classified",
]

EVIDENCE_INTEGRITY_STATUSES = [
    "verified",
    "compromised",
    "pending",
]


class Evidence(BaseModel):
    """
    Evidence entity registered within an authorized case context.
    Tracks authoritative hashes, custody states, and physical/digital metadata.
    """

    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint(
            f"evidence_type IN ({', '.join(f"'{t}'" for t in EVIDENCE_TYPES)})",
            name="chk_evidence_type",
        ),
        CheckConstraint(
            f"status IN ({', '.join(f"'{s}'" for s in EVIDENCE_STATUSES)})",
            name="chk_evidence_status",
        ),
        CheckConstraint(
            f"sensitivity_level IN ({', '.join(f"'{sl}'" for sl in EVIDENCE_SENSITIVITY)})",
            name="chk_evidence_sensitivity",
        ),
        CheckConstraint(
            f"integrity_status IN ({', '.join(f"'{i}'" for i in EVIDENCE_INTEGRITY_STATUSES)})",
            name="chk_evidence_integrity",
        ),
        Index("ix_evidence_case_id", "case_id"),
        Index("ix_evidence_number", "evidence_number", unique=True),
        Index("ix_evidence_current_custodian", "current_custodian_id"),
        Index("ix_evidence_status", "status"),
        Index("ix_evidence_integrity_status", "integrity_status"),
        Index("ix_evidence_type", "evidence_type"),
    )

    case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    evidence_number = Column(String(100), unique=True, nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    evidence_type = Column(String(100), nullable=False, default="digital_document")
    status = Column(String(50), nullable=False, default="registered")
    sensitivity_level = Column(String(50), nullable=False, default="standard")

    # Authoritative Cryptographic Hashes
    original_file_hash = Column(String(64), nullable=True)  # Immutable authoritative SHA-256
    current_file_hash = Column(String(64), nullable=True)   # Latest evaluated SHA-256
    integrity_status = Column(String(20), nullable=False, default="verified")

    # Custody Tracking & Two-Phase Handover
    current_custodian_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    pending_custodian_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    transfer_pending = Column(Boolean, nullable=False, default=False)
    transfer_reason = Column(Text, nullable=True)

    # Storage References (for standalone digital evidence)
    storage_key = Column(String(500), nullable=True)
    storage_bucket = Column(String(100), nullable=True)
    mime_type = Column(String(100), nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)

    # Collection Metadata
    collection_date = Column(DateTime(timezone=True), nullable=True)
    collection_location = Column(Text, nullable=True)
    source = Column(String(500), nullable=True)

    # Creator & Archival Tracking
    registered_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    case = relationship("Case", back_populates="evidence")
    document = relationship("Document")
    current_custodian = relationship("User", foreign_keys=[current_custodian_id])
    pending_custodian = relationship("User", foreign_keys=[pending_custodian_id])
    registered_by = relationship("User", foreign_keys=[registered_by_id])
    custody_events = relationship(
        "EvidenceCustodyEvent",
        back_populates="evidence",
        cascade="all, delete-orphan",
        order_by="EvidenceCustodyEvent.created_at.asc()",
    )
