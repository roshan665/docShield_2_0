"""
Main FastAPI Application Entrypoint
Configures middleware stack, CORS, exception handlers, and routing.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.api.v1.endpoints.health import liveness_check, readiness_check
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.core.middleware import (
    AccessAuditMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)

# Initialize structured logging early
setup_logging(level=settings.LOG_LEVEL)
logger = get_logger("app.lifecycle")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown events."""
    logger.info(
        f"Starting {settings.APP_NAME} [env={settings.APP_ENV}, debug={settings.DEBUG}]"
    )
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title=settings.APP_NAME,
    description="Zero-Trust, AI-Assisted Digital Evidence & Legal Case Lifecycle Platform",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# 1. Custom Exception Handlers
register_exception_handlers(app)

# 2. CORS Middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 3. Security Headers, Request ID & Access Audit Middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(AccessAuditMiddleware)

# 4. Mount API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)

# 5. Top-level health endpoints (standard container probes)
app.add_api_route("/health", liveness_check, methods=["GET"], tags=["Health"], include_in_schema=True)
app.add_api_route("/health/ready", readiness_check, methods=["GET"], tags=["Health"], include_in_schema=True)


@app.get("/", tags=["Root"])
async def root():
    """Root metadata discovery endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs" if settings.DEBUG else "Disabled in production",
        "api_v1": settings.API_V1_STR,
    }
