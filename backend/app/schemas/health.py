"""Health and diagnostic response schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Liveness probe response."""
    status: str
    timestamp: str
    environment: str
    version: str = "1.0.0"


class ServiceStatus(BaseModel):
    """Detailed health status of each dependency."""
    database: bool
    redis: bool
    storage: bool
    celery: bool


class ReadyResponse(BaseModel):
    """Readiness probe response."""
    status: str
    timestamp: str
    services: ServiceStatus


class TaskTriggerResponse(BaseModel):
    """Response when enqueuing a background test task."""
    task_id: str
    status: str
    message: str
