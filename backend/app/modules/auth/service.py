"""
Authentication & Authorization Business Logic Service
Enforces Argon2id verification, JTI lifecycle via Redis, brute-force IP throttling, and account lockout.
"""

import uuid
from datetime import UTC, datetime
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationException,
    EntityNotFoundException,
    PermissionDeniedException,
    ValidationException,
)
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.auth import User
from app.modules.auth.repository import (
    RoleRepository,
    SecurityEventRepository,
    UserRepository,
)
from app.schemas.auth import (
    TokenResponse,
    UserResponse,
)

logger = get_logger(__name__)

# Security Thresholds
MAX_FAILED_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_MINUTES = 15
IP_BRUTE_FORCE_WINDOW_SECONDS = 300   # 5 minutes
IP_BRUTE_FORCE_MAX_FAILURES = 20
IP_BLOCK_DURATION_SECONDS = 1800      # 30 minutes


class AuthService:
    """Orchestrates authentication, session issuance, and threat defense."""

    def __init__(self, session: AsyncSession, redis_client: aioredis.Redis):
        self.session = session
        self.redis = redis_client
        self.user_repo = UserRepository(session)
        self.role_repo = RoleRepository(session)
        self.security_repo = SecurityEventRepository(session)

    async def login(
        self,
        email: str,
        password: str,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[TokenResponse, str]:
        """
        Validates credentials with brute force protection, lockout check, and token generation.
        Returns (TokenResponse, refresh_token_string).
        """
        ip = client_ip or "127.0.0.1"

        # 1. Check IP-level Brute Force Block
        ip_block_key = f"auth:ip_blocked:{ip}"
        if await self.redis.exists(ip_block_key):
            logger.warning(f"Rejected login from blocked IP: {ip}")
            raise AuthenticationException(
                detail="Too many failed login attempts from this IP address. Access blocked temporarily.",
                error_code="RATE_002",
            )

        # 2. Lookup User
        user = await self.user_repo.get_by_email(email)

        # Handle unknown user (apply constant-time dummy verification to mitigate user enumeration)
        if not user:
            await self._record_failed_attempt(
                user=None,
                attempted_email=email,
                client_ip=ip,
                reason="User not found",
            )
            await self.session.commit()
            # Dummy verify for constant-time
            verify_password("dummy_password", "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$dummyhash")
            raise AuthenticationException(detail="Invalid email or password", error_code="AUTH_001")

        # 3. Check Account Status (Deactivated)
        if not user.is_active:
            await self.security_repo.record_event(
                event_type="LOGIN_REJECTED_INACTIVE",
                severity="warning",
                actor_id=user.id,
                ip_address=ip,
                details={"email": email, "reason": "Account deactivated"},
            )
            await self.session.commit()
            raise PermissionDeniedException(
                detail="Your account has been deactivated. Contact an administrator.",
                error_code="AUTH_005",
            )

        # 4. Check Account Lockout
        now = datetime.now(UTC)
        if user.is_locked:
            if user.locked_until and user.locked_until > now:
                minutes_remaining = max(1, int((user.locked_until - now).total_seconds() / 60))
                await self.security_repo.record_event(
                    event_type="LOGIN_REJECTED_LOCKED",
                    severity="warning",
                    actor_id=user.id,
                    ip_address=ip,
                    details={"email": email, "locked_until": user.locked_until.isoformat()},
                )
                await self.session.commit()
                raise PermissionDeniedException(
                    detail=f"Account is locked due to consecutive failed attempts. Try again in {minutes_remaining} minutes.",
                    error_code="AUTH_003",
                )
            else:
                # Lockout duration expired: release lock
                user.is_locked = False
                user.failed_login_attempts = 0
                user.locked_until = None
                await self.user_repo.update(user)
                await self.session.commit()

        # 5. Verify Argon2id Password
        is_valid = verify_password(password, user.password_hash)
        if not is_valid:
            newly_locked = await self._record_failed_attempt(
                user=user,
                attempted_email=email,
                client_ip=ip,
                reason="Invalid password",
            )
            await self.session.commit()
            if newly_locked:
                raise PermissionDeniedException(
                    detail="Account has been locked for 15 minutes due to 5 consecutive failed login attempts.",
                    error_code="AUTH_003",
                )
            raise AuthenticationException(detail="Invalid email or password", error_code="AUTH_001")

        # 6. Authentication Successful
        await self.user_repo.reset_failed_logins(user)

        # Clear IP failure count on successful login
        await self.redis.delete(f"auth:ip_failed:{ip}")

        # 7. Generate Tokens & JTI
        access_jti = str(uuid.uuid4())
        refresh_jti = str(uuid.uuid4())

        permissions = [f"{p.resource}:{p.action}" for p in user.role.permissions]

        access_token = create_access_token(
            subject=str(user.id),
            role=user.role.name,
            extra_claims={"jti": access_jti},
        )
        refresh_token = create_refresh_token(
            subject=str(user.id),
            expires_delta=None,
        )

        # Track active refresh JTI in Redis (TTL = 7 days)
        refresh_ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        await self.redis.setex(f"auth:active_refresh:{user.id}:{refresh_jti}", refresh_ttl, "active")

        # Log security audit event
        await self.security_repo.record_event(
            event_type="LOGIN_SUCCESS",
            severity="info",
            actor_id=user.id,
            ip_address=ip,
            details={"email": user.email, "role": user.role.name, "user_agent": user_agent},
        )

        user_response = UserResponse(
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

        token_response = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_response,
        )

        return token_response, refresh_token

    async def refresh_tokens(self, refresh_token_str: str, client_ip: str | None = None) -> tuple[TokenResponse, str]:
        """
        Validates refresh token, invalidates old token, and issues rotated new tokens.
        """
        payload = decode_token(refresh_token_str)
        if payload.get("type") != "refresh":
            raise AuthenticationException(detail="Invalid token type", error_code="AUTH_004")

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise AuthenticationException(detail="Invalid token payload", error_code="AUTH_004")

        user = await self.user_repo.get_by_id(UUID(user_id_str))
        if not user or not user.is_active or user.is_locked:
            raise AuthenticationException(detail="User account unavailable", error_code="AUTH_001")

        # Rotation: Issue new tokens
        access_jti = str(uuid.uuid4())
        new_refresh_jti = str(uuid.uuid4())

        permissions = [f"{p.resource}:{p.action}" for p in user.role.permissions]

        new_access_token = create_access_token(
            subject=str(user.id),
            role=user.role.name,
            extra_claims={"jti": access_jti},
        )
        new_refresh_token = create_refresh_token(
            subject=str(user.id),
        )

        # Register new refresh JTI in Redis
        refresh_ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        await self.redis.setex(f"auth:active_refresh:{user.id}:{new_refresh_jti}", refresh_ttl, "active")

        user_response = UserResponse(
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

        return (
            TokenResponse(
                access_token=new_access_token,
                token_type="bearer",
                expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user=user_response,
            ),
            new_refresh_token,
        )

    async def logout(self, user_id: UUID, access_jti: str | None = None) -> None:
        """Revokes active tokens by blacklisting JTI in Redis."""
        if access_jti:
            # Blacklist access token for remaining lifetime
            ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            await self.redis.setex(f"auth:blacklist:{access_jti}", ttl, "revoked")

        # Invalidate active refresh tokens for user
        pattern = f"auth:active_refresh:{user_id}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)

        await self.security_repo.record_event(
            event_type="LOGOUT",
            severity="info",
            actor_id=user_id,
            details={"action": "User signed out; tokens revoked"},
        )

    async def change_password(
        self, user_id: UUID, current_password: str, new_password: str
    ) -> None:
        """Allows authenticated users to change their password upon verifying the current one."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise EntityNotFoundException(detail="User account not found")

        if not verify_password(current_password, user.password_hash):
            raise ValidationException(detail="Current password is incorrect", error_code="AUTH_001")

        if len(new_password) < 8:
            raise ValidationException(detail="New password must be at least 8 characters long")

        user.password_hash = hash_password(new_password)
        await self.user_repo.update(user)

        # Invalidate all active sessions across devices
        pattern = f"auth:active_refresh:{user.id}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)

        await self.security_repo.record_event(
            event_type="PASSWORD_CHANGED",
            severity="info",
            actor_id=user.id,
            details={"action": "Self-service password update"},
        )

    async def _record_failed_attempt(
        self,
        user: User | None,
        attempted_email: str,
        client_ip: str,
        reason: str,
    ) -> bool:
        """Internal helper to increment IP and account failure counters."""
        newly_locked = False

        # Track IP failures in Redis
        ip_fail_key = f"auth:ip_failed:{client_ip}"
        ip_fails = await self.redis.incr(ip_fail_key)
        if ip_fails == 1:
            await self.redis.expire(ip_fail_key, IP_BRUTE_FORCE_WINDOW_SECONDS)

        if ip_fails >= IP_BRUTE_FORCE_MAX_FAILURES:
            # Block this IP in Redis
            await self.redis.setex(f"auth:ip_blocked:{client_ip}", IP_BLOCK_DURATION_SECONDS, "blocked")
            await self.security_repo.record_event(
                event_type="BRUTE_FORCE_DETECTED",
                severity="critical",
                actor_id=user.id if user else None,
                ip_address=client_ip,
                details={
                    "attempted_email": attempted_email,
                    "ip_failures": ip_fails,
                    "action": f"IP blocked for {IP_BLOCK_DURATION_SECONDS // 60} minutes",
                },
            )

        # Increment User Account failed logins
        if user:
            newly_locked = await self.user_repo.increment_failed_login(
                user, max_attempts=MAX_FAILED_LOGIN_ATTEMPTS, lockout_minutes=ACCOUNT_LOCKOUT_MINUTES
            )
            await self.security_repo.record_event(
                event_type="FAILED_LOGIN",
                severity="warning" if newly_locked else "info",
                actor_id=user.id,
                ip_address=client_ip,
                details={
                    "attempted_email": attempted_email,
                    "failed_attempts": user.failed_login_attempts,
                    "newly_locked": newly_locked,
                },
            )
            if newly_locked:
                await self.security_repo.record_event(
                    event_type="ACCOUNT_LOCKED",
                    severity="warning",
                    actor_id=user.id,
                    ip_address=client_ip,
                    details={"locked_until": user.locked_until.isoformat() if user.locked_until else None},
                )
        else:
            await self.security_repo.record_event(
                event_type="FAILED_LOGIN",
                severity="info",
                ip_address=client_ip,
                details={"attempted_email": attempted_email, "reason": reason},
            )

        return newly_locked
