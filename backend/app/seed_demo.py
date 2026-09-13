"""
DocShield Demo Environment Portable Seeder
Initializes S3/MinIO storage buckets, uploads physical demo document assets,
seeds roles/permissions/users, and deterministically reconstructs cases,
evidence items, hash-chained custody events, extracted legal entities,
and pgvector embeddings for a complete reproducible demo deployment.
"""

import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import delete, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.logging import get_logger  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.ai import DocumentEmbedding, ExtractedEntity  # noqa: E402
from app.models.audit import AuditEvent  # noqa: E402
from app.models.auth import Permission, Role, RolePermission, User  # noqa: E402
from app.models.case import Case, CaseMember  # noqa: E402
from app.models.custody import EvidenceCustodyEvent  # noqa: E402
from app.models.document import Document, DocumentVersion  # noqa: E402
from app.models.evidence import Evidence  # noqa: E402
from app.modules.audit.service import AuditService  # noqa: E402
from app.modules.evidence.custody_chain import (  # noqa: E402
    GENESIS_HASH,
    canonicalize_custody_event,
    compute_custody_event_hash,
    verify_custody_chain,
)
from app.storage.s3 import S3StorageService  # noqa: E402

logger = get_logger(__name__)

FIXTURES_PATH = backend_dir / "demo_data" / "fixtures.json"
FILES_DIR = backend_dir / "demo_data" / "files"
EMBEDDINGS_PATH = backend_dir / "demo_data" / "embeddings.json"


async def ensure_storage(storage: S3StorageService) -> bool:
    """Ensure MinIO/S3 buckets exist."""
    print(" [1/6] Provisioning Object Storage Buckets...")
    try:
        storage.ensure_bucket_exists(settings.S3_BUCKET_DOCUMENTS)
        storage.ensure_bucket_exists(settings.S3_BUCKET_EVIDENCE)
        print(f"  ✓ Verified buckets: '{settings.S3_BUCKET_DOCUMENTS}', '{settings.S3_BUCKET_EVIDENCE}'")
        return True
    except Exception as e:
        print(f"  ✗ Storage initialization warning: {e}")
        return False


# 1. System Roles definition
ROLES_DATA = [
    {
        "name": "investigator",
        "display_name": "Investigating Officer",
        "description": "Lead and investigating officers responsible for case investigation and evidence collection.",
        "is_system_role": True,
    },
    {
        "name": "forensic_expert",
        "display_name": "Forensic Expert / Analyst",
        "description": "Forensic lab personnel analyzing physical and digital evidence and generating reports.",
        "is_system_role": True,
    },
    {
        "name": "legal_officer",
        "display_name": "Legal Officer / Prosecutor",
        "description": "Public prosecutors and legal counsels preparing court filings and legal packages.",
        "is_system_role": True,
    },
    {
        "name": "supervisor",
        "display_name": "Supervisory Officer / SP",
        "description": "Superintendents of Police and division supervisors reviewing case milestones and audits.",
        "is_system_role": True,
    },
    {
        "name": "system_admin",
        "display_name": "System Administrator",
        "description": "Infrastructure, user management, and security monitoring administrators.",
        "is_system_role": True,
    },
]

# 2. Granular Permissions definition
PERMISSIONS_DATA = [
    ("cases", "create", "Create new legal investigation case"),
    ("cases", "read", "Read assigned case details and summary"),
    ("cases", "update", "Update case metadata and investigation status"),
    ("cases", "close", "Close or archive completed cases"),
    ("cases", "add_members", "Assign investigators and experts to a case team"),
    ("documents", "upload", "Upload new document files into case repository"),
    ("documents", "read", "Read and view document metadata"),
    ("documents", "download", "Download document file content"),
    ("documents", "version", "Create newer version of existing document"),
    ("evidence", "register", "Register physical or digital evidence record"),
    ("evidence", "read", "View evidence metadata and integrity status"),
    ("evidence", "transfer", "Initiate custody transfer to another officer"),
    ("evidence", "receive", "Acknowledge and accept incoming evidence custody"),
    ("evidence", "verify", "Execute cryptographic SHA-256 integrity checks"),
    ("evidence", "download", "Download forensic digital evidence image/file"),
    ("custody", "view", "View chronological hash-chained chain of custody"),
    ("audit", "view_case", "View case-scoped audit log entries"),
    ("audit", "view_system", "View system-wide audit records"),
    ("search", "traditional", "Execute structured filter search"),
    ("search", "semantic", "Execute natural language semantic vector search"),
    ("ai", "ask", "Query AI RAG case assistant"),
    ("export", "legal_package", "Generate court-ready document/evidence zip package"),
    ("users", "create", "Register and provision new user accounts"),
    ("users", "read", "View user account profiles and status"),
    ("users", "update", "Update user account profile details"),
    ("users", "delete", "Deactivate or purge user accounts"),
    ("users", "status", "Activate, deactivate, or unlock user accounts"),
    ("users", "reset_password", "Perform administrative password reset"),
    ("roles", "manage", "Assign and modify system roles and permissions"),
    ("roles", "view", "Inspect system roles and permission matrices"),
    ("security", "view_events", "Inspect security alerts, brute force attempts, and tampering logs"),
    ("security", "resolve_alerts", "Mark security incident alerts as resolved"),
    ("system", "admin_panel", "Access privileged system administration interface"),
    ("system", "health", "Inspect internal infrastructure readiness diagnostics"),
]

# 3. Role-Permission Matrix Mapping
ROLE_PERMISSIONS_MAPPING = {
    "investigator": [
        ("cases", "create"), ("cases", "read"), ("cases", "update"), ("cases", "add_members"),
        ("documents", "upload"), ("documents", "read"), ("documents", "download"), ("documents", "version"),
        ("evidence", "register"), ("evidence", "read"), ("evidence", "transfer"), ("evidence", "receive"),
        ("evidence", "verify"), ("evidence", "download"),
        ("custody", "view"),
        ("audit", "view_case"),
        ("search", "traditional"), ("search", "semantic"),
        ("ai", "ask"),
    ],
    "forensic_expert": [
        ("cases", "read"),
        ("documents", "upload"), ("documents", "read"), ("documents", "download"), ("documents", "version"),
        ("evidence", "read"), ("evidence", "transfer"), ("evidence", "receive"), ("evidence", "verify"),
        ("evidence", "download"),
        ("custody", "view"),
        ("audit", "view_case"),
        ("search", "traditional"), ("search", "semantic"),
        ("ai", "ask"),
    ],
    "legal_officer": [
        ("cases", "read"),
        ("documents", "upload"), ("documents", "read"), ("documents", "download"), ("documents", "version"),
        ("evidence", "read"), ("evidence", "receive"), ("evidence", "verify"), ("evidence", "download"),
        ("custody", "view"),
        ("audit", "view_case"),
        ("search", "traditional"), ("search", "semantic"),
        ("ai", "ask"),
        ("export", "legal_package"),
    ],
    "supervisor": [
        ("cases", "create"), ("cases", "read"), ("cases", "update"), ("cases", "close"), ("cases", "add_members"),
        ("documents", "upload"), ("documents", "read"), ("documents", "download"), ("documents", "version"),
        ("evidence", "register"), ("evidence", "read"), ("evidence", "transfer"), ("evidence", "receive"),
        ("evidence", "verify"), ("evidence", "download"),
        ("custody", "view"),
        ("audit", "view_case"),
        ("search", "traditional"), ("search", "semantic"),
        ("ai", "ask"),
        ("export", "legal_package"),
        ("security", "view_events"),
    ],
    "system_admin": [
        ("users", "create"), ("users", "read"), ("users", "update"), ("users", "delete"),
        ("users", "status"), ("users", "reset_password"),
        ("roles", "manage"), ("roles", "view"),
        ("audit", "view_system"),
        ("security", "view_events"), ("security", "resolve_alerts"),
        ("system", "admin_panel"), ("system", "health"),
    ],
}


async def seed_roles_and_permissions(session: AsyncSession) -> dict[str, Role]:
    """Ensure standard system roles and permissions exist."""
    print(" [2/6] Seeding RBAC Roles & Permissions Matrix...")

    # 1. Roles
    role_objs = {}
    for r_data in ROLES_DATA:
        res = await session.execute(select(Role).where(Role.name == r_data["name"]))
        existing = res.scalar_one_or_none()
        if not existing:
            role = Role(
                name=r_data["name"],
                display_name=r_data["display_name"],
                description=r_data["description"],
                is_system_role=r_data["is_system_role"],
            )
            session.add(role)
            await session.flush()
            role_objs[r_data["name"]] = role
        else:
            role_objs[r_data["name"]] = existing

    # 2. Permissions
    perm_objs = {}
    for res_name, act_name, desc in PERMISSIONS_DATA:
        q = select(Permission).where(Permission.resource == res_name, Permission.action == act_name)
        res = await session.execute(q)
        existing = res.scalar_one_or_none()
        key = (res_name, act_name)
        if not existing:
            perm = Permission(resource=res_name, action=act_name, description=desc)
            session.add(perm)
            await session.flush()
            perm_objs[key] = perm
        else:
            perm_objs[key] = existing

    # 3. Role-Permission mappings
    for role_name, perms in ROLE_PERMISSIONS_MAPPING.items():
        role = role_objs[role_name]
        for p_key in perms:
            perm = perm_objs[p_key]
            link_q = select(RolePermission).where(
                RolePermission.role_id == role.id,
                RolePermission.permission_id == perm.id,
            )
            link_res = await session.execute(link_q)
            if not link_res.scalar_one_or_none():
                link = RolePermission(role_id=role.id, permission_id=perm.id)
                session.add(link)
    await session.flush()
    print(f"  ✓ Verified {len(role_objs)} roles and {len(perm_objs)} granular permissions")
    return role_objs


async def seed_users(session: AsyncSession, users_data: list[dict], role_objs: dict[str, Role]) -> dict[str, User]:
    """Upsert demo user accounts with verified Argon2id credentials."""
    print(" [3/6] Seeding Demo User Accounts...")
    user_objs = {}
    for u_data in users_data:
        res = await session.execute(select(User).where(User.email == u_data["email"]))
        user = res.scalar_one_or_none()
        role = role_objs[u_data["role_name"]]
        if not user:
            user = User(
                employee_id=u_data["employee_id"],
                email=u_data["email"],
                full_name=u_data["full_name"],
                password_hash=hash_password(u_data["password"]),
                role_id=role.id,
                department=u_data.get("department", "Law Enforcement"),
                designation=u_data.get("designation", "Officer"),
                is_active=True,
                is_locked=False,
            )
            session.add(user)
            await session.flush()
            print(f"  + Created user: {u_data['email']} ({role.display_name})")
        else:
            # Ensure active & unlocked with valid demo password
            user.is_active = True
            user.is_locked = False
            user.failed_login_attempts = 0
            user.locked_until = None
            user.role_id = role.id
            user.password_hash = hash_password(u_data["password"])
            await session.flush()
            print(f"  ✓ Existing user: {u_data['email']} ({role.display_name})")
        user_objs[u_data["email"]] = user
    return user_objs


async def seed_cases_and_evidence(
    session: AsyncSession,
    storage: S3StorageService,
    cases_data: list[dict],
    user_objs: dict[str, User],
    emb_map: dict[str, list[float]],
) -> dict[str, int]:
    """Deterministic, idempotent ingestion of cases, documents, evidence, custody, and embeddings."""
    print(" [4/6] Seeding Flagship Cases, Documents, & Evidence Vault...")
    stats = {
        "cases_seeded": 0,
        "documents_seeded": 0,
        "evidence_seeded": 0,
        "custody_events_seeded": 0,
        "embeddings_seeded": 0,
    }

    audit_svc = AuditService(session)

    for c_data in cases_data:
        # A. Case Upsert
        c_res = await session.execute(select(Case).where(Case.case_number == c_data["case_number"]))
        case = c_res.scalar_one_or_none()
        lead_user = user_objs[c_data["lead_officer_email"]]

        if not case:
            case = Case(
                case_number=c_data["case_number"],
                fir_number=c_data.get("fir_number"),
                title=c_data["title"],
                description=c_data.get("description"),
                status=c_data.get("status", "open"),
                priority=c_data.get("priority", "medium"),
                category=c_data.get("category"),
                police_station=c_data.get("police_station"),
                district=c_data.get("district"),
                state=c_data.get("state"),
                investigating_officer_id=lead_user.id,
                created_by=lead_user.id,
            )
            session.add(case)
            await session.flush()
            stats["cases_seeded"] += 1
            print(f"  + Case [{case.case_number}]: {case.title} (Status: {case.status})")

            # Record Case Creation Audit Event
            await audit_svc.record_event(
                action="case:create",
                resource_type="case",
                resource_id=case.id,
                actor_id=lead_user.id,
                case_id=case.id,
                details={"case_number": case.case_number, "priority": case.priority, "status": case.status},
            )
        else:
            print(f"  ✓ Case [{case.case_number}]: {case.title} already exists")

        # B. Case Memberships
        for m_data in c_data.get("members", []):
            m_user = user_objs.get(m_data["email"])
            if not m_user:
                continue
            mem_q = select(CaseMember).where(
                CaseMember.case_id == case.id,
                CaseMember.user_id == m_user.id,
                CaseMember.is_active == True,  # noqa: E712
            )
            mem_res = await session.execute(mem_q)
            if not mem_res.scalar_one_or_none():
                cm = CaseMember(
                    case_id=case.id,
                    user_id=m_user.id,
                    role_in_case=m_data["role_in_case"],
                    added_by=lead_user.id,
                    added_at=datetime.now(UTC),
                    is_active=True,
                )
                session.add(cm)
                await session.flush()

        # C. Documents & Document Versions
        for d_data in c_data.get("documents", []):
            d_res = await session.execute(
                select(Document).where(Document.case_id == case.id, Document.title == d_data["title"])
            )
            doc = d_res.scalar_one_or_none()
            doc_uploader = user_objs.get(d_data.get("uploader_email", c_data["lead_officer_email"]))

            filename = d_data["filename"]
            file_path = FILES_DIR / filename
            if not file_path.exists():
                print(f"    ! Warning: asset file '{filename}' missing on disk, skipping.")
                continue

            file_bytes = file_path.read_bytes()
            file_size = len(file_bytes)
            file_hash = hashlib.sha256(file_bytes).hexdigest()

            if not doc:
                doc = Document(
                    case_id=case.id,
                    title=d_data["title"],
                    description=d_data.get("description", d_data.get("summary")),
                    document_type=d_data.get("document_type", "other"),
                    classification=d_data.get("classification", "confidential"),
                    status="processed",
                    original_filename=filename,
                    mime_type=d_data["mime_type"],
                    file_size_bytes=file_size,
                    uploaded_by=doc_uploader.id,
                    ai_processed=True,
                    ai_classification=d_data.get("document_type"),
                    ai_confidence=0.95,
                    ocr_text=d_data.get("ocr_text"),
                    summary=d_data.get("summary"),
                )
                session.add(doc)
                await session.flush()
                stats["documents_seeded"] += 1

                # Storage Key for Version 1
                storage_key = f"cases/{case.id}/documents/{doc.id}/versions/v1"
                storage_bucket = settings.S3_BUCKET_DOCUMENTS

                # Upload to MinIO/S3 if not exists
                try:
                    if not storage.exists(storage_key, storage_bucket):
                        storage.upload(
                            file_data=file_bytes,
                            key=storage_key,
                            bucket=storage_bucket,
                            content_type=d_data["mime_type"],
                            metadata={"case_id": str(case.id), "doc_id": str(doc.id)},
                        )
                except Exception as upload_err:
                    logger.warning(f"Could not upload {storage_key} to MinIO: {upload_err}")

                # Create DocumentVersion v1
                v1 = DocumentVersion(
                    document_id=doc.id,
                    version_number=1,
                    storage_key=storage_key,
                    storage_bucket=storage_bucket,
                    file_hash_sha256=file_hash,
                    file_size_bytes=file_size,
                    mime_type=d_data["mime_type"],
                    original_filename=filename,
                    sanitized_filename=filename,
                    created_by=doc_uploader.id,
                    is_original=True,
                    integrity_status="verified",
                    last_verified_at=datetime.now(UTC),
                )
                session.add(v1)
                await session.flush()

                doc.current_version_id = v1.id
                await session.flush()

                # Audit Event for upload
                await audit_svc.record_event(
                    action="document:upload",
                    resource_type="document",
                    resource_id=doc.id,
                    actor_id=doc_uploader.id,
                    case_id=case.id,
                    details={"title": doc.title, "filename": filename, "sha256": file_hash},
                )

                # Seed Extracted Entities
                for ent in d_data.get("entities", []):
                    ee = ExtractedEntity(
                        document_id=doc.id,
                        entity_type=ent["entity_type"],
                        entity_value=ent["entity_value"],
                        confidence=ent.get("confidence", 0.95),
                        source="ai_extracted",
                        verified=True,
                    )
                    session.add(ee)
                await session.flush()

                # Seed Vector Embeddings if chunk available
                for idx, chunk in enumerate(d_data.get("chunks", [])):
                    if chunk in emb_map:
                        vector = emb_map[chunk]
                        emb_record = DocumentEmbedding(
                            document_id=doc.id,
                            case_id=case.id,
                            version_id=v1.id,
                            chunk_id=f"{doc.id}_chunk_{idx}",
                            chunk_index=idx,
                            chunk_text=chunk,
                            embedding=vector,
                            model_name="models/text-embedding-004",
                            vector_dimensions=768,
                            is_searchable=True,
                        )
                        session.add(emb_record)
                        stats["embeddings_seeded"] += 1
                await session.flush()

                # Handle supplementary version 2 if defined
                for supp_v in d_data.get("versions", []):
                    v2_file = FILES_DIR / supp_v["filename"]
                    if v2_file.exists():
                        v2_bytes = v2_file.read_bytes()
                        v2_size = len(v2_bytes)
                        v2_hash = hashlib.sha256(v2_bytes).hexdigest()
                        v2_uploader = user_objs.get(supp_v.get("uploader_email", doc_uploader.email))
                        v2_storage_key = f"cases/{case.id}/documents/{doc.id}/versions/v2"

                        try:
                            if not storage.exists(v2_storage_key, storage_bucket):
                                storage.upload(
                                    file_data=v2_bytes,
                                    key=v2_storage_key,
                                    bucket=storage_bucket,
                                    content_type=supp_v["mime_type"],
                                    metadata={"case_id": str(case.id), "doc_id": str(doc.id)},
                                )
                        except Exception as upload_err:
                            logger.warning(f"Could not upload v2: {upload_err}")

                        v2 = DocumentVersion(
                            document_id=doc.id,
                            version_number=supp_v["version_number"],
                            storage_key=v2_storage_key,
                            storage_bucket=storage_bucket,
                            file_hash_sha256=v2_hash,
                            file_size_bytes=v2_size,
                            mime_type=supp_v["mime_type"],
                            original_filename=supp_v["filename"],
                            sanitized_filename=supp_v["filename"],
                            change_reason=supp_v.get("change_reason"),
                            created_by=v2_uploader.id,
                            is_original=False,
                            integrity_status="verified",
                            last_verified_at=datetime.now(UTC),
                        )
                        session.add(v2)
                        await session.flush()
                        doc.current_version_id = v2.id
                        await session.flush()

        # D. Evidence Records & Cryptographic Custody Chain
        for ev_data in c_data.get("evidence", []):
            ev_res = await session.execute(
                select(Evidence).where(Evidence.evidence_number == ev_data["evidence_number"])
            )
            ev = ev_res.scalar_one_or_none()
            reg_user = user_objs[ev_data["registered_by_email"]]
            cur_custodian = user_objs[ev_data["current_custodian_email"]]

            file_hash = None
            storage_key = None
            storage_bucket = None
            file_size = None
            mime_type = None

            if ev_data.get("filename"):
                ev_file = FILES_DIR / ev_data["filename"]
                if ev_file.exists():
                    ev_bytes = ev_file.read_bytes()
                    file_size = len(ev_bytes)
                    file_hash = hashlib.sha256(ev_bytes).hexdigest()
                    storage_bucket = settings.S3_BUCKET_DOCUMENTS
                    storage_key = f"cases/{case.id}/evidence/{ev_data['evidence_number']}/{ev_data['filename']}"
                    mime_type = "application/octet-stream"
                    try:
                        if not storage.exists(storage_key, storage_bucket):
                            storage.upload(
                                file_data=ev_bytes,
                                key=storage_key,
                                bucket=storage_bucket,
                                content_type=mime_type,
                            )
                    except Exception as upload_err:
                        logger.warning(f"Could not upload evidence file: {upload_err}")

            if not ev:
                ev = Evidence(
                    case_id=case.id,
                    evidence_number=ev_data["evidence_number"],
                    title=ev_data["title"],
                    description=ev_data.get("description"),
                    evidence_type=ev_data.get("evidence_type", "digital_document"),
                    status=ev_data.get("status", "registered"),
                    sensitivity_level=ev_data.get("sensitivity_level", "standard"),
                    original_file_hash=file_hash,
                    current_file_hash=file_hash,
                    integrity_status="verified",
                    current_custodian_id=cur_custodian.id,
                    pending_custodian_id=None,
                    transfer_pending=False,
                    storage_key=storage_key,
                    storage_bucket=storage_bucket,
                    file_size_bytes=file_size,
                    mime_type=mime_type,
                    collection_date=datetime.now(UTC) - timedelta(days=4),
                    collection_location=ev_data.get("collection_location"),
                    source=ev_data.get("source"),
                    registered_by_id=reg_user.id,
                )
                session.add(ev)
                await session.flush()
                stats["evidence_seeded"] += 1
            else:
                # Update existing evidence record to link to this demo case
                ev.case_id = case.id
                ev.title = ev_data["title"]
                ev.description = ev_data.get("description")
                ev.evidence_type = ev_data.get("evidence_type", "digital_document")
                ev.status = ev_data.get("status", "registered")
                ev.sensitivity_level = ev_data.get("sensitivity_level", "standard")
                ev.current_custodian_id = cur_custodian.id
                ev.registered_by_id = reg_user.id
                if file_hash:
                    ev.original_file_hash = file_hash
                    ev.current_file_hash = file_hash
                    ev.storage_key = storage_key
                    ev.storage_bucket = storage_bucket
                    ev.file_size_bytes = file_size
                    ev.mime_type = mime_type
                await session.flush()

            # Check existing custody events
            evt_check = await session.execute(
                select(EvidenceCustodyEvent)
                .where(EvidenceCustodyEvent.evidence_id == ev.id)
                .order_by(EvidenceCustodyEvent.created_at.asc())
            )
            existing_evts = list(evt_check.scalars().all())
            v_res = verify_custody_chain(existing_evts)

            # If invalid or fewer events than planned, delete and re-seed clean sequential chain
            expected_count = len(ev_data.get("custody_events", []))
            if not v_res["valid"] or len(existing_evts) < expected_count:
                await session.execute(
                    delete(EvidenceCustodyEvent).where(EvidenceCustodyEvent.evidence_id == ev.id)
                )
                await session.flush()

                # Replay Custody Events Sequentially with Strict Hash-Chaining
                prev_hash = GENESIS_HASH
                for evt_info in ev_data.get("custody_events", []):
                    from_u = user_objs.get(evt_info["from_user_email"]) if evt_info.get("from_user_email") else None
                    to_u = user_objs[evt_info["to_user_email"]]
                    evt_time = datetime.now(UTC) - timedelta(hours=evt_info.get("hours_ago", 10))

                    canonical_bytes = canonicalize_custody_event(
                        evidence_id=ev.id,
                        event_type=evt_info["event_type"],
                        from_user_id=from_u.id if from_u else None,
                        to_user_id=to_u.id,
                        reason=evt_info["reason"],
                        file_hash_at_event=file_hash,
                        timestamp=evt_time,
                        location=evt_info.get("location"),
                    )
                    event_hash = compute_custody_event_hash(canonical_bytes, prev_hash)

                    custody_record = EvidenceCustodyEvent(
                        evidence_id=ev.id,
                        case_id=case.id,
                        event_type=evt_info["event_type"],
                        from_user_id=from_u.id if from_u else None,
                        to_user_id=to_u.id,
                        reason=evt_info["reason"],
                        location=evt_info.get("location"),
                        file_hash_at_event=file_hash,
                        previous_event_hash=prev_hash,
                        event_hash=event_hash,
                        acknowledgement_status="acknowledged",
                        acknowledged_at=evt_time,
                        created_at=evt_time,
                    )
                    session.add(custody_record)
                    await session.flush()
                    prev_hash = event_hash
                    stats["custody_events_seeded"] += 1

            # Record Audit Event for Evidence Registration if not logged yet
            audit_check = await session.execute(
                select(AuditEvent).where(
                    AuditEvent.resource_type == "evidence",
                    AuditEvent.resource_id == ev.id,
                    AuditEvent.action == "evidence:register",
                )
            )
            if not audit_check.scalar_one_or_none():
                await audit_svc.record_event(
                    action="evidence:register",
                    resource_type="evidence",
                    resource_id=ev.id,
                    actor_id=reg_user.id,
                    case_id=case.id,
                    details={
                        "evidence_number": ev.evidence_number,
                        "title": ev.title,
                        "type": ev.evidence_type,
                        "custodian": cur_custodian.email,
                    },
                )

    await session.commit()
    return stats


async def verify_seeded_environment(session: AsyncSession, seeded_case_numbers: list[str] | None = None) -> bool:
    """Run cryptographic validation on custody chains and audit ledgers."""
    print(" [5/6] Verifying Cryptographic Chains & Data Integrity...")

    # 1. Verify Custody Chains for Seeded Cases
    if seeded_case_numbers:
        case_subq = select(Case.id).where(Case.case_number.in_(seeded_case_numbers))
        ev_q = select(Evidence).where(Evidence.case_id.in_(case_subq))
    else:
        ev_q = select(Evidence)

    ev_res = await session.execute(ev_q)
    all_ev = ev_res.scalars().all()
    all_custody_valid = True

    for ev in all_ev:
        evt_q = (
            select(EvidenceCustodyEvent)
            .where(EvidenceCustodyEvent.evidence_id == ev.id)
            .order_by(EvidenceCustodyEvent.created_at.asc())
        )
        evt_res = await session.execute(evt_q)
        events = list(evt_res.scalars().all())
        res = verify_custody_chain(events)
        if not res["valid"]:
            print(f"  ✗ Custody chain broken for {ev.evidence_number}: {res['reason']}")
            all_custody_valid = False
        else:
            print(f"  ✓ Custody chain verified for {ev.evidence_number} ({len(events)} events, Tip: {res['tip_hash'][:10]}...)")

    # 2. Verify Audit Chain
    audit_svc = AuditService(session)
    audit_verify = await audit_svc.verify_chain()
    if audit_verify["valid"]:
        print(f"  ✓ Audit ledger verified unbroken ({audit_verify['events_checked']} events checked)")
    else:
        print(f"  ✗ Audit chain broken: {audit_verify['reason']}")

    return all_custody_valid and audit_verify["valid"]


async def print_dashboard_summary(session: AsyncSession):
    """Print overall summary of live records in database."""
    print(" [6/6] Live Seeded Database Status:")
    u_cnt = (await session.execute(select(text("count(*)")).select_from(User))).scalar()
    c_cnt = (await session.execute(select(text("count(*)")).select_from(Case))).scalar()
    d_cnt = (await session.execute(select(text("count(*)")).select_from(Document))).scalar()
    e_cnt = (await session.execute(select(text("count(*)")).select_from(Evidence))).scalar()
    ce_cnt = (await session.execute(select(text("count(*)")).select_from(EvidenceCustodyEvent))).scalar()
    a_cnt = (await session.execute(select(text("count(*)")).select_from(AuditEvent))).scalar()
    emb_cnt = (await session.execute(select(text("count(*)")).select_from(DocumentEmbedding))).scalar()

    print(f"    • Users:                {u_cnt}")
    print(f"    • Active Cases:         {c_cnt}")
    print(f"    • Documents in Vault:   {d_cnt}")
    print(f"    • Evidence in Custody:  {e_cnt}")
    print(f"    • Custody Ledger Events:{ce_cnt}")
    print(f"    • Cryptographic Audits: {a_cnt}")
    print(f"    • pgvector Embeddings:  {emb_cnt}")


async def seed_demo_data():
    """Main entrypoint to execute demo data seeding."""
    print("=" * 65)
    print("  DOCSHIELD — Portable Demo Environment Initialization")
    print("=" * 65)

    if not FIXTURES_PATH.exists():
        print(f"Error: Fixtures file not found at {FIXTURES_PATH}")
        sys.exit(1)

    with open(FIXTURES_PATH, encoding="utf-8") as f:
        fixtures = json.load(f)

    emb_map = {}
    if EMBEDDINGS_PATH.exists():
        with open(EMBEDDINGS_PATH, encoding="utf-8") as f:
            emb_list = json.load(f)
            emb_map = {item["chunk_text"]: item["embedding"] for item in emb_list}

    storage = S3StorageService()
    await ensure_storage(storage)

    async with AsyncSessionLocal() as session:
        # Step 2: Roles & Permissions
        role_objs = await seed_roles_and_permissions(session)

        # Step 3: Users
        user_objs = await seed_users(session, fixtures.get("users", []), role_objs)

        # Step 4: Cases, Documents, Evidence, Custody, Embeddings
        _ = await seed_cases_and_evidence(
            session,
            storage,
            fixtures.get("cases", []),
            user_objs,
            emb_map,
        )

        # Step 5: Validation
        seeded_case_nums = [c["case_number"] for c in fixtures.get("cases", [])]
        verified = await verify_seeded_environment(session, seeded_case_numbers=seeded_case_nums)

        # Step 6: Summary
        await print_dashboard_summary(session)

        print("=" * 65)
        if verified:
            print("  ✓ DOCSHIELD DEMO DATA INITIALIZATION COMPLETED SUCCESSFULLY")
        else:
            print("  ! COMPLETED WITH CRYPTOGRAPHIC INTEGRITY WARNINGS")
        print("=" * 65)


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
