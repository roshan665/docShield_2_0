"""
Legal Court Export REST Router
Provides case-scoped export package generation, manifest verification, and secure downloads.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import rate_limit_export
from app.models.auth import User
from app.modules.auth.dependencies import get_current_user, require_permission
from app.modules.export.service import ExportService
from app.schemas.export import (
    CaseExportListResponse,
    CaseExportResponse,
    ExportCreateRequest,
)

export_router = APIRouter(tags=["Legal Court Export"])


async def get_export_service(session: AsyncSession = Depends(get_db)) -> ExportService:
    return ExportService(session)


@export_router.post(
    "/cases/{case_id}/exports",
    response_model=CaseExportResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_export)],
)
async def generate_case_export(
    request: Request,
    case_id: UUID,
    payload: ExportCreateRequest = ExportCreateRequest(),
    current_user: User = Depends(require_permission("cases", "read")),
    export_service: ExportService = Depends(get_export_service),
) -> CaseExportResponse:
    """
    Generates a court-ready export package with cryptographic manifest.
    Pre-verifies document and custody integrity. Only accessible to authorized case members.
    """
    client_ip = request.client.host if request.client else None
    export_record = await export_service.generate_case_export(
        case_id=case_id,
        current_user=current_user,
        include_files=payload.include_files,
        reason=payload.reason,
        client_ip=client_ip,
    )
    return CaseExportResponse.model_validate(export_record)


@export_router.get(
    "/cases/{case_id}/exports",
    response_model=CaseExportListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_case_exports(
    case_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_permission("cases", "read")),
    export_service: ExportService = Depends(get_export_service),
) -> CaseExportListResponse:
    """Lists all legal export packages generated for a case dossier."""
    items, total = await export_service.list_exports(
        case_id=case_id,
        current_user=current_user,
        skip=skip,
        limit=limit,
    )
    return CaseExportListResponse(
        items=[CaseExportResponse.model_validate(x) for x in items],
        total=total,
    )


@export_router.get(
    "/cases/{case_id}/exports/{export_id}",
    response_model=CaseExportResponse,
    status_code=status.HTTP_200_OK,
)
async def get_case_export_details(
    case_id: UUID,
    export_id: UUID,
    current_user: User = Depends(require_permission("cases", "read")),
    export_service: ExportService = Depends(get_export_service),
) -> CaseExportResponse:
    """Retrieves metadata and cryptographic manifest for a specific export package."""
    export_record = await export_service.get_export(
        case_id=case_id,
        export_id=export_id,
        current_user=current_user,
    )
    return CaseExportResponse.model_validate(export_record)


@export_router.get(
    "/cases/{case_id}/exports/{export_id}/download",
)
async def download_case_export(
    request: Request,
    case_id: UUID,
    export_id: UUID,
    current_user: User = Depends(get_current_user),
    export_service: ExportService = Depends(get_export_service),
) -> Response:
    """
    Downloads court-ready ZIP archive package.
    Executes live server-side SHA-256 integrity verification before streaming bytes.
    """
    client_ip = request.client.host if request.client else None
    content, filename, mime_type = await export_service.download_export(
        case_id=case_id,
        export_id=export_id,
        current_user=current_user,
        client_ip=client_ip,
    )
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )

