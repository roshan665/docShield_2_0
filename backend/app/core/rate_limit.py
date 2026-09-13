"""
Rate Limiting Infrastructure
Provides Redis-backed sliding window rate limiting with thread-safe in-memory fallback.
Used to protect Search and RAG endpoints against abuse and DoS.
"""

import logging
import time
from collections import defaultdict
from threading import Lock
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status

from app.core.config import settings
from app.models.auth import User
from app.modules.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

# Thread-safe in-memory store for fallback: key -> list of float timestamps
_memory_store: dict[str, list[float]] = defaultdict(list)
_memory_lock = Lock()

# Global async redis connection pool
_redis_client: aioredis.Redis | None = None


def get_redis_client() -> aioredis.Redis | None:
    """Lazily initialize and return Redis client."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
            )
        except Exception as e:
            logger.warning(f"Could not connect to Redis for rate limiting: {e}. Using in-memory store.")
            _redis_client = None
    return _redis_client


async def is_rate_limited(
    key: str,
    max_requests: int,
    window_seconds: int = 60,
) -> tuple[bool, int]:
    """
    Check if a key has exceeded max_requests within window_seconds.
    Returns (is_limited, retry_after_seconds).
    """
    now = time.time()
    client = get_redis_client()

    if client is not None:
        try:
            redis_key = f"rate_limit:{key}"
            pipe = client.pipeline()
            # Remove timestamps outside the sliding window
            pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
            # Count elements remaining
            pipe.zcard(redis_key)
            # Add current timestamp
            pipe.zadd(redis_key, {str(now): now})
            # Set TTL on the key
            pipe.expire(redis_key, window_seconds + 5)
            results = await pipe.execute()

            request_count = results[1]
            if request_count >= max_requests:
                return True, int(window_seconds)
            return False, 0
        except Exception as e:
            logger.debug(f"Redis rate limit check failed: {e}. Falling back to in-memory.")

    # Fallback to in-memory sliding window
    with _memory_lock:
        cutoff = now - window_seconds
        timestamps = [ts for ts in _memory_store[key] if ts > cutoff]
        if len(timestamps) >= max_requests:
            retry_after = int(window_seconds - (now - timestamps[0])) if timestamps else window_seconds
            _memory_store[key] = timestamps
            return True, max(1, retry_after)

        timestamps.append(now)
        _memory_store[key] = timestamps
        return False, 0


async def reset_rate_limits() -> None:
    """Utility for test suites to clear in-memory and Redis rate limiting state."""
    with _memory_lock:
        _memory_store.clear()
    client = get_redis_client()
    if client is not None:
        try:
            keys = await client.keys("rate_limit:*")
            if keys:
                await client.delete(*keys)
        except Exception:
            pass


async def rate_limit_search(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Dependency that enforces rate limiting on search endpoints (30 req/min)."""
    key = f"search:{current_user.id}"
    limited, retry_after = await is_rate_limited(
        key=key,
        max_requests=settings.SEARCH_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
    )
    if limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Search rate limit exceeded. Please retry after {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )


async def rate_limit_rag(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Dependency that enforces rate limiting on RAG ask endpoints (15 req/min)."""
    key = f"rag:{current_user.id}"
    limited, retry_after = await is_rate_limited(
        key=key,
        max_requests=settings.RAG_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
    )
    if limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"RAG query rate limit exceeded. Please retry after {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )


async def rate_limit_export(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Dependency that enforces rate limiting on export endpoints (10 req/min)."""
    key = f"export:{current_user.id}"
    limited, retry_after = await is_rate_limited(
        key=key,
        max_requests=10,
        window_seconds=60,
    )
    if limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Export generation rate limit exceeded. Please retry after {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

