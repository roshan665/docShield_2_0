"""
Case and Case Membership SQLAlchemy Models
Conforms strictly to DATABASE_DESIGN.md and Phase 3 requirements.
"""

from sqlalchemy import (
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

# Allowed lifecycle states and priorities
CASE_STATUSES = [
    "open",
    "under_investigation",
    "pending_review",
    "pending_legal",
    "closed",
    "archived",
]

CASE_PRIORITIES = [
    "critical",
    "high",
    "medium",
    "low",
]

CASE_MEMBER_ROLES = [
    "lead_investigator",
    "investigator",
    "forensic_analyst",
    "legal_counsel",
    "supervisor",
    "reviewer",
]


class Case(BaseModel):
    """
    Case entity representing a legal / criminal investigation lifecycle.
    """

    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({', '.join(f"'{s}'" for s in CASE_STATUSES)})",
            name="chk_cases_status",
        ),
        CheckConstraint(
            f"priority IN ({', '.join(f"'{p}'" for p in CASE_PRIORITIES)})",
            name="chk_cases_priority",
        ),
    )

    case_number = Column(String(100), unique=True, nullable=False, index=True)
    fir_number = Column(String(100), nullable=True, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="open", nullable=False, index=True)
    priority = Column(String(20), default="medium", nullable=False, index=True)
    category = Column(String(100), nullable=True)
    police_station = Column(String(255), nullable=True)
    district = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    investigating_officer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    closed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    investigating_officer = relationship("User", foreign_keys=[investigating_officer_id])
    members = relationship(
        "CaseMember",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    audit_events = relationship(
        "AuditEvent",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="AuditEvent.timestamp.desc()",
    )
    documents = relationship(
        "Document",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="Document.created_at.desc()",
    )
    evidence = relationship(
        "Evidence",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="Evidence.created_at.desc()",
    )



class CaseMember(BaseModel):
    """
    Explicit case team membership linking users to cases with specific roles.
    Enforces that users have NO global case access.
    """

    __tablename__ = "case_members"
    __table_args__ = (
        CheckConstraint(
            f"role_in_case IN ({', '.join(f"'{r}'" for r in CASE_MEMBER_ROLES)})",
            name="chk_case_members_role",
        ),
        # Partial unique index ensuring a user is actively enrolled in a case at most once
        Index(
            "uq_active_case_member",
            "case_id",
            "user_id",
            unique=True,
            postgresql_where=Column("is_active").is_(True),
        ),
        Index("idx_case_members_user_active", "user_id", "is_active"),
    )

    case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_in_case = Column(String(50), nullable=False)
    added_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    added_at = Column(DateTime(timezone=True), nullable=False)
    removed_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    case = relationship("Case", back_populates="members")
    user = relationship("User", foreign_keys=[user_id], lazy="selectin")
    assigner = relationship("User", foreign_keys=[added_by])

