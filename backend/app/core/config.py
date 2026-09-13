"""
Application Configuration Management
Uses Pydantic BaseSettings to load and validate environment variables.
"""

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

    @property
    def DEBUG(self) -> bool:
        return self.APP_DEBUG

    # Database Configuration (PostgreSQL 16 + pgvector)
    POSTGRES_USER: str = "sih_user"
    POSTGRES_PASSWORD: str = "sih_secure_password_dev"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "sih190"

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = "sih_redis_pass_dev"
    REDIS_DB: int = 0

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
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

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


    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Async connection string for SQLAlchemy asyncpg engine"""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def SQLALCHEMY_SYNC_DATABASE_URI(self) -> str:
        """Sync connection string for Alembic migrations"""
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def REDIS_URL(self) -> str:
        """Redis connection URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def CELERY_BROKER_URL(self) -> str:
        """Celery broker URL using Redis database 1"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/1"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/1"

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        """Celery results backend URL using Redis database 2"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/2"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/2"


settings = Settings()
