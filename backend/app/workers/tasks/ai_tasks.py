"""
Celery Background Tasks for AI Processing
Asynchronously processes uploaded legal documents through the 7-stage pipeline.
"""

import asyncio
import logging
from uuid import UUID

from app.core.database import AsyncSessionLocal
from app.modules.ai.service import AIService
from app.storage.s3 import S3StorageService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _async_process_document(document_id_str: str, actor_id_str: str | None = None) -> dict:
    doc_uuid = UUID(document_id_str)
    actor_uuid = UUID(actor_id_str) if actor_id_str else None

    async with AsyncSessionLocal() as session:
        storage = S3StorageService()
        ai_service = AIService(session=session, storage=storage)
        res = await ai_service.process_document(document_id=doc_uuid, actor_id=actor_uuid)
        return {
            "document_id": str(res.document_id),
            "ai_processed": res.ai_processed,
            "classification": res.ai_classification,
            "entities_count": len(res.entities),
            "chunks_count": res.chunk_count,
        }


@celery_app.task(name="ai.process_document", bind=True, max_retries=2)
def process_document_task(self, document_id: str, actor_id: str | None = None) -> dict:
    """
    Celery task running document AI pipeline asynchronously.
    """
    try:
        logger.info(f"Executing Celery task ai.process_document for doc: {document_id}")
        return asyncio.run(_async_process_document(document_id, actor_id))
    except Exception as exc:
        logger.exception(f"Error in Celery ai.process_document task: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=10) from exc
