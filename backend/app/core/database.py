"""
Database Connection & Session Management
Provides Async SQLAlchemy 2.0 engine, sessions, and diagnostic health checks.
"""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Create async engine with robust connection pooling
engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=settings.DEBUG,
    future=True,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> bool:
    """Verifies active PostgreSQL connection and pgvector extension availability."""
    try:
        async with AsyncSessionLocal() as session:
            # Check basic query execution
            result = await session.execute(text("SELECT 1"))
            val = result.scalar()
            if val != 1:
                return False

            # Check if pgvector extension is available or installed
            ext_check = await session.execute(
                text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
            )
            return ext_check.scalar() is not None
    except Exception as e:
        logger.warning(f"Database health check failed: {str(e)}")
        return False
