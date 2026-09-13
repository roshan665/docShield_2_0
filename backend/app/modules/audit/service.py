"""
Audit Service & Cryptographic Hash-Chain Engine
Provides append-only recording, concurrency serialization, and integrity verification.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent

GENESIS_PREVIOUS_HASH = "0" * 64


class AuditService:
    """
    Manages tamper-evident hash-chained audit logging and verification.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def canonical_hash(
        action: str,
        actor_id: UUID | None,
        resource_type: str,
        resource_id: UUID | None,
        case_id: UUID | None,
        details: dict[str, Any] | None,
        result: str,
        timestamp: datetime,
        previous_event_hash: str,
    ) -> str:
        """
        Computes deterministic SHA-256 hash:
        H_n = SHA256(canonical_json(data) || previous_event_hash)
        """
        payload = {
            "action": action,
            "actor_id": str(actor_id) if actor_id else None,
            "case_id": str(case_id) if case_id else None,
            "details": details or {},
            "resource_id": str(resource_id) if resource_id else None,
            "resource_type": resource_type,
            "result": result,
            "timestamp": timestamp.isoformat(),
        }
        canonical_str = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        hash_input = f"{canonical_str}|{previous_event_hash}".encode()
        return hashlib.sha256(hash_input).hexdigest()

    async def record_event(
        self,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        actor_id: UUID | None = None,
        case_id: UUID | None = None,
        details: dict[str, Any] | None = None,
        result: str = "success",
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_id: str | None = None,
    ) -> AuditEvent:
        """
        Atomically acquires a PostgreSQL transactional advisory lock, fetches the latest
        event hash, calculates the SHA-256 chain hash, and inserts the audit record.
        """
        # 1. Acquire transaction advisory lock to strictly serialize sequential hash chaining
        await self.session.execute(text("SELECT pg_advisory_xact_lock(hashtext('audit_chain_lock'))"))

        # 2. Query the latest event hash
        latest_query = (
            select(AuditEvent.event_hash)
            .order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
            .limit(1)
        )
        res = await self.session.execute(latest_query)
        last_hash = res.scalar()
        previous_event_hash = last_hash if last_hash else GENESIS_PREVIOUS_HASH

        # 3. Create timestamp and compute canonical SHA-256 hash
        now = datetime.now(UTC)
        event_hash = self.canonical_hash(
            action=action,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            case_id=case_id,
            details=details,
            result=result,
            timestamp=now,
            previous_event_hash=previous_event_hash,
        )

        # 4. Insert new AuditEvent
        event = AuditEvent(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            case_id=case_id,
            details=details,
            result=result,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            previous_event_hash=previous_event_hash,
            event_hash=event_hash,
            timestamp=now,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def verify_chain(self, limit: int | None = None) -> dict[str, Any]:
        """
        Traverses the audit chain from genesis to tip, verifying mathematical correctness
        of every SHA-256 hash and unbroken backward linkage.
        """
        query = select(AuditEvent).order_by(AuditEvent.timestamp.asc(), AuditEvent.id.asc())
        if limit:
            query = query.limit(limit)

        res = await self.session.execute(query)
        events = list(res.scalars().all())

        if not events:
            return {
                "valid": True,
                "events_checked": 0,
                "first_invalid_event": None,
                "reason": "No audit records present",
            }

        expected_prev = GENESIS_PREVIOUS_HASH
        events_checked = 0

        for event in events:
            events_checked += 1

            # 1. Verify previous hash pointer
            if event.previous_event_hash != expected_prev:
                return {
                    "valid": False,
                    "events_checked": events_checked,
                    "first_invalid_event": str(event.id),
                    "reason": f"Chain broken: expected previous_event_hash '{expected_prev}', got '{event.previous_event_hash}'",
                }

            # 2. Recompute canonical hash
            expected_hash = self.canonical_hash(
                action=event.action,
                actor_id=event.actor_id,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                case_id=event.case_id,
                details=event.details,
                result=event.result,
                timestamp=event.timestamp,
                previous_event_hash=event.previous_event_hash,
            )

            # 3. Verify event hash match
            if event.event_hash != expected_hash:
                return {
                    "valid": False,
                    "events_checked": events_checked,
                    "first_invalid_event": str(event.id),
                    "reason": f"Tampering detected: stored hash '{event.event_hash}' does not match recomputed hash '{expected_hash}'",
                }

            expected_prev = event.event_hash

        return {
            "valid": True,
            "events_checked": events_checked,
            "first_invalid_event": None,
            "reason": None,
        }

    async def list_events(
        self,
        case_id: UUID | None = None,
        actor_id: UUID | None = None,
        resource_type: str | None = None,
        action: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[AuditEvent], int]:
        """Lists audit events with pagination and filtering."""
        query = select(AuditEvent)

        if case_id:
            query = query.where(AuditEvent.case_id == case_id)
        if actor_id:
            query = query.where(AuditEvent.actor_id == actor_id)
        if resource_type:
            query = query.where(AuditEvent.resource_type == resource_type)
        if action:
            query = query.where(AuditEvent.action == action)

        # Count
        count_query = select(text("count(*)")).select_from(query.subquery())
        count_res = await self.session.execute(count_query)
        total = count_res.scalar() or 0

        # Items
        query = query.order_by(AuditEvent.timestamp.desc()).offset(skip).limit(limit)
        res = await self.session.execute(query)
        return list(res.scalars().all()), total

