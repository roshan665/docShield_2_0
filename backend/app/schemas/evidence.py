"""
Evidence and Chain of Custody Pydantic Schemas
Defines request and response contracts conforming strictly to SIH 26190 API specification.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EvidenceRegisterRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=500, description="Evidence title/name")
    description: str | None = Field(None, max_length=5000, description="Detailed evidence description")
    evidence_type: str = Field("digital_document", description="Controlled evidence category")
    sensitivity_level: str = Field("standard", description="standard, sensitive, highly_sensitive, classified")
    document_id: UUID | None = Field(None, description="Optional associated case document ID")
    collection_date: datetime | None = Field(None, description="Date and time evidence was seized/collected")
    collection_location: str | None = Field(None, max_length=1000, description="Location where evidence was gathered")
    source: str | None = Field(None, max_length=500, description="Source individual, agency, or device")
    notes: str | None = Field(None, max_length=2000, description="Registration notes or panchnama reference")


class EvidenceUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=500)
    description: str | None = Field(None, max_length=5000)
    sensitivity_level: str | None = Field(None)
    collection_location: str | None = Field(None, max_length=1000)
    source: str | None = Field(None, max_length=500)


class EvidenceStatusTransitionRequest(BaseModel):
    target_status: str = Field(..., description="Target lifecycle state")
    reason: str = Field(..., min_length=3, max_length=1000, description="Legal/investigative reason for state transition")
    location: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=2000)


class EvidenceCustodyTransferRequest(BaseModel):
    to_user_id: UUID = Field(..., description="Target recipient officer ID who must be an active case member")
    reason: str = Field(..., min_length=5, max_length=1000, description="Official purpose of custody handover")
    location: str | None = Field(None, max_length=500, description="Transfer location, e.g. Cyber Forensic Lab")
    notes: str | None = Field(None, max_length=2000, description="Handover notes or parcel seal numbers")


class EvidenceCustodyAcknowledgeRequest(BaseModel):
    location: str | None = Field(None, max_length=500, description="Receipt location")
    notes: str | None = Field(None, max_length=2000, description="Receipt notes, verification acknowledgment")


class CustodyEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    evidence_id: UUID
    case_id: UUID
    event_type: str
    from_user_id: UUID | None = None
    to_user_id: UUID
    from_user_name: str | None = None
    to_user_name: str | None = None
    reason: str
    location: str | None = None
    notes: str | None = None
    file_hash_at_event: str | None = None
    previous_event_hash: str
    event_hash: str
    acknowledgement_status: str
    acknowledged_at: datetime | None = None
    event_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    document_id: UUID | None = None
    evidence_number: str
    title: str
    description: str | None = None
    evidence_type: str
    status: str
    sensitivity_level: str
    original_file_hash: str | None = None
    current_file_hash: str | None = None
    integrity_status: str
    current_custodian_id: UUID
    current_custodian_name: str | None = None
    pending_custodian_id: UUID | None = None
    pending_custodian_name: str | None = None
    transfer_pending: bool = False
    transfer_reason: str | None = None
    storage_key: str | None = None
    storage_bucket: str | None = None
    mime_type: str | None = None
    file_size_bytes: int | None = None
    collection_date: datetime | None = None
    collection_location: str | None = None
    source: str | None = None
    registered_by_id: UUID
    registered_by_name: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    archived_at: datetime | None = None
    custody_events_count: int = 0


class CustodyChainVerificationResponse(BaseModel):
    valid: bool
    events_checked: int
    first_invalid_event: str | None = None
    reason: str | None = None
    genesis_hash: str | None = None
    tip_hash: str | None = None


class EvidenceIntegrityResponse(BaseModel):
    evidence_id: UUID
    original_hash: str | None = None
    current_hash: str | None = None
    match: bool
    integrity_status: str
    checked_at: datetime

