"""
Document and Document Version SQLAlchemy Models
Implements immutable document versioning and S3 storage references.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, BaseModel, UUIDPrimaryKeyMixin

# Standard legal document categories
DOCUMENT_TYPES = [
    "fir",
    "police_report",
    "investigation_report",
    "witness_statement",
    "charge_sheet",
    "court_filing",
    "evidence_record",
    "forensic_report",
    "legal_notice",
    "judgment",
    "supporting_document",
    "other",
]

DOCUMENT_CLASSIFICATIONS = [
    "public",
    "internal",
    "confidential",
    "secret",
    "top_secret",
]

DOCUMENT_STATUSES = [
    "uploading",
    "processing",
    "processed",
    "failed",
    "archived",
]


class Document(BaseModel):
    """
    Document entity representing a logical legal record or filing within a Case.
    Points to an immutable current_version_id.
    """

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            f"document_type IN ({', '.join(f"'{t}'" for t in DOCUMENT_TYPES)})",
            name="chk_documents_type",
        ),
        CheckConstraint(
            f"classification IN ({', '.join(f"'{c}'" for c in DOCUMENT_CLASSIFICATIONS)})",
            name="chk_documents_classification",
        ),
        CheckConstraint(
            f"status IN ({', '.join(f"'{s}'" for s in DOCUMENT_STATUSES)})",
            name="chk_documents_status",
        ),
        Index("ix_documents_case_id", "case_id"),
        Index("ix_documents_type", "document_type"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_created_at", "created_at"),
    )

    case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    document_type = Column(String(100), nullable=False, default="other")
    classification = Column(String(50), nullable=False, default="internal")
    status = Column(String(50), nullable=False, default="processed")

    # Circular FK handled via use_alter=True to allow NULL initialization on initial insert
    current_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="SET NULL", use_alter=True, name="fk_documents_current_version_id"),
        nullable=True,
    )

    original_filename = Column(String(500), nullable=True)
    mime_type = Column(String(100), nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)

    uploaded_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    is_evidence = Column(Boolean, nullable=False, default=False)
    evidence_id = Column(UUID(as_uuid=True), nullable=True)
    ai_processed = Column(Boolean, nullable=False, default=False)
    ai_classification = Column(String(100), nullable=True)
    ai_confidence = Column(Float, nullable=True)
    ocr_text = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    ai_processing_error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(UTC), nullable=True)

    # Relationships
    case = relationship("Case", back_populates="documents")
    uploader = relationship("User", foreign_keys=[uploaded_by])
    current_version = relationship(
        "DocumentVersion",
        foreign_keys=[current_version_id],
        post_update=True,
    )
    versions = relationship(
        "DocumentVersion",
        foreign_keys="DocumentVersion.document_id",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="desc(DocumentVersion.version_number)",
    )
    metadata_entries = relationship(
        "DocumentMetadata",
        foreign_keys="DocumentMetadata.document_id",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    entities = relationship(
        "ExtractedEntity",
        foreign_keys="ExtractedEntity.document_id",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    embeddings = relationship(
        "DocumentEmbedding",
        foreign_keys="DocumentEmbedding.document_id",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentVersion(Base, UUIDPrimaryKeyMixin):
    """
    Immutable version of a Document.
    Each version has its own distinct storage key, SHA-256 hash, and metadata.
    """

    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_version_number"),
        CheckConstraint(
            "integrity_status IN ('verified', 'compromised', 'pending')",
            name="chk_doc_version_integrity",
        ),
        Index("ix_document_versions_document_id", "document_id"),
        Index("ix_document_versions_file_hash", "file_hash_sha256"),
        Index("ix_document_versions_integrity", "integrity_status"),
    )

    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number = Column(Integer, nullable=False)
    storage_key = Column(String(500), nullable=False)
    storage_bucket = Column(String(100), nullable=False)
    file_hash_sha256 = Column(String(64), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=False)
    original_filename = Column(String(500), nullable=False)
    sanitized_filename = Column(String(500), nullable=False)
    change_reason = Column(Text, nullable=True)

    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    is_original = Column(Boolean, nullable=False, default=False)
    integrity_status = Column(String(20), nullable=False, default="verified")
    last_verified_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    document = relationship("Document", foreign_keys=[document_id], back_populates="versions")
    creator = relationship("User", foreign_keys=[created_by])
    embeddings = relationship(
        "DocumentEmbedding",
        foreign_keys="DocumentEmbedding.version_id",
        back_populates="version",
        cascade="all, delete-orphan",
    )
