"""Role and permission inspection service."""


from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.repository import RoleRepository
from app.schemas.auth import PermissionResponse, RoleDetailResponse


class RoleService:
    def __init__(self, session: AsyncSession):
        self.role_repo = RoleRepository(session)

    async def list_roles(self) -> list[RoleDetailResponse]:
        roles = await self.role_repo.list_roles()
        result = []
        for r in roles:
            perms = [
                PermissionResponse(
                    id=p.id, resource=p.resource, action=p.action, description=p.description
                )
                for p in r.permissions
            ]
            result.append(
                RoleDetailResponse(
                    id=r.id,
                    name=r.name,
                    display_name=r.display_name,
                    description=r.description,
                    is_system_role=r.is_system_role,
                    permissions=perms,
                )
            )
        return result

    async def list_permissions(self) -> list[PermissionResponse]:
        perms = await self.role_repo.list_permissions()
        return [
            PermissionResponse(
                id=p.id, resource=p.resource, action=p.action, description=p.description
            )
            for p in perms
        ]
