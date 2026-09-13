"""
Pydantic Schemas for Security Event Monitoring & Incident Handling
Conforms to Phase 8 requirements.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SecurityEventResponse(BaseModel):
    """Safe structured security event details."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    severity: str
    category: str | None = None
    actor_id: UUID | None = None
    case_id: UUID | None = None
    resource_type: str | None = None
    resource_id: UUID | None = None
    ip_address: str | None = None
    details: dict[str, Any] | None = None
    resolved: bool = False
    resolved_by: UUID | None = None
    resolved_at: datetime | None = None
    created_at: datetime


class SecurityEventListResponse(BaseModel):
    """Paginated security events log."""
    items: list[SecurityEventResponse]
    total: int


class SecurityMetricsResponse(BaseModel):
    """Aggregated security metrics for administrative monitoring dashboard."""
    total_events: int
    critical_events: int
    high_events: int
    medium_events: int
    low_events: int
    info_events: int
    failed_logins: int
    locked_accounts: int
    integrity_violations: int
    malicious_files: int
    unauthorized_access_attempts: int
    rate_limit_events: int
    category_breakdown: dict[str, int]
    recent_critical_events: list[SecurityEventResponse]


class TamperSimulationRequest(BaseModel):
    """Demo simulation request to safely demonstrate live tamper detection."""
    target_type: str = Field(description="'document' or 'evidence'")
    target_id: UUID = Field(description="UUID of the document or evidence to tamper with")


class TamperSimulationResponse(BaseModel):
    """Result of demo tamper simulation."""
    message: str
    target_type: str
    target_id: UUID
    previous_hash: str
    tampered_payload_hash: str
    security_event_id: UUID

