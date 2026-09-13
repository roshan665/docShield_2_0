"""
Pydantic Schemas for Legal Court Export & Cryptographic Manifests
Conforms to Phase 8 requirements.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExportCreateRequest(BaseModel):
    """Payload to initiate a case export generation."""
    include_files: bool = Field(default=True, description="Whether to bundle binary files in ZIP")
    reason: str | None = Field(default=None, max_length=500, description="Court or investigative purpose")


class ExportFileEntry(BaseModel):
    """File entry within cryptographic manifest."""
    path: str
    sha256: str
    size_bytes: int


class ExportManifest(BaseModel):
    """Cryptographic manifest documenting all files and hashes."""
    case_id: UUID
    case_number: str
    export_id: UUID
    generated_at: datetime
    generated_by_id: UUID | None
    generated_by_name: str
    manifest_hash: str
    files: list[ExportFileEntry]


class ExportVerificationSummary(BaseModel):
    """Pre-export live cryptographic verification summary."""
    documents_verified: int
    evidence_verified: int
    custody_events_verified: int
    audit_events_verified: int
    all_verified: bool
    failures: list[dict[str, Any]] = Field(default_factory=list)


class CaseExportResponse(BaseModel):
    """Response payload for court-ready export package."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    case_number: str | None = None
    requested_by_id: UUID | None = None
    file_name: str
    file_size_bytes: int
    file_hash_sha256: str
    manifest_hash_sha256: str
    integrity_status: str
    export_status: str
    verification_summary: dict[str, Any] | None = None
    manifest_data: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class CaseExportListResponse(BaseModel):
    """Paginated list of case exports."""
    items: list[CaseExportResponse]
    total: int

