"""
Authentication & User Database Repositories
Encapsulates all SQLAlchemy data access queries for users, roles, and security events.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import Permission, Role, SecurityEvent, User


class UserRepository:
    """Data access repository for User entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        query = (
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.role).selectinload(Role.permissions)
            )
        )
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        query = (
            select(User)
            .where(User.email == email.lower())
            .options(
                selectinload(User.role).selectinload(Role.permissions)
            )
        )
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def get_by_employee_id(self, employee_id: str) -> User | None:
        query = (
            select(User)
            .where(User.employee_id == employee_id)
            .options(
                selectinload(User.role).selectinload(Role.permissions)
            )
        )
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 50,
        role_id: UUID | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        base_query = select(User).options(selectinload(User.role).selectinload(Role.permissions))
        count_query = select(func.count(User.id))

        filters = []
        if role_id is not None:
            filters.append(User.role_id == role_id)
        if is_active is not None:
            filters.append(User.is_active == is_active)
        if search:
            search_pattern = f"%{search}%"
            filters.append(
                or_(
                    User.full_name.ilike(search_pattern),
                    User.email.ilike(search_pattern),
                    User.employee_id.ilike(search_pattern),
                )
            )

        if filters:
            base_query = base_query.where(*filters)
            count_query = count_query.where(*filters)

        total_res = await self.session.execute(count_query)
        total = total_res.scalar() or 0

        query = base_query.order_by(User.created_at.desc()).offset(skip).limit(limit)
        res = await self.session.execute(query)
        users = list(res.scalars().all())

        return users, total

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        # Refresh with role
        return await self.get_by_id(user.id)  # type: ignore

    async def update(self, user: User) -> User:
        user.updated_at = datetime.now(UTC)
        await self.session.flush()
        return user

    async def increment_failed_login(
        self, user: User, max_attempts: int = 5, lockout_minutes: int = 15
    ) -> bool:
        """
        Increments failed login counter. If threshold exceeded, locks the account.
        Returns True if account was newly locked.
        """
        user.failed_login_attempts += 1
        newly_locked = False

        if user.failed_login_attempts >= max_attempts:
            user.is_locked = True
            user.locked_until = datetime.now(UTC) + timedelta(minutes=lockout_minutes)
            newly_locked = True

        user.updated_at = datetime.now(UTC)
        await self.session.flush()
        return newly_locked

    async def reset_failed_logins(self, user: User) -> None:
        """Resets failed login counters and lockout state upon valid authentication."""
        user.failed_login_attempts = 0
        user.is_locked = False
        user.locked_until = None
        user.last_login = datetime.now(UTC)
        user.updated_at = datetime.now(UTC)
        await self.session.flush()


class RoleRepository:
    """Data access repository for Role and Permission entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, role_id: UUID) -> Role | None:
        query = select(Role).where(Role.id == role_id).options(selectinload(Role.permissions))
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Role | None:
        query = select(Role).where(Role.name == name).options(selectinload(Role.permissions))
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def list_roles(self) -> list[Role]:
        query = select(Role).order_by(Role.name).options(selectinload(Role.permissions))
        res = await self.session.execute(query)
        return list(res.scalars().all())

    async def list_permissions(self) -> list[Permission]:
        query = select(Permission).order_by(Permission.resource, Permission.action)
        res = await self.session.execute(query)
        return list(res.scalars().all())


class SecurityEventRepository:
    """Data access repository for audit security events."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_event(
        self,
        event_type: str,
        severity: str,
        actor_id: UUID | None = None,
        ip_address: str | None = None,
        details: dict | None = None,
        category: str | None = None,
        case_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
    ) -> SecurityEvent:
        event = SecurityEvent(
            event_type=event_type,
            severity=severity.lower(),
            category=category.upper() if category else None,
            actor_id=actor_id,
            case_id=case_id,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            details=details or {},
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_event_by_id(self, event_id: UUID) -> SecurityEvent | None:
        """Retrieves a single security event by ID."""
        stmt = select(SecurityEvent).where(SecurityEvent.id == event_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_events(
        self,
        skip: int = 0,
        limit: int = 50,
        severity: str | None = None,
        category: str | None = None,
        event_type: str | None = None,
        case_id: UUID | None = None,
        actor_id: UUID | None = None,
        resolved: bool | None = None,
    ) -> tuple[list[SecurityEvent], int]:
        """Lists security events with filtering and total count."""
        conditions = []
        if severity:
            conditions.append(SecurityEvent.severity == severity.lower())
        if category:
            conditions.append(SecurityEvent.category == category.upper())
        if event_type:
            conditions.append(SecurityEvent.event_type.ilike(f"%{event_type}%"))
        if case_id:
            conditions.append(SecurityEvent.case_id == case_id)
        if actor_id:
            conditions.append(SecurityEvent.actor_id == actor_id)
        if resolved is not None:
            conditions.append(SecurityEvent.resolved == resolved)

        count_stmt = select(func.count(SecurityEvent.id))
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one() or 0

        stmt = select(SecurityEvent)
        if conditions:
            stmt = stmt.where(*conditions)
        stmt = stmt.order_by(desc(SecurityEvent.created_at)).offset(skip).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all()), total

    async def resolve_event(
        self,
        event_id: UUID,
        resolver_id: UUID,
    ) -> SecurityEvent | None:
        """Marks a security event as resolved."""
        event = await self.get_event_by_id(event_id)
        if not event:
            return None
        event.resolved = True
        event.resolved_by = resolver_id
        event.resolved_at = datetime.now(UTC)
        await self.session.flush()
        return event

    async def get_metrics(self) -> dict:
        """Calculates security metrics for administrative monitoring."""
        # Total counts
        total_stmt = select(func.count(SecurityEvent.id))
        total = (await self.session.execute(total_stmt)).scalar_one() or 0

        # Severity counts
        severity_stmt = select(SecurityEvent.severity, func.count(SecurityEvent.id)).group_by(SecurityEvent.severity)
        severity_rows = (await self.session.execute(severity_stmt)).all()
        sev_map = {row[0]: row[1] for row in severity_rows}

        # Category counts
        cat_stmt = select(SecurityEvent.category, func.count(SecurityEvent.id)).group_by(SecurityEvent.category)
        cat_rows = (await self.session.execute(cat_stmt)).all()
        cat_map = {row[0]: row[1] for row in cat_rows if row[0]}

        # Failed logins count
        failed_logins_stmt = select(func.count(SecurityEvent.id)).where(SecurityEvent.event_type.ilike("%login%failed%"))
        failed_logins = (await self.session.execute(failed_logins_stmt)).scalar_one() or 0

        # Locked accounts count
        locked_stmt = select(func.count(SecurityEvent.id)).where(SecurityEvent.event_type.ilike("%lockout%"))
        locked_accounts = (await self.session.execute(locked_stmt)).scalar_one() or 0

        # Integrity violations count
        integrity_stmt = select(func.count(SecurityEvent.id)).where(
            or_(
                SecurityEvent.category == "INTEGRITY",
                SecurityEvent.event_type.ilike("%integrity%"),
                SecurityEvent.event_type.ilike("%mismatch%"),
            )
        )
        integrity_violations = (await self.session.execute(integrity_stmt)).scalar_one() or 0

        # Malicious files count
        malicious_stmt = select(func.count(SecurityEvent.id)).where(
            or_(
                SecurityEvent.category == "FILE_SECURITY",
                SecurityEvent.event_type.ilike("%malicious%"),
                SecurityEvent.event_type.ilike("%virus%"),
            )
        )
        malicious_files = (await self.session.execute(malicious_stmt)).scalar_one() or 0

        # Unauthorized access attempts
        unauthorized_stmt = select(func.count(SecurityEvent.id)).where(
            or_(
                SecurityEvent.category == "AUTHORIZATION",
                SecurityEvent.event_type.ilike("%unauthorized%"),
                SecurityEvent.event_type.ilike("%permission%"),
            )
        )
        unauthorized_attempts = (await self.session.execute(unauthorized_stmt)).scalar_one() or 0

        # Rate limit events
        rate_limit_stmt = select(func.count(SecurityEvent.id)).where(
            or_(
                SecurityEvent.category == "RATE_LIMIT",
                SecurityEvent.event_type.ilike("%rate_limit%"),
            )
        )
        rate_limit_events = (await self.session.execute(rate_limit_stmt)).scalar_one() or 0

        # Recent critical events
        crit_stmt = (
            select(SecurityEvent)
            .where(SecurityEvent.severity.in_(["critical", "high"]))
            .order_by(desc(SecurityEvent.created_at))
            .limit(10)
        )
        recent_critical = list((await self.session.execute(crit_stmt)).scalars().all())

        return {
            "total_events": total,
            "critical_events": sev_map.get("critical", 0),
            "high_events": sev_map.get("high", 0),
            "medium_events": sev_map.get("medium", 0),
            "low_events": sev_map.get("low", 0),
            "info_events": sev_map.get("info", 0),
            "failed_logins": failed_logins,
            "locked_accounts": locked_accounts,
            "integrity_violations": integrity_violations,
            "malicious_files": malicious_files,
            "unauthorized_access_attempts": unauthorized_attempts,
            "rate_limit_events": rate_limit_events,
            "category_breakdown": cat_map,
            "recent_critical_events": recent_critical,
        }
