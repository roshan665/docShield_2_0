"""
Application Configuration Management
Uses Pydantic BaseSettings to load and validate environment variables.
"""

from typing import Any
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # General Project Info
    APP_NAME: str = "Secure Digital Evidence Management Platform"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    PORT: int = 8000

    @property
    def DEBUG(self) -> bool:
        return self.APP_DEBUG

    # Database Configuration (PostgreSQL 16 + pgvector)
    # Direct DATABASE_URL for Render / Supabase cloud hosting
    DATABASE_URL: str | None = None
    POSTGRES_USER: str = "sih_user"
    POSTGRES_PASSWORD: str = "sih_secure_password_dev"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "sih190"

    # Redis Configuration
    REDIS_URL: str | None = None
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = "sih_redis_pass_dev"
    REDIS_DB: int = 0
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    # Object Storage (MinIO / S3)
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minio_admin"
    S3_SECRET_KEY: str = "minio_secret_key_dev"
    S3_BUCKET_DOCUMENTS: str = "sih190-documents"
    S3_BUCKET_EVIDENCE: str = "sih190-evidence"
    S3_REGION: str = "us-east-1"
    S3_USE_SSL: bool = False

    # File Ingestion & Security
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    ALLOWED_DOCUMENT_MIME_TYPES: list[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "image/jpeg",
        "image/png",
    ]

    # Malware Scanning (ClamAV Integration)
    CLAMAV_HOST: str = "localhost"
    CLAMAV_PORT: int = 3310
    CLAMAV_TIMEOUT_SECONDS: int = 10
    MALWARE_SCAN_REQUIRED: bool = True

    # Security & Cryptography
    JWT_SECRET_KEY: str = "replace_with_64_char_hex_secret_key_minimum_production_only_value"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    BACKEND_CORS_ORIGINS: list[str] | str = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                try:
                    import json
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [item.strip() for item in v.split(",") if item.strip()]
        elif isinstance(v, (list, tuple)):
            return [str(item).strip() for item in v if str(item).strip()]
        return v

    # Logging & Rate Limiting
    LOG_LEVEL: str = "INFO"
    RATE_LIMIT_DEFAULT: str = "100/minute"

    # AI Pipeline & Vector Search Configuration (Google Gemini 2.5 & pgvector)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    EMBEDDING_MODEL: str = "models/text-embedding-004"
    EMBEDDING_DIMENSIONS: int = 768
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    SEMANTIC_SEARCH_TOP_K: int = 10
    MIN_SIMILARITY_THRESHOLD: float = 0.6
    OCR_ENABLED: bool = True
    SEARCH_RATE_LIMIT_PER_MINUTE: int = 30
    RAG_RATE_LIMIT_PER_MINUTE: int = 15

    @model_validator(mode="after")
    def _compute_redis_and_celery_urls(self) -> "Settings":
        """Compute Redis and Celery URLs if not explicitly provided."""
        if not self.REDIS_URL:
            if self.REDIS_PASSWORD:
                self.REDIS_URL = f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
            else:
                self.REDIS_URL = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

        if not self.CELERY_BROKER_URL:
            if self.REDIS_URL and not self.REDIS_URL.endswith(f"/{self.REDIS_DB}"):
                self.CELERY_BROKER_URL = self.REDIS_URL
            elif self.REDIS_PASSWORD:
                self.CELERY_BROKER_URL = f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/1"
            else:
                self.CELERY_BROKER_URL = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/1"

        if not self.CELERY_RESULT_BACKEND:
            if self.REDIS_URL and not self.REDIS_URL.endswith(f"/{self.REDIS_DB}"):
                self.CELERY_RESULT_BACKEND = self.REDIS_URL
            elif self.REDIS_PASSWORD:
                self.CELERY_RESULT_BACKEND = f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/2"
            else:
                self.CELERY_RESULT_BACKEND = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/2"

        return self

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Async connection string for SQLAlchemy asyncpg engine"""
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                url = "postgresql+asyncpg://" + url[len("postgres://"):]
            elif url.startswith("postgresql://"):
                url = "postgresql+asyncpg://" + url[len("postgresql://"):]
            return url
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def SQLALCHEMY_SYNC_DATABASE_URI(self) -> str:
        """Sync connection string for Alembic migrations"""
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                url = "postgresql+psycopg://" + url[len("postgres://"):]
            elif url.startswith("postgresql://"):
                url = "postgresql+psycopg://" + url[len("postgresql://"):]
            return url
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
