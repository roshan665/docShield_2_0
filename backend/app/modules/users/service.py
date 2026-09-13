"""
User Management Administration Service
Handles user provisioning, profile updates, status toggling, and administrative password resets.
"""

import secrets
import string
from datetime import UTC, datetime
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityNotFoundException, ValidationException
from app.core.security import hash_password
from app.models.auth import User, UserRole
from app.modules.auth.repository import (
    RoleRepository,
    SecurityEventRepository,
    UserRepository,
)
from app.schemas.auth import (
    UserCreateRequest,
    UserResponse,
    UserStatusUpdateRequest,
    UserUpdateRequest,
)


class UserService:
    """Administrative user management business operations."""

    def __init__(self, session: AsyncSession, redis_client: aioredis.Redis):
        self.session = session
        self.redis = redis_client
        self.user_repo = UserRepository(session)
        self.role_repo = RoleRepository(session)
        self.security_repo = SecurityEventRepository(session)

    async def create_user(self, data: UserCreateRequest, admin_id: UUID) -> UserResponse:
        # Check uniqueness of email
        if await self.user_repo.get_by_email(data.email):
            raise ValidationException(detail=f"Email '{data.email}' is already registered", error_code="USER_002")

        # Check uniqueness of employee_id
        if await self.user_repo.get_by_employee_id(data.employee_id):
            raise ValidationException(detail=f"Employee ID '{data.employee_id}' is already registered", error_code="USER_003")

        # Check role exists
        role = None
        if data.role_id:
            role = await self.role_repo.get_by_id(data.role_id)
        elif data.role_name:
            role = await self.role_repo.get_by_name(data.role_name)

        if not role:
            raise ValidationException(detail="Valid role_id or role_name is required", error_code="ROLE_001")

        # Create user
        user = User(
            employee_id=data.employee_id,
            email=data.email.lower(),
            full_name=data.full_name,
            password_hash=hash_password(data.password),
            role_id=role.id,
            phone=data.phone,
            department=data.department,
            designation=data.designation,
            is_active=True,
            is_locked=False,
        )

        user = await self.user_repo.create(user)

        # Create user_roles entry for schema compatibility
        user_role_entry = UserRole(
            user_id=user.id,
            role_id=role.id,
            assigned_by=admin_id,
            assigned_at=datetime.now(UTC),
        )
        self.session.add(user_role_entry)
        await self.session.flush()

        await self.security_repo.record_event(
            event_type="USER_CREATED",
            severity="info",
            actor_id=admin_id,
            details={"created_user_id": str(user.id), "email": user.email, "role": role.name},
        )

        return self._build_user_response(user)

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 50,
        role_id: UUID | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[UserResponse], int]:
        users, total = await self.user_repo.list_users(
            skip=skip, limit=limit, role_id=role_id, is_active=is_active, search=search
        )
        return [self._build_user_response(u) for u in users], total

    async def get_user(self, user_id: UUID) -> UserResponse:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise EntityNotFoundException(detail="User not found")
        return self._build_user_response(user)

    async def update_user(self, user_id: UUID, data: UserUpdateRequest, admin_id: UUID) -> UserResponse:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise EntityNotFoundException(detail="User not found")

        if data.full_name is not None:
            user.full_name = data.full_name
        if data.department is not None:
            user.department = data.department
        if data.designation is not None:
            user.designation = data.designation
        if data.phone is not None:
            user.phone = data.phone
        if data.role_id is not None:
            role = await self.role_repo.get_by_id(data.role_id)
            if not role:
                raise ValidationException(detail="Specified role_id does not exist", error_code="ROLE_001")
            user.role_id = role.id
        elif data.role_name is not None:
            role = await self.role_repo.get_by_name(data.role_name)
            if not role:
                raise ValidationException(detail="Specified role_name does not exist", error_code="ROLE_001")
            user.role_id = role.id

        user = await self.user_repo.update(user)
        # Re-fetch user to refresh role relationships
        refreshed = await self.user_repo.get_by_id(user.id)

        await self.security_repo.record_event(
            event_type="USER_UPDATED",
            severity="info",
            actor_id=admin_id,
            details={"updated_user_id": str(user.id)},
        )

        return self._build_user_response(refreshed)  # type: ignore

    async def update_user_status(
        self, user_id: UUID, data: UserStatusUpdateRequest, admin_id: UUID
    ) -> UserResponse:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise EntityNotFoundException(detail="User not found")

        changes = {}
        if data.is_active is not None:
            user.is_active = data.is_active
            changes["is_active"] = data.is_active

        if data.is_locked is not None:
            user.is_locked = data.is_locked
            if not data.is_locked:
                user.failed_login_attempts = 0
                user.locked_until = None
            changes["is_locked"] = data.is_locked

        user = await self.user_repo.update(user)

        # If deactivated or locked by admin, revoke their active refresh tokens
        if data.is_active is False or data.is_locked is True:
            pattern = f"auth:active_refresh:{user.id}:*"
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)

        await self.security_repo.record_event(
            event_type="USER_STATUS_CHANGED",
            severity="warning",
            actor_id=admin_id,
            details={"target_user_id": str(user.id), "changes": changes},
        )

        return self._build_user_response(user)

    async def admin_reset_password(self, user_id: UUID, admin_id: UUID) -> str:
        """Generates a secure temporary password, hashes it, and revokes all active tokens."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise EntityNotFoundException(detail="User not found")

        # Generate a high-entropy 14-character temporary password
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        temp_password = "".join(secrets.choice(chars) for _ in range(14))

        user.password_hash = hash_password(temp_password)
        user.failed_login_attempts = 0
        user.is_locked = False
        user.locked_until = None
        await self.user_repo.update(user)

        # Invalidate all active sessions for this user in Redis
        pattern = f"auth:active_refresh:{user.id}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)

        await self.security_repo.record_event(
            event_type="ADMIN_PASSWORD_RESET",
            severity="warning",
            actor_id=admin_id,
            details={"target_user_id": str(user.id), "target_email": user.email},
        )

        return temp_password

    def _build_user_response(self, user: User) -> UserResponse:
        permissions = [f"{p.resource}:{p.action}" for p in user.role.permissions]
        return UserResponse(
            id=user.id,
            employee_id=user.employee_id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.name,
            role_display_name=user.role.display_name,
            department=user.department,
            designation=user.designation,
            is_active=user.is_active,
            is_locked=user.is_locked,
            last_login=user.last_login,
            created_at=user.created_at,
            permissions=permissions,
        )
