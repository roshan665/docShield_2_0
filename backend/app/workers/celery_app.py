"""
Celery Application Factory & Configuration
Configures Redis broker and result backend with serialization and retry defaults.
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "sih190_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.tasks.test_tasks",
        "app.workers.tasks.ai_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,        # 5 minutes max
    task_soft_time_limit=240,   # 4 minutes soft limit
    worker_prefetch_multiplier=1,
)
