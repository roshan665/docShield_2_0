"""
Authentication and RBAC Pydantic Schemas
Defines request and response payload validations.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# -----------------------------------------------------------------------------
# Role & Permission Schemas
# -----------------------------------------------------------------------------

class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    resource: str
    action: str
    description: str | None = None


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    display_name: str
    description: str | None = None
    is_system_role: bool


class RoleDetailResponse(RoleResponse):
    permissions: list[PermissionResponse] = []


# -----------------------------------------------------------------------------
# User Schemas
# -----------------------------------------------------------------------------

class UserBase(BaseModel):
    employee_id: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: str | None = Field(None, max_length=20)
    department: str | None = Field(None, max_length=100)
    designation: str | None = Field(None, max_length=100)


class UserCreateRequest(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    role_id: UUID | None = None
    role_name: str | None = None


class UserUpdateRequest(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=255)
    phone: str | None = Field(None, max_length=20)
    department: str | None = Field(None, max_length=100)
    designation: str | None = Field(None, max_length=100)
    role_id: UUID | None = None
    role_name: str | None = None


class UserStatusUpdateRequest(BaseModel):
    is_active: bool | None = None
    is_locked: bool | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: str
    email: str
    full_name: str
    role: str
    role_display_name: str
    department: str | None = None
    designation: str | None = None
    is_active: bool
    is_locked: bool
    last_login: datetime | None = None
    created_at: datetime
    permissions: list[str] = []


# -----------------------------------------------------------------------------
# Auth Schemas
# -----------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class AdminResetPasswordResponse(BaseModel):
    message: str
    user_id: UUID
    temporary_password: str
