"""
Core Application Dependencies
Provides reusable dependency injection providers for FastAPI endpoints.
"""

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger

logger = get_logger(__name__)

# Re-export get_db
__all__ = ["get_db", "get_redis"]


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """Provides an asynchronous Redis client connection."""
    client = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    try:
        yield client
    finally:
        await client.aclose()
