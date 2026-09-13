#!/usr/bin/env python3
"""
Development-Only Demo Data Reset Utility for DocShield.
Purges database records and resets storage buckets for clean re-seeding.

SAFETY GUARD: Strictly forbidden in production environments.
Usage:
    python scripts/reset_demo_data.py [--force]
"""

import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.storage.s3 import S3StorageService


async def reset_demo_environment(force: bool = False):
    print("=" * 65)
    print("  DOCSHIELD — Development Demo Environment Reset")
    print("=" * 65)

    # 1. Strict Production Guard
    if settings.APP_ENV.lower() == "production":
        print("ERROR: Demo reset utility is strictly FORBIDDEN in production environment!")
        sys.exit(1)

    if not force:
        confirm = input("Are you sure you want to PURGE all demo data and reset storage? (yes/no): ")
        if confirm.strip().lower() != "yes":
            print("Operation aborted.")
            return

    print("\nPurging database records...")
    async with AsyncSessionLocal() as session:
        # Truncate tables in dependency order with CASCADE
        tables_to_clear = [
            "document_embeddings",
            "extracted_entities",
            "document_metadata",
            "evidence_custody_events",
            "evidence",
            "documents",
            "document_versions",
            "case_members",
            "cases",
            "audit_events",
            "security_events",
        ]
        for tbl in tables_to_clear:
            try:
                await session.execute(text(f"TRUNCATE TABLE {tbl} CASCADE;"))
                print(f"  ✓ Truncated {tbl}")
            except Exception as e:
                print(f"  ! Table {tbl} truncate skipped/error: {e}")
        await session.commit()

    print("\nResetting MinIO/S3 Storage...")
    try:
        storage = S3StorageService()
        for bucket in [settings.S3_BUCKET_DOCUMENTS, settings.S3_BUCKET_EVIDENCE]:
            objs = storage.s3_client.list_objects_v2(Bucket=bucket)
            if "Contents" in objs:
                delete_keys = [{"Key": o["Key"]} for o in objs["Contents"]]
                storage.s3_client.delete_objects(Bucket=bucket, Delete={"Objects": delete_keys})
                print(f"  ✓ Cleared {len(delete_keys)} objects from bucket '{bucket}'")
            else:
                print(f"  ✓ Bucket '{bucket}' is already clean")
    except Exception as st_err:
        print(f"  ! Storage reset warning: {st_err}")

    print("\n" + "=" * 65)
    print("  ✓ RESET COMPLETE. You may now run:")
    print("    python scripts/seed_demo_data.py")
    print("=" * 65)


if __name__ == "__main__":
    force_flag = "--force" in sys.argv or "--yes" in sys.argv
    asyncio.run(reset_demo_environment(force=force_flag))

