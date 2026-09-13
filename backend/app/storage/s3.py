"""
S3-Compatible Storage Service Implementation
Supports AWS S3 and local MinIO instances transparently.
"""

import io
from collections.abc import Generator
from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.exceptions import StorageException
from app.core.logging import get_logger
from app.storage.service import StorageService

logger = get_logger(__name__)


class S3StorageService(StorageService):
    """Boto3-based implementation for S3 and MinIO."""

    def __init__(self):
        # MinIO requires path-style addressing and explicit endpoint
        endpoint = settings.S3_ENDPOINT_URL if settings.S3_ENDPOINT_URL else None
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            use_ssl=settings.S3_USE_SSL,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def upload(
        self,
        file_data: BinaryIO | bytes,
        key: str,
        bucket: str,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> str:
        try:
            extra_args = {"ContentType": content_type}
            if metadata:
                extra_args["Metadata"] = metadata

            if isinstance(file_data, bytes):
                body = io.BytesIO(file_data)
            else:
                body = file_data

            self.s3_client.upload_fileobj(
                Fileobj=body,
                Bucket=bucket,
                Key=key,
                ExtraArgs=extra_args,
            )
            logger.info(f"Successfully uploaded object {key} to bucket {bucket}")
            return key
        except ClientError as e:
            logger.error(f"S3 upload error for {key} in {bucket}: {str(e)}")
            raise StorageException(detail=f"Storage upload error: {str(e)}") from e

    def download(self, key: str, bucket: str) -> bytes:
        try:
            buffer = io.BytesIO()
            self.s3_client.download_fileobj(Bucket=bucket, Key=key, Fileobj=buffer)
            return buffer.getvalue()
        except ClientError as e:
            logger.error(f"S3 download error for {key} in {bucket}: {str(e)}")
            raise StorageException(detail=f"Storage download error: {str(e)}") from e

    def download_stream(self, key: str, bucket: str, chunk_size: int = 65536) -> Generator[bytes, None, None]:
        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            stream = response["Body"]
            while chunk := stream.read(chunk_size):
                yield chunk
        except ClientError as e:
            logger.error(f"S3 stream download error for {key} in {bucket}: {str(e)}")
            raise StorageException(detail=f"Storage stream error: {str(e)}") from e

    def delete(self, key: str, bucket: str) -> bool:
        try:
            self.s3_client.delete_object(Bucket=bucket, Key=key)
            logger.info(f"Deleted object {key} from {bucket}")
            return True
        except ClientError as e:
            logger.error(f"S3 delete error for {key} in {bucket}: {str(e)}")
            return False

    def exists(self, key: str, bucket: str) -> bool:
        try:
            self.s3_client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False

    def get_metadata(self, key: str, bucket: str) -> dict[str, str]:
        try:
            response = self.s3_client.head_object(Bucket=bucket, Key=key)
            return response.get("Metadata", {})
        except ClientError as e:
            raise StorageException(detail=f"Could not retrieve object metadata: {str(e)}") from e

    def check_health(self) -> bool:
        try:
            # Listing buckets confirms credentials and connectivity
            self.s3_client.list_buckets()
            return True
        except Exception as e:
            logger.warning(f"Storage health check failed: {str(e)}")
            return False

    def ensure_bucket_exists(self, bucket: str) -> bool:
        try:
            self.s3_client.head_bucket(Bucket=bucket)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ("404", "NoSuchBucket"):
                try:
                    self.s3_client.create_bucket(Bucket=bucket)
                    logger.info(f"Created missing S3 bucket: {bucket}")
                    return True
                except Exception as create_err:
                    logger.error(f"Failed to auto-create S3 bucket {bucket}: {create_err}")
                    return False
            return False

