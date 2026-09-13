"""Storage package initialization and factory."""
from app.storage.s3 import S3StorageService
from app.storage.service import StorageService

_storage_instance = None


def get_storage_service() -> StorageService:
    """Returns singleton StorageService instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = S3StorageService()
    return _storage_instance


__all__ = ["StorageService", "S3StorageService", "get_storage_service"]
