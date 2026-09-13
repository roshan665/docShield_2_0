"""
Case Management Pydantic Schemas
Defines request and response data contracts for Case & Case Membership operations.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CaseCreateRequest(BaseModel):
    case_number: str = Field(..., min_length=3, max_length=100, description="Unique case number e.g. CR-2026-001")
    fir_number: str | None = Field(None, max_length=100, description="Optional FIR reference e.g. FIR-2026-101")
    title: str = Field(..., min_length=3, max_length=500, description="Case title")
    description: str | None = Field(None, description="Detailed case brief")
    priority: str = Field("medium", pattern="^(critical|high|medium|low)$")
    category: str | None = Field(None, max_length=100)
    police_station: str | None = Field(None, max_length=255)
    district: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)


class CaseUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=500)
    description: str | None = None
    priority: str | None = Field(None, pattern="^(critical|high|medium|low)$")
    category: str | None = Field(None, max_length=100)
    police_station: str | None = Field(None, max_length=255)
    district: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    status: str | None = Field(None, pattern="^(open|under_investigation|pending_review|pending_legal|closed|archived)$")


class CaseStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(open|under_investigation|pending_review|pending_legal|closed|archived)$")
    reason: str | None = Field(None, description="Reason for status transition")


class CaseMemberAddRequest(BaseModel):
    user_id: UUID
    role_in_case: str = Field("investigator", pattern="^(lead_investigator|investigator|forensic_analyst|legal_counsel|supervisor|reviewer)$")


class CaseMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    user_id: UUID
    role_in_case: str
    added_by: UUID | None = None
    added_at: datetime
    is_active: bool
    user_full_name: str | None = None
    user_email: str | None = None
    user_employee_id: str | None = None
    user_role: str | None = None


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_number: str
    fir_number: str | None = None
    title: str
    description: str | None = None
    status: str
    priority: str
    category: str | None = None
    police_station: str | None = None
    district: str | None = None
    state: str | None = None
    investigating_officer_id: UUID | None = None
    investigating_officer_name: str | None = None
    created_by: UUID
    created_by_name: str | None = None
    closed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    members_count: int = 0
    user_role_in_case: str | None = None

