"""
User Administration HTTP Endpoints
Handles user provisioning, listing, status modifications, and admin password resets.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.exceptions import PermissionDeniedException
from app.models.auth import User
from app.modules.auth.dependencies import (
    get_current_user,
    get_user_service,
    require_permission,
    require_role,
)
from app.modules.users.service import UserService
from app.schemas.auth import (
    AdminResetPasswordResponse,
    UserCreateRequest,
    UserResponse,
    UserStatusUpdateRequest,
    UserUpdateRequest,
)

users_router = APIRouter(prefix="/users", tags=["Users"])
admin_router = APIRouter(prefix="/admin/users", tags=["Admin Users"])


# -----------------------------------------------------------------------------
# /api/v1/users endpoints
# -----------------------------------------------------------------------------

@users_router.get("", response_model=list[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    role_id: UUID | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(require_permission("users", "read")),
) -> list[UserResponse]:
    """Lists users with filtering and search (Admin role)."""
    users, _ = await user_service.list_users(
        skip=skip, limit=limit, role_id=role_id, is_active=is_active, search=search
    )
    return users


@users_router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(require_permission("users", "create")),
) -> UserResponse:
    """Provisions a new government user account (Admin role)."""
    return await user_service.create_user(data=payload, admin_id=current_user.id)


@users_router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: UUID,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Retrieves user profile (Admin, or Self)."""
    if current_user.role.name != "system_admin" and current_user.id != user_id:
        raise PermissionDeniedException(detail="Cannot inspect other user profiles", error_code="AUTHZ_001")
    return await user_service.get_user(user_id=user_id)


@users_router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    payload: UserUpdateRequest,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(require_permission("users", "update")),
) -> UserResponse:
    """Updates user profile information (Admin role)."""
    return await user_service.update_user(user_id=user_id, data=payload, admin_id=current_user.id)


@users_router.patch("/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: UUID,
    payload: UserStatusUpdateRequest,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(require_permission("users", "status")),
) -> UserResponse:
    """Activates, deactivates, or unlocks a user account (Admin role)."""
    return await user_service.update_user_status(
        user_id=user_id, data=payload, admin_id=current_user.id
    )


# -----------------------------------------------------------------------------
# /api/v1/admin/users endpoints
# -----------------------------------------------------------------------------

@admin_router.post("/{user_id}/reset-password", response_model=AdminResetPasswordResponse)
async def admin_reset_password(
    user_id: UUID,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(require_role("system_admin")),
) -> AdminResetPasswordResponse:
    """Generates temporary password for user and invalidates their sessions (Admin role)."""
    temp_password = await user_service.admin_reset_password(user_id=user_id, admin_id=current_user.id)
    return AdminResetPasswordResponse(
        message="Temporary password successfully generated. Instruct user to change upon next login.",
        user_id=user_id,
        temporary_password=temp_password,
    )
