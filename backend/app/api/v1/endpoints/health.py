"""Health check endpoints conforming to the API Specification."""

from datetime import UTC, datetime

from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.core.database import check_database_health
from app.schemas.health import (
    HealthResponse,
    ReadyResponse,
    ServiceStatus,
    TaskTriggerResponse,
)
from app.storage import get_storage_service
from app.workers import check_celery_health, check_redis_health
from app.workers.tasks.test_tasks import ping_task

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def liveness_check() -> HealthResponse:
    """
    Basic liveness probe for container orchestrators.
    Returns immediately without querying downstream dependencies.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(UTC).isoformat(),
        environment=settings.APP_ENV,
        version="1.0.0",
    )


@router.get("/health/ready", response_model=ReadyResponse)
async def readiness_check(response: Response) -> ReadyResponse:
    """
    Deep readiness probe inspecting DB, Redis, MinIO/S3, and Celery broker.
    Returns HTTP 200 if all services are operational; 503 if any service is down.
    """
    storage = get_storage_service()

    db_ok = await check_database_health()
    redis_ok = check_redis_health()
    storage_ok = storage.check_health()
    celery_ok = check_celery_health()

    all_ready = db_ok and redis_ok and storage_ok and celery_ok

    if not all_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadyResponse(
        status="ready" if all_ready else "degraded",
        timestamp=datetime.now(UTC).isoformat(),
        services=ServiceStatus(
            database=db_ok,
            redis=redis_ok,
            storage=storage_ok,
            celery=celery_ok,
        ),
    )


@router.post("/health/test-task", response_model=TaskTriggerResponse)
async def trigger_test_task() -> TaskTriggerResponse:
    """Dispatches a diagnostic background task to verify the Celery worker queue."""
    try:
        task = ping_task.delay("verification_ping")
        return TaskTriggerResponse(
            task_id=task.id,
            status="queued",
            message="Diagnostic task dispatched to Celery worker",
        )
    except Exception as e:
        return TaskTriggerResponse(
            task_id="",
            status="failed",
            message=f"Could not dispatch task to Celery: {str(e)}",
        )
