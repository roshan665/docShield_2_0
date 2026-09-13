"""
Document Pydantic Schemas
Defines request and response serialization models for document management and versioning.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentVersionResponse(BaseModel):
    """Immutable document version response representation."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    version_number: int
    file_hash_sha256: str
    file_size_bytes: int
    mime_type: str
    original_filename: str
    sanitized_filename: str
    change_reason: str | None = None
    created_by: UUID
    created_by_name: str | None = None
    is_original: bool
    integrity_status: str
    created_at: datetime
    last_verified_at: datetime | None = None


class DocumentResponse(BaseModel):
    """Document entity response model."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    title: str
    description: str | None = None
    document_type: str
    classification: str
    status: str
    current_version_id: UUID | None = None
    current_version: DocumentVersionResponse | None = None
    original_filename: str | None = None
    mime_type: str | None = None
    file_size_bytes: int | None = None
    file_hash_sha256: str | None = None
    uploaded_by: UUID
    uploaded_by_name: str | None = None
    versions_count: int = 1
    created_at: datetime
    updated_at: datetime | None = None


class DocumentIntegrityResponse(BaseModel):
    """Result of live cryptographic SHA-256 verification against stored object."""
    document_id: UUID
    version_id: UUID
    version_number: int
    stored_hash: str
    computed_hash: str
    match: bool
    integrity_status: str
    verified_at: datetime
