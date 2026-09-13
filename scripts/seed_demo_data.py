#!/usr/bin/env python3
"""
Convenience CLI runner for DocShield portable demo data seeding.
Usage:
    python scripts/seed_demo_data.py
    python -m app.seed_demo (inside backend/)
"""

import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))

from app.seed_demo import seed_demo_data

if __name__ == "__main__":
    asyncio.run(seed_demo_data())

