"""API v1 router aggregator."""

from fastapi import APIRouter

from app.api.v1.endpoints import health
from app.modules.ai.router import ai_router
from app.modules.audit.router import admin_audit_router, audit_router
from app.modules.auth.router import router as auth_router
from app.modules.cases.router import router as cases_router
from app.modules.documents.router import documents_router
from app.modules.evidence.router import evidence_router
from app.modules.export.router import export_router
from app.modules.roles.router import roles_router
from app.modules.search.router import search_router
from app.modules.security.router import security_router
from app.modules.users.router import admin_router, users_router

api_router = APIRouter()

# Health checks
api_router.include_router(health.router)

# Authentication endpoints
api_router.include_router(auth_router)

# User management endpoints
api_router.include_router(users_router)
api_router.include_router(admin_router)

# Role & Permission discovery
api_router.include_router(roles_router)

# Case Management
api_router.include_router(cases_router)

# Document Management
api_router.include_router(documents_router)

# AI Document Intelligence & RAG
api_router.include_router(ai_router)

# Search & RAG Intelligence (Phase 7)
api_router.include_router(search_router)

# Legal Court Export (Phase 8)
api_router.include_router(export_router)

# Evidence Management & Chain of Custody
api_router.include_router(evidence_router)

# Security Monitoring & Incident Response (Phase 8)
api_router.include_router(security_router)

# Audit Trail & Verification
api_router.include_router(audit_router)
api_router.include_router(admin_audit_router)



