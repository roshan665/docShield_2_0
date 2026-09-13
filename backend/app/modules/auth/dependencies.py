"""
Authentication & RBAC FastAPI Dependencies
Provides token extraction, JTI revocation checks, and role/permission enforcement guards.
"""

from collections.abc import Callable
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_redis
from app.core.exceptions import AuthenticationException, PermissionDeniedException
from app.core.security import decode_token
from app.models.auth import User
from app.modules.auth.repository import UserRepository
from app.modules.auth.service import AuthService
from app.modules.roles.service import RoleService
from app.modules.users.service import UserService

security_scheme = HTTPBearer(auto_error=False)


async def get_auth_service(
    session: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> AuthService:
    return AuthService(session, redis_client)


async def get_user_service(
    session: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> UserService:
    return UserService(session, redis_client)


async def get_role_service(session: AsyncSession = Depends(get_db)) -> RoleService:
    return RoleService(session)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    session: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> User:
    """
    Extracts Bearer token, validates cryptographic signature and expiry,
    checks Redis blacklist for JTI revocation, and verifies active user status.
    """
    if not credentials or credentials.scheme.lower() != "bearer":
        raise AuthenticationException(detail="Missing or invalid authentication credentials", error_code="AUTH_001")

    token = credentials.credentials
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise AuthenticationException(detail="Invalid token type", error_code="AUTH_004")

    # Check JTI blacklist in Redis
    jti = payload.get("jti")
    if jti and await redis_client.exists(f"auth:blacklist:{jti}"):
        raise AuthenticationException(detail="Token has been revoked", error_code="AUTH_004")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationException(detail="Invalid token claims", error_code="AUTH_004")

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(UUID(user_id_str))

    if not user:
        raise AuthenticationException(detail="User not found", error_code="AUTH_001")

    if not user.is_active:
        raise PermissionDeniedException(detail="User account is deactivated", error_code="AUTH_005")

    if user.is_locked:
        raise PermissionDeniedException(detail="User account is locked", error_code="AUTH_003")

    return user


require_authenticated_user = get_current_user


def require_role(*allowed_roles: str | list[str] | tuple[str, ...]) -> Callable[[User], User]:
    """
    Factory creating a FastAPI dependency enforcing that current_user has one of the allowed roles.
    Supports both unpacked varargs require_role("admin", "supervisor") and collection require_role(["admin", "supervisor"]).
    """
    flattened: set[str] = set()
    for r in allowed_roles:
        if isinstance(r, (list, tuple, set)):
            flattened.update(r)
        else:
            flattened.add(str(r))

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = current_user.role.name
        if user_role not in flattened:
            raise PermissionDeniedException(
                detail=f"Access forbidden: role '{user_role}' does not possess required privilege.",
                error_code="AUTHZ_001",
            )
        return current_user

    return role_checker


def require_permission(resource: str, action: str) -> Callable[[User], User]:
    """
    Factory creating a FastAPI dependency checking for granular resource:action permission.
    """
    async def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        user_permissions = {f"{p.resource}:{p.action}" for p in current_user.role.permissions}
        required_perm = f"{resource}:{action}"

        if required_perm not in user_permissions:
            raise PermissionDeniedException(
                detail=f"Access forbidden: missing required permission '{required_perm}'.",
                error_code="AUTHZ_002",
            )
        return current_user

    return permission_checker
