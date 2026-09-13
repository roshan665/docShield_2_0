"""
Diagnostic / Verification Tasks
Provides simple queue check tasks without business processing.
"""

from datetime import UTC, datetime

from app.workers.celery_app import celery_app


@celery_app.task(name="tasks.ping")
def ping_task(message: str = "ping") -> dict:
    """Simple verification task to confirm worker connectivity."""
    return {
        "status": "pong",
        "echo": message,
        "timestamp": datetime.now(UTC).isoformat(),
    }
