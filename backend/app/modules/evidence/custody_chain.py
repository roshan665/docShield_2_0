"""
Cryptographic Chain of Custody Ledger Service
Implements SHA-256 hash chaining, canonical payload serialization, and chain integrity verification.
"""

import hashlib
import json
from datetime import datetime
from uuid import UUID

GENESIS_HASH = "0" * 64


def canonicalize_custody_event(
    evidence_id: UUID | str,
    event_type: str,
    from_user_id: UUID | str | None,
    to_user_id: UUID | str,
    reason: str,
    file_hash_at_event: str | None,
    timestamp: datetime | str,
    location: str | None = None,
) -> bytes:
    """
    Produces deterministic canonical UTF-8 bytes for an evidence custody event.
    """
    ts_str = timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp)
    payload = {
        "evidence_id": str(evidence_id),
        "event_type": str(event_type),
        "from_user_id": str(from_user_id) if from_user_id else None,
        "to_user_id": str(to_user_id),
        "reason": str(reason).strip(),
        "file_hash_at_event": str(file_hash_at_event).lower() if file_hash_at_event else None,
        "location": str(location).strip() if location else None,
        "timestamp": ts_str,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_custody_event_hash(
    canonical_bytes: bytes,
    previous_event_hash: str,
) -> str:
    """
    Computes SHA-256(canonical_payload || previous_event_hash).
    """
    hasher = hashlib.sha256()
    hasher.update(canonical_bytes)
    hasher.update(previous_event_hash.encode("utf-8"))
    return hasher.hexdigest().lower()


def verify_custody_chain(events: list) -> dict:
    """
    Validates sequential continuity and cryptographic signatures across custody events.
    Expected list sorted chronologically (ascending).
    """
    if not events:
        return {
            "valid": True,
            "events_checked": 0,
            "first_invalid_event": None,
            "reason": "Chain is empty",
            "genesis_hash": None,
            "tip_hash": None,
        }

    expected_prev_hash = GENESIS_HASH

    for idx, evt in enumerate(events):
        # 1. Verify previous hash link
        if evt.previous_event_hash != expected_prev_hash:
            return {
                "valid": False,
                "events_checked": idx + 1,
                "first_invalid_event": str(evt.id),
                "reason": (
                    f"Chain link broken at event #{idx + 1}: expected predecessor hash "
                    f"'{expected_prev_hash[:12]}...', got '{evt.previous_event_hash[:12]}...'"
                ),
                "genesis_hash": events[0].event_hash,
                "tip_hash": events[-1].event_hash,
            }

        # 2. Recompute canonical hash
        canonical_bytes = canonicalize_custody_event(
            evidence_id=evt.evidence_id,
            event_type=evt.event_type,
            from_user_id=evt.from_user_id,
            to_user_id=evt.to_user_id,
            reason=evt.reason,
            file_hash_at_event=evt.file_hash_at_event,
            timestamp=evt.created_at,
            location=evt.location,
        )
        calculated_hash = compute_custody_event_hash(canonical_bytes, evt.previous_event_hash)

        if calculated_hash != evt.event_hash:
            return {
                "valid": False,
                "events_checked": idx + 1,
                "first_invalid_event": str(evt.id),
                "reason": (
                    f"Event tampering detected at event #{idx + 1}: stored hash '{evt.event_hash[:12]}...' "
                    f"does not match computed hash '{calculated_hash[:12]}...'"
                ),
                "genesis_hash": events[0].event_hash,
                "tip_hash": events[-1].event_hash,
            }

        expected_prev_hash = evt.event_hash

    return {
        "valid": True,
        "events_checked": len(events),
        "first_invalid_event": None,
        "reason": "All custody event cryptographic hashes and linkage verified successfully",
        "genesis_hash": events[0].event_hash,
        "tip_hash": events[-1].event_hash,
    }

