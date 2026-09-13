# Implementation Roadmap — Secure Digital Evidence & Legal Case Lifecycle Management Platform

---

## 1. Development Phases

### Phase 0: Project Foundation (Week 1)

| Task | Description | Priority |
|------|-------------|----------|
| Repository setup | Git, .gitignore, README, docs/ | 🔴 Critical |
| Backend scaffold | FastAPI project, core/ modules, config, database setup | 🔴 Critical |
| Frontend scaffold | Next.js project, TypeScript, Tailwind, shadcn/ui | 🔴 Critical |
| Docker Compose | postgres, minio, redis, backend, frontend, celery-worker | 🔴 Critical |
| Database setup | SQLAlchemy models, Alembic migrations, initial schema | 🔴 Critical |
| Environment config | .env.example, Pydantic Settings | 🔴 Critical |
| CI foundation | Basic test runner, linting | 🟡 Medium |

**Deliverable**: Running dev environment with empty API and frontend shell.

---

### Phase 1: Authentication & User Management (Week 2)

| Task | Description | Priority |
|------|-------------|----------|
| User model + migration | users table, roles, permissions, user_roles, role_permissions | 🔴 Critical |
| Seed data | Default roles + permissions | 🔴 Critical |
| Auth service | Login, JWT generation, password hashing (Argon2id) | 🔴 Critical |
| Auth endpoints | POST /login, /refresh, /logout, GET /me | 🔴 Critical |
| Auth middleware | JWT validation, current_user dependency | 🔴 Critical |
| RBAC enforcement | Role checking, permission checking dependencies | 🔴 Critical |
| Account lockout | Failed login tracking, lockout logic | 🟠 High |
| User management API | CRUD users, role assignment (admin) | 🟠 High |
| Login page (frontend) | Login form, token storage, auth context | 🔴 Critical |
| Protected routes | Auth guard, redirect to login | 🔴 Critical |
| Dashboard layout | Sidebar, header, role-based navigation | 🟠 High |
| Auth tests | Login, token refresh, RBAC, lockout tests | 🔴 Critical |

**Deliverable**: Working login, role-based UI, protected API endpoints.

---

### Phase 2: Case Management (Week 3)

| Task | Description | Priority |
|------|-------------|----------|
| Case models + migration | cases, case_members tables | 🔴 Critical |
| Case service | Create, read, update, status management | 🔴 Critical |
| Case membership | Add/remove members, role-in-case | 🔴 Critical |
| Case access control | case_members-based authorization | 🔴 Critical |
| Case API endpoints | Full CRUD + member management | 🔴 Critical |
| Case list page | Filterable, sortable case listing | 🟠 High |
| Case detail page | Tabs: overview, documents, evidence, audit | 🟠 High |
| Case creation form | Form with validation | 🟠 High |
| Audit trail foundation | AuditEvent model, audit service, hash chaining | 🔴 Critical |
| Audit logging | Log case CRUD operations | 🔴 Critical |
| Case tests | CRUD, membership, access control tests | 🟠 High |

**Deliverable**: Case management with team assignment, audit logging.

---

### Phase 3: Document Management + Storage (Week 4)

| Task | Description | Priority |
|------|-------------|----------|
| S3 client | MinIO/S3 abstraction (upload, download, presigned URLs) | 🔴 Critical |
| File validator | MIME check, size limit, extension whitelist, filename sanitization | 🔴 Critical |
| Document models + migration | documents, document_versions tables | 🔴 Critical |
| Document upload service | Validate → Hash → Store → Create records | 🔴 Critical |
| Version control | Create new version, list versions, download specific version | 🔴 Critical |
| Document API endpoints | Upload, download, versions, metadata | 🔴 Critical |
| Integrity service | SHA-256 hash generation + verification | 🔴 Critical |
| Integrity API | Verify document integrity endpoint | 🔴 Critical |
| Document upload UI | File upload with progress, case selection | 🟠 High |
| Document list/detail UI | Document listing, version history, integrity badge | 🟠 High |
| Audit logging | Log document operations | 🔴 Critical |
| Document tests | Upload, download, versioning, integrity, security tests | 🟠 High |

**Deliverable**: Secure document upload, versioning, SHA-256 integrity verification.

---

### Phase 4: Evidence Management + Chain of Custody (Week 5)

| Task | Description | Priority |
|------|-------------|----------|
| Evidence models + migration | evidence, evidence_custody_events tables | 🔴 Critical |
| Evidence service | Register, update, verify integrity | 🔴 Critical |
| Custody service | Transfer, receive, hash-chained events | 🔴 Critical |
| Custody hash chaining | Compute event_hash = SHA256(... + previous_event_hash) | 🔴 Critical |
| Custody chain verification | Verify entire chain integrity | 🔴 Critical |
| Evidence API endpoints | Register, transfer, receive, verify, custody chain | 🔴 Critical |
| Evidence registration UI | Registration form with case linkage | 🟠 High |
| Custody transfer UI | Transfer dialog, custody chain timeline visualization | 🟠 High |
| Evidence detail page | Integrity status, custody history, linked documents | 🟠 High |
| Notifications foundation | Notification model, service, evidence transfer notifications | 🟠 High |
| Audit logging | Log evidence + custody operations | 🔴 Critical |
| Evidence + custody tests | Transfer flow, chain integrity, IDOR tests | 🔴 Critical |

**Deliverable**: Evidence registration, custody transfers with hash-chained events, integrity verification.

---

### Phase 5: AI Document Intelligence (Week 6)

| Task | Description | Priority |
|------|-------------|----------|
| Celery setup | Worker configuration, Redis broker | 🟠 High |
| OCR pipeline | Tesseract integration for scanned documents | 🟠 High |
| Text extraction | PDF, DOCX, image text extraction | 🟠 High |
| Gemini integration | API client, classification prompt, entity extraction prompt | 🟠 High |
| Classification service | Document type classification with confidence | 🟠 High |
| Entity extraction service | Named entities from legal documents | 🟠 High |
| Summary generation | Document summarization | 🟡 Medium |
| AI pipeline orchestration | Celery task: OCR → Classify → Extract → Summarize | 🟠 High |
| AI results storage | document_metadata, extracted_entities tables | 🟠 High |
| AI processing status | Status tracking, processing notifications | 🟡 Medium |
| AI results UI | Classification badge, entities list, summary display, confidence indicators | 🟡 Medium |
| AI endpoints | Classify, extract, summarize, processing status | 🟠 High |

**Deliverable**: Automatic document processing pipeline with OCR, classification, and entity extraction.

---

### Phase 6: Search, Semantic RAG & Universal Dashboard (Week 7-8) — Promoted to MVP

| Task | Description | Priority |
|------|-------------|----------|
| Traditional search | Filter by case number, FIR, document type, date, etc. | 🟠 High |
| Full-text search | PostgreSQL tsvector search on OCR text | 🟠 High |
| Search API | POST /search/documents, /search/entities | 🟠 High |
| Search UI | Search page with filters, results display | 🟠 High |
| Embedding generation | text-embedding-004 integration in AI pipeline (768 dims) | 🔴 Critical |
| Embedding storage | pgvector, document_embeddings table (with case_id), HNSW index | 🔴 Critical |
| Semantic search service | Vector similarity search strictly scoped to user's authorized cases | 🔴 Critical |
| Semantic search API | POST /api/v1/search/semantic | 🔴 Critical |
| RAG case assistant | Context retrieval + Gemini Flash generation with source citations | 🔴 Critical |
| RAG API | POST /api/v1/ai/ask | 🔴 Critical |
| AI assistant UI | Chat interface with source citations and "AI Generated" warning | 🟠 High |
| Universal Dashboard API | Single endpoint returning role-tailored stats, tasks & alerts | 🟠 High |
| Universal Dashboard UI | Responsive role-filtered widget dashboard (Investigator/Forensic/Legal/Supervisor/Admin) | 🟠 High |
| Notification UI | Notification dropdown, badge counts, notification center | 🟡 Medium |

**Deliverable**: End-to-end authorized Semantic Search, working RAG Case Assistant, and responsive Universal Role-Aware Dashboard.

---

### Phase 7: Legal Export & Security Monitoring (Week 9)

| Task | Description | Priority |
|------|-------------|----------|
| Legal export service | Generate court-ready document package with manifest | 🟠 High |
| Export package storage | Zip bundle in S3, recorded in export_packages table with SHA-256 | 🟠 High |
| Export API | POST /exports/legal-package/{case_id}, GET status/download | 🟠 High |
| Export UI | Export generator wizard and download tracking | 🟡 Medium |
| Security monitoring | IP brute-force tracking (Redis), failed logins, tampering alerts | 🟠 High |
| Admin security UI | Security events viewer, alert resolution, user admin | 🟡 Medium |

**Deliverable**: Court-ready export packaging and administrative security monitoring.

---

### Phase 8: Hardening, Polish & Demo Setup (Week 10)

| Task | Description | Priority |
|------|-------------|----------|
| Security test suite | Auth bypass, IDOR, prompt injection, rate limit verification | 🔴 Critical |
| UI polish | Loading skeletons, empty states, toast alerts, error boundaries | 🟠 High |
| Demo data scripts | Seed realistic Indian FIRs, charge sheets, forensic reports | 🟠 High |
| Tamper simulation script | Script to simulate S3 tampering to trigger live integrity alert | 🟠 High |
| End-to-end demo dry run | Full 26-step scripted judge walkthrough rehearsal | 🔴 Critical |

**Deliverable**: Production-hardened demo build ready for SIH 2026 judging.

---

## 2. MVP Feature Matrix

| Feature | Status | Phase |
|---------|--------|-------|
| ✅ Authentication (JWT + Argon2id) | MVP | 1 |
| ✅ RBAC (5 roles: Investigator, Forensic, Legal, Supervisor, Admin) | MVP | 1 |
| ✅ Case Management (with status state machine) | MVP | 2 |
| ✅ Case Membership & Access Control | MVP | 2 |
| ✅ Document Upload & S3 Object Storage | MVP | 3 |
| ✅ Document Version Control & Metadata | MVP | 3 |
| ✅ SHA-256 Integrity Verification & Mismatch Alert | MVP | 3 |
| ✅ Evidence Management & Custody State Machine | MVP | 4 |
| ✅ Chain of Custody (Hash-chained ledger) | MVP | 4 |
| ✅ Tamper-Evident Audit Trail (Advisory lock hash chaining) | MVP | 2-4 |
| ✅ OCR Pipeline (Tesseract) | MVP | 5 |
| ✅ AI Document Classification (Gemini Flash) | MVP | 5 |
| ✅ AI Entity Extraction (Gemini Flash) | MVP | 5 |
| ✅ Traditional & Full-Text Search | MVP | 6 |
| ✅ Semantic Search (pgvector text-embedding-004) | MVP (Promoted) | 6 |
| ✅ RAG Case Assistant (Authorized scope retrieval) | MVP (Promoted) | 6 |
| ✅ Universal Role-Filtered Dashboard | MVP (Simplified) | 6 |
| ✅ In-App Notifications | MVP | 4,6 |

---

## 3. Should-Have Features

| Feature | Phase |
|---------|-------|
| AI Document Summarization | Phase 5 (Optional) |
| Legal Court Export Package (Zip with SHA-256 Manifest) | Phase 7 |
| Security Monitoring & IP Brute Force Alerts | Phase 7 |
| Admin User Management UI | Phase 7 |

---

## 4. Future / Advanced Features

| Feature | Not in MVP |
|---------|-----------|
| Digital Signatures | Post-MVP |
| Hyperledger Fabric | Post-MVP |
| HSM/KMS Integration | Post-MVP |
| Government Identity (Aadhaar/SSO) | Post-MVP |
| Court System Integration | Post-MVP |
| Multi-Agency Federation | Post-MVP |
| Mobile Application | Post-MVP |
| Advanced SIEM Integration | Post-MVP |
| Anomaly Detection | Post-MVP |
| Audio/Video Evidence Processing | Post-MVP |

---

## 5. Recommended Implementation Order (Exact)

```
 1. Git init + .gitignore + README
 2. Docker Compose (postgres, minio, redis)
 3. Backend scaffold (FastAPI, core/, config)
 4. Database setup (SQLAlchemy, Alembic, initial migration)
 5. User + Role + Permission models
 6. Seed data (roles, permissions)
 7. Auth service (login, JWT, password hashing)
 8. Auth endpoints (login, refresh, logout, me)
 9. Auth middleware (JWT validation, current_user)
10. RBAC dependencies (require_role, require_permission)
11. Frontend scaffold (Next.js, Tailwind, shadcn/ui)
12. Login page
13. Auth context + protected routes
14. Dashboard layout (sidebar, header)
15. User management API (admin)
16. Case model + migration
17. Case service + repository
18. Case membership + access control
19. Case API endpoints
20. Audit event model + hash-chaining service
21. Audit logging for cases
22. Case list + detail pages (frontend)
23. S3 client (MinIO abstraction)
24. File validator
25. Document model + version model + migrations
26. Document upload service (validate → hash → store → record)
27. Version control service
28. Integrity service (SHA-256 verify)
29. Document API endpoints
30. Document upload + list + detail pages (frontend)
31. Evidence model + migration
32. Evidence service
33. Custody event model + hash-chaining
34. Custody transfer/receive service
35. Evidence + custody API endpoints
36. Evidence UI (registration, transfer, custody timeline)
37. Notification model + service
38. Celery worker setup
39. OCR pipeline (Tesseract)
40. Text extraction pipeline
41. Gemini classification service
42. Gemini entity extraction service
43. AI pipeline orchestration (Celery task)
44. AI results storage + API
45. AI results display in document detail
46. Traditional search service + API
47. Search page (frontend)
48. Dashboard API (role-specific stats)
49. Dashboard pages (frontend)
50. Notification UI
51. Embedding generation (text-embedding-004)
52. Semantic search service + API
53. RAG service + API
54. AI assistant page (frontend)
55. Legal export service + API
56. Export UI
57. Security monitoring service
58. Admin pages (frontend)
59. Polish + responsive + accessibility
60. Demo data script
61. End-to-end demo flow test
```

---

## 6. SIH Demo Strategy

### Demo Narrative (10-15 minutes)

```
ACT 1: Setup & Authentication (2 min)
1. Show system overview / architecture slide
2. Investigator logs in → role-specific dashboard

ACT 2: Case & Document Management (3 min)
3. Create a new case (cybercrime investigation)
4. Upload an FIR document (PDF)
5. System validates file → SHA-256 hash → stored in MinIO
6. AI pipeline processes: OCR → Classification (FIR) → Entity extraction
7. Show extracted entities: case number, FIR number, persons, law sections
8. Show AI-generated classification with confidence badge

ACT 3: Evidence & Chain of Custody (3 min)
9. Register digital evidence (seized laptop data)
10. Show evidence integrity metadata (SHA-256 hash)
11. Transfer evidence to forensic expert
12. Show hash-chained custody event
13. Forensic expert logs in → sees only assigned evidence
14. Forensic expert verifies integrity → ✅ Verified
15. Forensic expert uploads forensic report

ACT 4: AI Intelligence & Search (2 min)
16. Semantic search: "mobile device forensic analysis"
17. Show relevant results ranked by similarity
18. Ask AI assistant: "What evidence was collected?"
19. Show RAG response with source citations + AI-generated label

ACT 5: Security & Integrity (2 min)
20. Show audit trail timeline for the case
21. [DEMO] Simulate file tampering (modify file in MinIO)
22. Run integrity verification → 🚨 HASH MISMATCH
23. Security alert generated → supervisor notified

ACT 6: Legal Export (1 min)
24. Legal officer generates court-ready package
25. Package includes: case summary, FIR, evidence index, forensic report,
    custody chain, SHA-256 hashes, audit summary
26. Show package contents

CLOSING (1 min)
27. Recap: zero-trust, AI-assisted, cryptographically verifiable,
    traceable from creation to legal submission
28. Show architecture diagram
29. Mention future: Hyperledger Fabric, government ID integration,
    national scale
```

---

## 7. Testing Strategy

| Level | Scope | When | Tools |
|-------|-------|------|-------|
| **Unit Tests** | Individual functions | Every commit | pytest |
| **Integration Tests** | Module interactions, DB | Every PR | pytest + testcontainers |
| **Security Tests** | Auth bypass, IDOR, injection | Every PR | pytest |
| **API Tests** | Endpoint contracts | Every PR | pytest + httpx |
| **E2E Tests** | Full demo flow | Before demo | Playwright or manual |

### Critical Test Scenarios

1. Unauthenticated access → 401
2. Cross-case document access → 403
3. Non-custodian evidence transfer → 403
4. Malicious file upload → 400
5. Hash mismatch detection → integrity alert
6. Custody chain verification → chain intact
7. Audit chain verification → chain intact
8. Rate limit enforcement → 429
9. Account lockout → 403 after 5 failures
10. Expired JWT → 401

---

## 8. Deployment Strategy

### Development

```yaml
# docker-compose.yml
services:
  postgres:     # PostgreSQL 16 + pgvector
  minio:        # S3-compatible storage
  redis:        # Celery broker + cache
  backend:      # FastAPI (hot reload)
  frontend:     # Next.js (hot reload)
  celery:       # Background worker
```

### Production Considerations

| Component | Production Option |
|-----------|------------------|
| Database | Managed PostgreSQL (RDS/Cloud SQL) |
| Storage | AWS S3 / GCS |
| Redis | Managed Redis (ElastiCache) |
| Backend | Docker on ECS/GKE/VM |
| Frontend | Vercel / Docker on CDN |
| TLS | Load balancer termination |
| Secrets | AWS Secrets Manager / Vault |
| Monitoring | Prometheus + Grafana |
| Logging | ELK / CloudWatch |

---

## 9. Risks & Mitigation

| # | Risk | Impact | Probability | Mitigation |
|---|------|--------|-------------|------------|
| 1 | Gemini API rate limits / costs | AI features unavailable | Medium | Cache results, use Flash model, batch requests, have fallback |
| 2 | OCR quality on poor scans | Inaccurate text extraction | High | Allow manual text entry, quality indicators, preprocessing |
| 3 | pgvector performance at scale | Slow semantic search | Low | HNSW index, limit vector count, pagination |
| 4 | MinIO vs S3 differences | Storage bugs in prod | Low | Use S3-compatible API only, test with both |
| 5 | Demo data realism | Judges not impressed | Medium | Create realistic Indian legal documents for demo |
| 6 | Scope creep | Miss SIH deadline | High | Strict MVP scope, defer should-have features |
| 7 | Team skill gaps | Delayed implementation | Medium | Architecture docs, code templates, pair programming |
| 8 | Security vulnerabilities | Demo compromise | Low | Security tests, code review, OWASP checklist |
| 9 | Celery worker failures | Documents stuck in "processing" | Medium | Retry logic, timeout, manual reprocessing |
| 10 | Browser compatibility | UI breaks for judges | Low | Test on Chrome/Firefox, responsive design |

---

## 10. Files to Create

| File | Purpose | Phase |
|------|---------|-------|
| `README.md` | Project overview, setup instructions | 0 |
| `.gitignore` | Git ignore rules | 0 |
| `.env.example` | Environment variable template | 0 |
| `docker-compose.yml` | Development environment | 0 |
| `backend/Dockerfile` | Backend container | 0 |
| `backend/requirements.txt` | Python dependencies | 0 |
| `backend/app/main.py` | FastAPI application | 0 |
| `backend/app/core/*` | Core framework modules | 0 |
| `backend/app/modules/*` | All feature modules | 1-8 |
| `backend/alembic/*` | Database migrations | 0-4 |
| `backend/tests/*` | Test suite | 1-8 |
| `frontend/package.json` | Frontend dependencies | 0 |
| `frontend/Dockerfile` | Frontend container | 0 |
| `frontend/src/app/*` | All pages | 1-8 |
| `frontend/src/components/*` | UI components | 1-8 |
| `frontend/src/lib/*` | Utilities | 1 |
| `frontend/src/services/*` | API services | 1-8 |
| `frontend/src/types/*` | TypeScript types | 1 |
| `scripts/seed_data.py` | Initial data seeding | 1 |
| `scripts/demo_setup.py` | Demo data population | 8 |
| `docs/ARCHITECTURE.md` | ✅ Created | 0 |
| `docs/SECURITY_MODEL.md` | ✅ Created | 0 |
| `docs/DATABASE_DESIGN.md` | ✅ Created | 0 |
| `docs/API_SPEC.md` | ✅ Created | 0 |
| `docs/AI_PIPELINE.md` | ✅ Created | 0 |
| `docs/DEVELOPMENT_RULES.md` | ✅ Created | 0 |
| `docs/IMPLEMENTATION_ROADMAP.md` | ✅ This file | 0 |

