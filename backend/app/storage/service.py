"""
Storage Service Interface (Abstraction)
Decouples application logic from underlying object storage technology.
"""

from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import BinaryIO


class StorageService(ABC):
    """Abstract interface for S3-compatible object storage operations."""

    @abstractmethod
    def upload(
        self,
        file_data: BinaryIO | bytes,
        key: str,
        bucket: str,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Uploads a file or bytes to the specified bucket and key."""
        pass

    @abstractmethod
    def download(self, key: str, bucket: str) -> bytes:
        """Downloads the full file content as bytes."""
        pass

    @abstractmethod
    def download_stream(self, key: str, bucket: str, chunk_size: int = 65536) -> Generator[bytes, None, None]:
        """Streams file content chunk-by-chunk."""
        pass

    @abstractmethod
    def delete(self, key: str, bucket: str) -> bool:
        """Deletes an object from the specified bucket."""
        pass

    @abstractmethod
    def exists(self, key: str, bucket: str) -> bool:
        """Checks if an object exists in the specified bucket."""
        pass

    @abstractmethod
    def get_metadata(self, key: str, bucket: str) -> dict[str, str]:
        """Retrieves object metadata and headers."""
        pass

    @abstractmethod
    def check_health(self) -> bool:
        """Verifies storage connectivity and bucket accessibility."""
        pass

    @abstractmethod
    def ensure_bucket_exists(self, bucket: str) -> bool:
        """Verifies or creates bucket if missing."""
        pass

