"""
Case Export and Cryptographic Manifest SQLAlchemy Models
Conforms strictly to Phase 8 legal court export requirements.
"""

from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class CaseExport(BaseModel):
    """
    Immutable record of a court-ready case export package.
    Stores metadata, cryptographic manifest hash, and package SHA-256.
    """

    __tablename__ = "case_exports"

    case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    file_name = Column(String(255), nullable=False)
    storage_path = Column(String(512), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False, default=0)
    file_hash_sha256 = Column(String(64), nullable=False)
    manifest_hash_sha256 = Column(String(64), nullable=False)
    integrity_status = Column(String(32), nullable=False, default="verified", index=True)
    export_status = Column(String(32), nullable=False, default="completed", index=True)
    verification_summary = Column(JSONB, nullable=True)
    manifest_data = Column(JSONB, nullable=True)

    # Relationships
    case = relationship("Case", backref="exports")
    requested_by = relationship("User", foreign_keys=[requested_by_id])

    __table_args__ = (
        Index("ix_case_exports_case_created", "case_id", "created_at"),
    )

