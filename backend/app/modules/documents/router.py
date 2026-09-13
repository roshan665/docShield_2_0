"""
Document Management REST API Endpoints (/api/v1/documents and /api/v1/cases/{case_id}/documents)
Enforces authentication, RBAC permission checks, explicit case membership access scoping,
and live cryptographic integrity verification.
"""

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)

from app.models.auth import User
from app.modules.auth.dependencies import require_permission
from app.modules.documents.dependencies import get_document_service
from app.modules.documents.service import DocumentService
from app.schemas.document import (
    DocumentIntegrityResponse,
    DocumentResponse,
    DocumentVersionResponse,
)

documents_router = APIRouter(tags=["Document Management"])


# ==============================================================================
# 1. Document Upload Endpoints
# ==============================================================================

@documents_router.post(
    "/cases/{case_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_case_document(
    request: Request,
    case_id: UUID,
    file: UploadFile = File(...),
    title: str = Form(...),
    document_type: str = Form(...),
    description: str | None = Form(None),
    classification: str = Form("internal"),
    current_user: User = Depends(require_permission("documents", "upload")),
    doc_service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """
    Ingests a new document file into a case.
    Validates case membership, file signatures, and stores in private S3/MinIO.
    """
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await doc_service.upload_document(
        case_id=case_id,
        title=title,
        document_type=document_type,
        upload_file=file,
        current_user=current_user,
        description=description,
        classification=classification,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@documents_router.post(
    "/documents/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document_alias(
    request: Request,
    case_id: UUID = Form(...),
    file: UploadFile = File(...),
    title: str = Form(...),
    document_type: str = Form(...),
    description: str | None = Form(None),
    classification: str = Form("internal"),
    current_user: User = Depends(require_permission("documents", "upload")),
    doc_service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """Alias for POST /cases/{case_id}/documents conforming to API_SPEC.md."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await doc_service.upload_document(
        case_id=case_id,
        title=title,
        document_type=document_type,
        upload_file=file,
        current_user=current_user,
        description=description,
        classification=classification,
        client_ip=client_ip,
        user_agent=user_agent,
    )


# ==============================================================================
# 2. Document Listing & Retrieval Endpoints
# ==============================================================================

@documents_router.get(
    "/cases/{case_id}/documents",
    response_model=list[DocumentResponse],
)
async def list_case_documents(
    case_id: UUID,
    document_type: str | None = Query(None),
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_permission("documents", "read")),
    doc_service: DocumentService = Depends(get_document_service),
) -> list[DocumentResponse]:
    """Lists all documents registered within a specific case. User must be a case member."""
    return await doc_service.list_documents_for_case(
        case_id=case_id,
        current_user=current_user,
        document_type=document_type,
        search=search,
        skip=skip,
        limit=limit,
    )


@documents_router.get(
    "/documents",
    response_model=list[DocumentResponse],
)
async def list_all_accessible_documents(
    document_type: str | None = Query(None),
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_permission("documents", "read")),
    doc_service: DocumentService = Depends(get_document_service),
) -> list[DocumentResponse]:
    """Lists documents across all cases where current user has active membership."""
    return await doc_service.list_documents_for_user(
        current_user=current_user,
        document_type=document_type,
        search=search,
        skip=skip,
        limit=limit,
    )


@documents_router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
)
async def get_document_details(
    document_id: UUID,
    current_user: User = Depends(require_permission("documents", "read")),
    doc_service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """Retrieves document details and current version metadata. User must be a member of the case."""
    return await doc_service.get_document(
        document_id=document_id,
        current_user=current_user,
    )


# ==============================================================================
# 3. Document Versioning Endpoints
# ==============================================================================

@documents_router.get(
    "/documents/{document_id}/versions",
    response_model=list[DocumentVersionResponse],
)
async def list_document_versions(
    document_id: UUID,
    current_user: User = Depends(require_permission("documents", "read")),
    doc_service: DocumentService = Depends(get_document_service),
) -> list[DocumentVersionResponse]:
    """Lists all immutable versions of a document, ordered newest first."""
    return await doc_service.list_document_versions(
        document_id=document_id,
        current_user=current_user,
    )


@documents_router.post(
    "/documents/{document_id}/versions",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_new_document_version(
    request: Request,
    document_id: UUID,
    file: UploadFile = File(...),
    change_reason: str | None = Form(None),
    current_user: User = Depends(require_permission("documents", "version")),
    doc_service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """
    Appends an immutable new version to an existing document.
    Prior versions remain unchanged and independently verifiable.
    """
    client_ip = request.client.host if request.client else None
    return await doc_service.create_document_version(
        document_id=document_id,
        upload_file=file,
        current_user=current_user,
        change_reason=change_reason,
        client_ip=client_ip,
    )


# ==============================================================================
# 4. Secure Download & Live Integrity Verification Endpoints
# ==============================================================================

@documents_router.get("/documents/{document_id}/download")
async def download_current_document(
    request: Request,
    document_id: UUID,
    current_user: User = Depends(require_permission("documents", "download")),
    doc_service: DocumentService = Depends(get_document_service),
) -> Response:
    """
    Downloads the current version of the document.
    Executes live server-side SHA-256 integrity verification before streaming bytes.
    """
    client_ip = request.client.host if request.client else None
    content, filename, mime_type = await doc_service.download_document(
        document_id=document_id,
        current_user=current_user,
        version_id=None,
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


@documents_router.get("/documents/{document_id}/versions/{version_id}/download")
async def download_specific_document_version(
    request: Request,
    document_id: UUID,
    version_id: UUID,
    current_user: User = Depends(require_permission("documents", "download")),
    doc_service: DocumentService = Depends(get_document_service),
) -> Response:
    """
    Downloads a specific historical version of the document.
    Executes live server-side SHA-256 integrity verification before streaming bytes.
    """
    client_ip = request.client.host if request.client else None
    content, filename, mime_type = await doc_service.download_document(
        document_id=document_id,
        current_user=current_user,
        version_id=version_id,
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


@documents_router.get(
    "/documents/{document_id}/verify",
    response_model=DocumentIntegrityResponse,
)
async def verify_document_integrity(
    request: Request,
    document_id: UUID,
    version_id: UUID | None = Query(None),
    current_user: User = Depends(require_permission("documents", "read")),
    doc_service: DocumentService = Depends(get_document_service),
) -> DocumentIntegrityResponse:
    """
    Triggers live cryptographic SHA-256 verification against the private S3 storage object.
    Records an integrity audit event.
    """
    client_ip = request.client.host if request.client else None
    return await doc_service.verify_integrity(
        document_id=document_id,
        current_user=current_user,
        version_id=version_id,
        client_ip=client_ip,
    )
