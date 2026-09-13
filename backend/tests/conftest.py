"""
Pytest Fixtures & Configuration
Provides async test clients, mocked storage, and application context.
"""

from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import AsyncSessionLocal, engine
from app.main import app
from app.storage.service import StorageService


class MockStorageService(StorageService):
    """In-memory mock storage service for isolated testing."""

    def __init__(self):
        self.store = {}

    def upload(self, file_data, key, bucket, content_type="application/octet-stream", metadata=None):
        if hasattr(file_data, "read"):
            data = file_data.read()
        else:
            data = file_data
        self.store[(bucket, key)] = {"data": data, "type": content_type, "meta": metadata or {}}
        return key

    def download(self, key, bucket):
        item = self.store.get((bucket, key))
        if item is None:
            raise Exception("Not found in mock")
        return item["data"]

    def download_stream(self, key, bucket, chunk_size=65536):
        data = self.download(key, bucket)
        yield data

    def delete(self, key, bucket):
        return bool(self.store.pop((bucket, key), None))

    def exists(self, key, bucket):
        return (bucket, key) in self.store

    def get_metadata(self, key, bucket):
        item = self.store.get((bucket, key))
        return item["meta"] if item else {}

    def check_health(self):
        return True

    def ensure_bucket_exists(self, bucket: str):
        return True


@pytest_asyncio.fixture
async def client():
    """Async HTTP client bound directly to FastAPI app via ASGI transport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
async def async_client(client):
    """Alias for client fixture."""
    return client


@pytest_asyncio.fixture
async def db_session():
    """Direct AsyncSession fixture for database tests."""
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()



@pytest.fixture
def mock_storage():
    """Provides an in-memory mock storage service instance."""
    mock = MockStorageService()
    with patch("app.storage.get_storage_service", return_value=mock):
        yield mock


@pytest_asyncio.fixture(autouse=True)
async def dispose_db_connections():
    """Ensure asyncpg engine pool is cleanly disposed between tests."""
    yield
    await engine.dispose()
