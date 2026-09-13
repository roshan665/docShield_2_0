"""
Document and Version Database Repository
Handles transactional queries, row-level locking for concurrency protection, and case-scoped filtering.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.case import CaseMember
from app.models.document import Document, DocumentVersion


class DocumentRepository:
    """Repository managing Document and DocumentVersion persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_document(self, document: Document) -> Document:
        """Persists a new Document row."""
        self.session.add(document)
        await self.session.flush()
        return document

    async def create_version(self, version: DocumentVersion) -> DocumentVersion:
        """Persists an immutable DocumentVersion row."""
        self.session.add(version)
        await self.session.flush()
        return version

    async def get_document_by_id(self, document_id: UUID) -> Document | None:
        """Retrieves a document with uploader, current_version, and versions preloaded."""
        query = (
            select(Document)
            .where(Document.id == document_id)
            .options(
                selectinload(Document.uploader),
                selectinload(Document.current_version).selectinload(DocumentVersion.creator),
                selectinload(Document.versions).selectinload(DocumentVersion.creator),
            )
        )
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    get_by_id = get_document_by_id

    async def get_document_for_update(self, document_id: UUID) -> Document | None:
        """
        Retrieves a document with pessimistic row-level lock (SELECT FOR UPDATE)
        to prevent concurrent version collisions.
        """
        query = (
            select(Document)
            .where(Document.id == document_id)
            .with_for_update()
            .options(
                selectinload(Document.uploader),
                selectinload(Document.current_version),
                selectinload(Document.versions),
            )
        )
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def get_version_by_id(self, version_id: UUID) -> DocumentVersion | None:
        """Retrieves a specific document version by its primary key."""
        query = (
            select(DocumentVersion)
            .where(DocumentVersion.id == version_id)
            .options(selectinload(DocumentVersion.creator))
        )
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def get_latest_version_number(self, document_id: UUID) -> int:
        """Returns the highest existing version number for a document."""
        query = select(func.coalesce(func.max(DocumentVersion.version_number), 0)).where(
            DocumentVersion.document_id == document_id
        )
        res = await self.session.execute(query)
        return res.scalar() or 0

    async def list_versions_for_document(self, document_id: UUID) -> list[DocumentVersion]:
        """Lists all immutable versions of a document, ordered newest first."""
        query = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .options(selectinload(DocumentVersion.creator))
            .order_by(DocumentVersion.version_number.desc())
        )
        res = await self.session.execute(query)
        return list(res.scalars().all())

    async def list_documents_for_case(
        self,
        case_id: UUID,
        document_type: str | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Document], int]:
        """Lists documents for a specific case with pagination and filtering."""
        base_query = (
            select(Document)
            .where(Document.case_id == case_id)
            .options(
                selectinload(Document.uploader),
                selectinload(Document.current_version).selectinload(DocumentVersion.creator),
                selectinload(Document.versions),
            )
        )

        if document_type:
            base_query = base_query.where(Document.document_type == document_type)
        if search:
            search_pat = f"%{search.strip()}%"
            base_query = base_query.where(
                or_(
                    Document.title.ilike(search_pat),
                    Document.original_filename.ilike(search_pat),
                    Document.description.ilike(search_pat),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(base_query.order_by(None).subquery())
        count_res = await self.session.execute(count_query)
        total = count_res.scalar() or 0

        # Paginate
        paged_query = base_query.order_by(Document.created_at.desc()).offset(skip).limit(limit)
        res = await self.session.execute(paged_query)
        return list(res.scalars().all()), total

    async def list_documents_for_user_cases(
        self,
        user_id: UUID,
        document_type: str | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Document], int]:
        """
        Lists documents across all cases where the user has active membership.
        Enforces zero cross-case leakage.
        """
        base_query = (
            select(Document)
            .join(CaseMember, (CaseMember.case_id == Document.case_id) & (CaseMember.user_id == user_id) & (CaseMember.is_active == True))  # noqa: E712
            .options(
                selectinload(Document.uploader),
                selectinload(Document.current_version).selectinload(DocumentVersion.creator),
                selectinload(Document.versions),
            )
        )

        if document_type:
            base_query = base_query.where(Document.document_type == document_type)
        if search:
            search_pat = f"%{search.strip()}%"
            base_query = base_query.where(
                or_(
                    Document.title.ilike(search_pat),
                    Document.original_filename.ilike(search_pat),
                    Document.description.ilike(search_pat),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(base_query.order_by(None).subquery())
        count_res = await self.session.execute(count_query)
        total = count_res.scalar() or 0

        # Paginate
        paged_query = base_query.order_by(Document.created_at.desc()).offset(skip).limit(limit)
        res = await self.session.execute(paged_query)
        return list(res.scalars().all()), total

    async def update(self, document: Document) -> Document:
        """Updates document record with updated timestamp."""
        document.updated_at = datetime.now(UTC)
        await self.session.flush()
        return document
