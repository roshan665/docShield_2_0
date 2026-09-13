"""
Phase 1 Foundation Verification Script
Performs direct live verification of:
1. PostgreSQL connection & pgvector extension
2. Redis connection & ping
3. MinIO / S3 object storage operations
4. Celery worker connectivity & task dispatch
5. FastAPI /health and /health/ready endpoints
"""

import sys
import os
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

import asyncio
from sqlalchemy import text
from app.core.config import settings
from app.core.database import AsyncSessionLocal, check_database_health
from app.storage import get_storage_service
from app.workers import check_redis_health, check_celery_health
from app.workers.tasks.test_tasks import ping_task
from app.main import app
from httpx import AsyncClient, ASGITransport


async def verify_all():
    print("==================================================")
    print("PHASE 1 FOUNDATION VERIFICATION")
    print("==================================================")
    all_ok = True

    # 1. PostgreSQL & pgvector check
    print("\n[1/5] Testing PostgreSQL Connection & pgvector Extension...")
    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT version();"))
            db_version = res.scalar()
            print(f"  ✓ PostgreSQL Connected: {db_version[:45]}...")

            ext_res = await session.execute(text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"))
            ext = ext_res.fetchone()
            if ext:
                print(f"  ✓ pgvector Extension Active: version {ext[1]}")
            else:
                print("  ✗ pgvector extension not found!")
                all_ok = False

            # Test vector math in PostgreSQL
            vec_test = await session.execute(text("SELECT '[1,2,3]'::vector + '[4,5,6]'::vector;"))
            vec_sum = vec_test.scalar()
            print(f"  ✓ pgvector calculation verified: [1,2,3] + [4,5,6] = {vec_sum}")
    except Exception as e:
        print(f"  ✗ PostgreSQL check failed: {e}")
        all_ok = False

    # 2. Redis check
    print("\n[2/5] Testing Redis Connection...")
    try:
        redis_ok = check_redis_health()
        if redis_ok:
            print(f"  ✓ Redis Connected & PONG at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        else:
            print("  ✗ Redis ping failed")
            all_ok = False
    except Exception as e:
        print(f"  ✗ Redis check failed: {e}")
        all_ok = False

    # 3. MinIO / S3 Storage check
    print("\n[3/5] Testing MinIO / S3 Object Storage...")
    try:
        storage = get_storage_service()
        health = storage.check_health()
        if health:
            print(f"  ✓ S3 Connection established to {settings.S3_ENDPOINT_URL}")
        else:
            print("  ✗ S3 check_health returned False")
            all_ok = False

        test_key = "system_checks/phase1_probe.txt"
        test_bucket = settings.S3_BUCKET_DOCUMENTS
        test_payload = b"Phase 1 Verification Probe - SHA-256 Baseline"

        # Upload
        storage.upload(test_payload, test_key, test_bucket, content_type="text/plain")
        print(f"  ✓ Uploaded probe object to {test_bucket}/{test_key}")

        # Exists
        assert storage.exists(test_key, test_bucket), "Object should exist"
        print(f"  ✓ Verified object existence in {test_bucket}")

        # Download & verify byte integrity
        downloaded = storage.download(test_key, test_bucket)
        assert downloaded == test_payload, "Downloaded content must match uploaded content"
        print(f"  ✓ Verified byte-level integrity: {len(downloaded)} bytes retrieved")

        # Cleanup
        storage.delete(test_key, test_bucket)
        print(f"  ✓ Cleaned up probe object")
    except Exception as e:
        print(f"  ✗ S3 check failed: {e}")
        all_ok = False

    # 4. Celery task dispatch check
    print("\n[4/5] Testing Celery Task Queue Connection...")
    try:
        celery_ok = check_celery_health()
        if celery_ok:
            print(f"  ✓ Celery Broker Reachable at {settings.CELERY_BROKER_URL}")
        else:
            print("  ✗ Celery broker unreachable")
            all_ok = False

        # Execute task synchronously to verify task logic
        result = ping_task("verification_test")
        assert result["status"] == "pong"
        assert result["echo"] == "verification_test"
        print(f"  ✓ Celery ping_task executed successfully: {result}")
    except Exception as e:
        print(f"  ✗ Celery check failed: {e}")
        all_ok = False

    # 5. FastAPI Endpoints (/health, /health/ready)
    print("\n[5/5] Testing FastAPI Endpoints...")
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Liveness
            res_liveness = await client.get("/health")
            assert res_liveness.status_code == 200
            print(f"  ✓ GET /health: 200 OK -> {res_liveness.json()}")

            # Readiness
            res_ready = await client.get("/health/ready")
            assert res_ready.status_code == 200
            ready_json = res_ready.json()
            print(f"  ✓ GET /health/ready: 200 OK -> {ready_json}")
            assert ready_json["services"]["database"] is True
            assert ready_json["services"]["redis"] is True
            assert ready_json["services"]["storage"] is True
            assert ready_json["services"]["celery"] is True
    except Exception as e:
        print(f"  ✗ FastAPI endpoints check failed: {e}")
        all_ok = False

    print("\n==================================================")
    if all_ok:
        print("ALL FOUNDATION CHECKS PASSED SUCCESSFULLY (100%)")
    else:
        print("SOME FOUNDATION CHECKS FAILED - REVIEW ABOVE LOGS")
    print("==================================================")
    return all_ok


if __name__ == "__main__":
    success = asyncio.run(verify_all())
    sys.exit(0 if success else 1)
