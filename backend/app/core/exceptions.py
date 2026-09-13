"""
Central Exception Hierarchy & Handlers
Ensures consistent, safe error payloads conforming to the API Specification.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppException(Exception):
    """Base application exception with error code and status code."""

    def __init__(
        self,
        detail: str,
        error_code: str = "SYS_001",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        extra: dict[str, Any] | None = None,
    ):
        super().__init__(detail)
        self.detail = detail
        self.error_code = error_code
        self.status_code = status_code
        self.extra = extra or {}


class EntityNotFoundException(AppException):
    """Raised when a requested resource is not found."""

    def __init__(self, detail: str = "Resource not found", error_code: str = "RES_001"):
        super().__init__(detail=detail, error_code=error_code, status_code=status.HTTP_404_NOT_FOUND)


class AuthenticationException(AppException):
    """Raised on authentication failures."""

    def __init__(self, detail: str = "Authentication failed", error_code: str = "AUTH_001"):
        super().__init__(detail=detail, error_code=error_code, status_code=status.HTTP_401_UNAUTHORIZED)


class PermissionDeniedException(AppException):
    """Raised when an authenticated actor lacks access rights."""

    def __init__(self, detail: str = "Permission denied", error_code: str = "AUTHZ_001"):
        super().__init__(detail=detail, error_code=error_code, status_code=status.HTTP_403_FORBIDDEN)


class ValidationException(AppException):
    """Raised on business validation errors."""

    def __init__(self, detail: str = "Validation failed", error_code: str = "VAL_001"):
        super().__init__(detail=detail, error_code=error_code, status_code=status.HTTP_400_BAD_REQUEST)


class IntegrityException(AppException):
    """Raised on cryptographic hash or tamper check violations."""

    def __init__(self, detail: str = "Integrity check failed", error_code: str = "DOC_004"):
        super().__init__(detail=detail, error_code=error_code, status_code=status.HTTP_409_CONFLICT)


class ConflictException(AppException):
    """Raised when a resource conflicts with an existing state (e.g. duplicate key)."""

    def __init__(self, detail: str = "Resource conflict", error_code: str = "RES_002"):
        super().__init__(detail=detail, error_code=error_code, status_code=status.HTTP_409_CONFLICT)


class StorageException(AppException):
    """Raised when object storage operations fail."""

    def __init__(self, detail: str = "Storage operation failed", error_code: str = "STR_001"):
        super().__init__(detail=detail, error_code=error_code, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


def register_exception_handlers(app: FastAPI) -> None:
    """Registers global exception handlers for the FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.warning(
            f"Handled application exception: {exc.detail} [{exc.error_code}] on {request.method} {request.url.path}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_code": exc.error_code,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        first_msg = errors[0]["msg"] if errors else "Invalid input data"
        logger.info(f"Validation error on {request.method} {request.url.path}: {errors}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": first_msg,
                "error_code": "VAL_001",
                "timestamp": datetime.now(UTC).isoformat(),
                "validation_errors": errors,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code_map = {
            401: "AUTH_001",
            403: "AUTHZ_001",
            404: "RES_001",
            405: "SYS_002",
            429: "RATE_001",
            500: "SYS_001",
        }
        error_code = code_map.get(exc.status_code, "SYS_001")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_code": error_code,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal server error occurred. Contact administrator.",
                "error_code": "SYS_001",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
