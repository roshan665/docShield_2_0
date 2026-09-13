"""
Roles & Permissions Inspection HTTP Endpoints
Provides endpoints for inspecting available roles and permissions (Admin role).
"""


from fastapi import APIRouter, Depends

from app.models.auth import User
from app.modules.auth.dependencies import (
    get_role_service,
    require_role,
)
from app.modules.roles.service import RoleService
from app.schemas.auth import PermissionResponse, RoleDetailResponse

roles_router = APIRouter(tags=["Roles & Permissions"])


@roles_router.get("/roles", response_model=list[RoleDetailResponse])
async def list_roles(
    role_service: RoleService = Depends(get_role_service),
    current_user: User = Depends(require_role("system_admin")),
) -> list[RoleDetailResponse]:
    """Lists all available roles and their assigned permission matrices."""
    return await role_service.list_roles()


@roles_router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    role_service: RoleService = Depends(get_role_service),
    current_user: User = Depends(require_role("system_admin")),
) -> list[PermissionResponse]:
    """Lists all standard system permissions."""
    return await role_service.list_permissions()
