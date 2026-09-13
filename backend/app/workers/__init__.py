"""Workers package initialization and diagnostics."""
import redis

from app.core.config import settings
from app.workers.celery_app import celery_app


def check_redis_health() -> bool:
    """Checks direct Redis connectivity."""
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2)
        return bool(r.ping())
    except Exception:
        return False


def check_celery_health() -> bool:
    """Checks whether Celery broker is reachable."""
    try:
        # Check connection to broker
        conn = celery_app.connection_for_read()
        conn.ensure_connection(max_retries=1)
        conn.close()
        return True
    except Exception:
        return False


__all__ = ["celery_app", "check_redis_health", "check_celery_health"]
