"""
Audit & Verification Pydantic Schemas
Contracts for audit log querying and cryptographic chain verification.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_id: UUID | None = None
    actor_name: str | None = None
    actor_email: str | None = None
    action: str
    resource_type: str
    resource_id: UUID | None = None
    case_id: UUID | None = None
    details: dict[str, Any] | None = None
    result: str
    ip_address: str | None = None
    previous_event_hash: str | None = None
    event_hash: str
    timestamp: datetime


class AuditVerificationResponse(BaseModel):
    valid: bool
    events_checked: int
    first_invalid_event: str | None = None
    reason: str | None = None


class CaseTimelineEventResponse(BaseModel):
    id: UUID
    timestamp: datetime
    action: str
    actor_name: str | None = None
    actor_email: str | None = None
    description: str
    details: dict[str, Any] | None = None
    result: str

