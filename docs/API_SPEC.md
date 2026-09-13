# API Specification — Secure Digital Evidence & Legal Case Lifecycle Management Platform

---

## 1. API Conventions

| Convention | Details |
|-----------|---------|
| **Base URL** | `/api/v1/` |
| **Format** | JSON request/response |
| **Authentication** | Bearer token in `Authorization` header |
| **Timestamps** | ISO 8601 UTC (`2026-01-15T10:30:00Z`) |
| **Resource IDs** | UUID v4 |
| **Pagination** | `?page=1&size=20` → `{ items, total, page, size, pages }` |
| **Sorting** | `?sort_by=created_at&sort_order=desc` |
| **File Uploads** | `multipart/form-data` |

### Standard Success Response

```json
{
  "id": "uuid",
  "...": "resource fields"
}
```

### Standard List Response

```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "size": 20,
  "pages": 5
}
```

### Standard Error Response

```json
{
  "detail": "Human-readable error message",
  "error_code": "AUTH_001",
  "timestamp": "2026-01-15T10:30:00Z"
}
```

---

## 2. Authentication — `/api/v1/auth`

| Method | Path | Description | Auth | Roles |
|--------|------|-------------|:----:|-------|
| POST | `/auth/login` | Login with email + password | ❌ | Any |
| POST | `/auth/refresh` | Refresh access token (cookie) | 🍪 | Any |
| POST | `/auth/logout` | Invalidate tokens | ✅ | Any |
| GET | `/auth/me` | Get current user profile | ✅ | Any |
| POST | `/auth/change-password` | Change own password (requires old password) | ✅ | Any |

> **Password Reset Policy**: In accordance with government zero-trust guidelines, forgotten passwords are reset by System Administrators via `POST /api/v1/admin/users/{id}/reset-password` (generates temporary one-time password). Self-service email reset is not permitted.

### Public Health Check — `GET /api/v1/health`
- **Auth**: None (Public)
- **Description**: Fast liveness probe for Docker/Kubernetes/load-balancers. Returns `{"status": "ok"}`.

### Login — `POST /api/v1/auth/login`

**Request:**
```json
{
  "email": "officer@ncrb.gov.in",
  "password": "secure_password"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "officer@ncrb.gov.in",
    "full_name": "Inspector Sharma",
    "role": "investigator",
    "permissions": ["case:create", "case:read", "document:upload", "..."]
  }
}
```
+ `Set-Cookie: refresh_token=...; HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`

**Errors:** 401 (AUTH_001 invalid credentials), 403 (AUTH_003 account locked)

---

## 3. Users & Roles — `/api/v1/users` & `/api/v1/roles`

| Method | Path | Description | Auth | Roles |
|--------|------|-------------|:----:|-------|
| GET | `/users` | List all users (paginated, filterable) | ✅ | Admin |
| POST | `/users` | Create new user | ✅ | Admin |
| GET | `/users/{id}` | Get user details | ✅ | Admin, Self |
| PUT | `/users/{id}` | Update user profile | ✅ | Admin |
| PATCH | `/users/{id}/status` | Activate/deactivate/unlock user | ✅ | Admin |
| POST | `/admin/users/{id}/reset-password` | Reset user password (admin generated) | ✅ | Admin |
| GET | `/roles` | List all system roles | ✅ | Admin |
| GET | `/permissions` | List all system permissions | ✅ | Admin |

---

## 4. Cases — `/api/v1/cases`

| Method | Path | Description | Auth | Roles |
|--------|------|-------------|:----:|-------|
| GET | `/cases` | List cases (strictly filtered by user's case membership) | ✅ | Inv, FE, LO, Sup |
| POST | `/cases` | Create new case | ✅ | Inv, Sup |
| GET | `/cases/{id}` | Get case details | ✅ | Case members |
| PUT | `/cases/{id}` | Update case info | ✅ | Lead Inv, Sup |
| PATCH | `/cases/{id}/status` | Update case status (validates state machine) | ✅ | Lead Inv, Sup |
| GET | `/cases/{id}/members` | List case team members | ✅ | Case members |
| POST | `/cases/{id}/members` | Add member to case | ✅ | Lead Inv, Sup |
| DELETE | `/cases/{id}/members/{user_id}` | Remove member from case | ✅ | Lead Inv, Sup |
| GET | `/cases/{id}/timeline` | Get case activity timeline | ✅ | Case members |
| GET | `/cases/{id}/documents` | List case documents | ✅ | Case members |
| GET | `/cases/{id}/evidence` | List case evidence | ✅ | Case members |

> **Case Scoping Rule**: All queries to `GET /cases` internally join `case_members WHERE user_id = :current_user_id AND is_active = true`. Supervisors are not granted global access; they must be explicitly added to cases they supervise.

### Create Case — `POST /api/v1/cases`

**Request:**
```json
{
  "case_number": "CR-2026-001234",
  "fir_number": "FIR-2026-5678",
  "title": "Cybercrime Investigation - Online Fraud",
  "description": "Investigation into online financial fraud targeting women...",
  "priority": "high",
  "category": "cybercrime",
  "police_station": "Cyber Crime PS, Delhi",
  "district": "New Delhi",
  "state": "Delhi"
}
```

**Response (201):** Full case object with `id`, `created_at`, `investigating_officer_id` (set to creator)

---

## 5. Documents — `/api/v1/documents`

| Method | Path | Description | Auth | Roles |
|--------|------|-------------|:----:|-------|
| POST | `/documents/upload` | Upload document (multipart) | ✅ | Case members |
| GET | `/documents/{id}` | Get document metadata | ✅ | Case members |
| GET | `/documents/{id}/download` | Download current version file | ✅ | Case members |
| GET | `/documents/{id}/versions` | List all versions | ✅ | Case members |
| GET | `/documents/{id}/versions/{vid}` | Get specific version metadata | ✅ | Case members |
| GET | `/documents/{id}/versions/{vid}/download` | Download specific version | ✅ | Case members |
| POST | `/documents/{id}/versions` | Upload new version | ✅ | Case members |
| GET | `/documents/{id}/metadata` | Get extracted metadata | ✅ | Case members |
| PUT | `/documents/{id}/metadata` | Update/verify metadata fields | ✅ | Case members |
| GET | `/documents/{id}/verify` | Verify document integrity | ✅ | Case members |
| GET | `/documents/{id}/entities` | Get extracted entities | ✅ | Case members |

> **Secure Download Policy**: All file downloads enforce `Content-Disposition: attachment; filename="<sanitized>"`, `X-Content-Type-Options: nosniff`, and record a tamper-evident `DOCUMENT_DOWNLOADED` audit log with actor ID, timestamp, and client IP.

### Upload Document — `POST /api/v1/documents/upload`

**Request** (`multipart/form-data`):
```
file: <binary file>
case_id: "550e8400-e29b-41d4-a716-446655440000"
title: "FIR - CR-2026-001234"
document_type: "fir"
classification: "confidential"
description: "First Information Report for case CR-2026-001234"
```

**Response (201):**
```json
{
  "id": "doc-uuid",
  "case_id": "case-uuid",
  "title": "FIR - CR-2026-001234",
  "document_type": "fir",
  "status": "processing",
  "current_version": {
    "id": "version-uuid",
    "version_number": 1,
    "file_hash_sha256": "a1b2c3d4...",
    "file_size_bytes": 245760,
    "is_original": true,
    "integrity_status": "verified"
  },
  "ai_processed": false,
  "created_at": "2026-01-15T10:30:00Z"
}
```

### Verify Integrity — `GET /api/v1/documents/{id}/verify`

**Response (200):**
```json
{
  "document_id": "doc-uuid",
  "version_id": "version-uuid",
  "stored_hash": "a1b2c3d4e5f6...",
  "computed_hash": "a1b2c3d4e5f6...",
  "match": true,
  "integrity_status": "verified",
  "verified_at": "2026-01-15T12:00:00Z"
}
```

---

## 6. Evidence — `/api/v1/evidence`

| Method | Path | Description | Auth | Roles |
|--------|------|-------------|:----:|-------|
| GET | `/evidence` | List accessible evidence (supports `?custodian=me`, `?case_id=uuid`) | ✅ | Case members |
| POST | `/evidence` | Register new evidence | ✅ | Inv, Sup |
| GET | `/evidence/{id}` | Get evidence details | ✅ | Case members |
| PUT | `/evidence/{id}` | Update evidence metadata | ✅ | Custodian, Sup |
| GET | `/evidence/{id}/verify` | Verify evidence integrity | ✅ | Case members |
| POST | `/evidence/{id}/transfer` | Initiate custody transfer | ✅ | Current custodian |
| POST | `/evidence/{id}/receive` | Acknowledge custody receipt | ✅ | Transfer target |
| GET | `/evidence/{id}/custody-chain` | Get full chain of custody | ✅ | Case members |
| GET | `/evidence/{id}/download` | Download evidence file | ✅ | Case members |

> **Custody Transfer Rule**: When initiating transfer (`POST /evidence/{id}/transfer`), the API verifies that (1) `current_user` is the active custodian, and (2) `to_user_id` is an active member of the parent case. Records an `EVIDENCE_DOWNLOADED` audit log on file download.

### Transfer Evidence — `POST /api/v1/evidence/{id}/transfer`

**Request:**
```json
{
  "to_user_id": "target-user-uuid",
  "reason": "Transfer to forensic lab for digital analysis",
  "location": "Cyber Forensic Lab, CFSL Delhi"
}
```

**Response (200):**
```json
{
  "custody_event": {
    "id": "event-uuid",
    "evidence_id": "evidence-uuid",
    "event_type": "transferred",
    "from_user_id": "current-user-uuid",
    "to_user_id": "target-user-uuid",
    "reason": "Transfer to forensic lab for digital analysis",
    "file_hash_at_event": "a1b2c3d4...",
    "event_hash": "computed-hash...",
    "timestamp": "2026-01-15T14:00:00Z"
  },
  "evidence_status": "in_analysis"
}
```

---

## 7. Chain of Custody — `/api/v1/custody`

| Method | Path | Description | Auth | Roles |
|--------|------|-------------|:----:|-------|
| GET | `/custody/events` | List custody events (filtered by evidence/date) | ✅ | Case members |
| GET | `/custody/events/{id}` | Get specific custody event | ✅ | Case members |
| POST | `/custody/events/{id}/verify` | Verify custody chain integrity up to event | ✅ | Case members |

*(Note: Direct evidence-to-chain view is canonical at `GET /api/v1/evidence/{id}/custody-chain`)*

---

## 8. Audit — `/api/v1/audit`

| Method | Path | Description | Auth | Roles |
|--------|------|-------------|:----:|-------|
| GET | `/audit/events` | List audit events (paginated, filtered) | ✅ | Sup, Admin |
| GET | `/audit/events/{id}` | Get specific audit event | ✅ | Sup, Admin |
| GET | `/audit/resource/{type}/{id}` | Audit history for a resource | ✅ | Case members, Admin |
| GET | `/audit/user/{id}` | Audit history for a user | ✅ | Admin |
| GET | `/audit/case/{id}` | Audit history for a case | ✅ | Case members, Sup |
| POST | `/audit/verify-chain` | Verify audit chain integrity | ✅ | Admin |

---

## 9. Search — `/api/v1/search`

| Method | Path | Description | Auth | Roles |
|--------|------|-------------|:----:|-------|
| POST | `/search/documents` | Traditional filtered search | ✅ | Case members |
| POST | `/search/semantic` | Semantic similarity search | ✅ | Case members |
| POST | `/search/entities` | Search by extracted entities | ✅ | Case members |

### Semantic Search — `POST /api/v1/search/semantic`

**Request:**
```json
{
  "query": "forensic analysis of mobile device data extraction",
  "case_ids": ["case-uuid-1"],
  "limit": 10,
  "min_similarity": 0.7
}
```

**Response (200):**
```json
{
  "results": [
    {
      "document_id": "doc-uuid",
      "document_title": "Forensic Report - Mobile Device Analysis",
      "chunk_text": "The digital forensic analysis of the seized mobile device...",
      "similarity_score": 0.92,
      "case_id": "case-uuid-1",
      "document_type": "forensic_report"
    }
  ],
  "query": "forensic analysis of mobile device data extraction",
  "total_results": 3
}
```

---

## 10. AI — `/api/v1/ai`

| Method | Path | Description | Auth | Roles |
|--------|------|-------------|:----:|-------|
| POST | `/ai/classify` | Classify a document | ✅ | Case members |
| POST | `/ai/extract` | Extract entities from document | ✅ | Case members |
| POST | `/ai/summarize` | Generate document summary | ✅ | Case members |
| POST | `/ai/ask` | RAG case assistant query | ✅ | Case members |
| GET | `/ai/processing-status/{doc_id}` | Get AI pipeline status | ✅ | Case members |

### RAG Query — `POST /api/v1/ai/ask`

**Request:**
```json
{
  "question": "What evidence was collected from the suspect's residence?",
  "case_id": "case-uuid"
}
```

**Response (200):**
```json
{
  "answer": "Based on the investigation report dated 2026-01-10, the following items were collected from the suspect's residence: (1) a laptop computer, (2) three mobile phones, (3) financial documents...",
  "sources": [
    {
      "document_id": "doc-uuid-1",
      "document_title": "Investigation Report - Site Visit",
      "relevance_score": 0.95
    },
    {
      "document_id": "doc-uuid-2",
      "document_title": "Evidence Collection Record",
      "relevance_score": 0.88
    }
  ],
  "ai_generated": true,
  "disclaimer": "This response is AI-generated. Verify information with original documents."
}
```

---

## 11. Notifications — `/api/v1/notifications`

| Method | Path | Description | Auth | Roles |
|--------|------|-------------|:----:|-------|
| GET | `/notifications` | List user's notifications | ✅ | Any |
| PATCH | `/notifications/{id}/read` | Mark as read | ✅ | Owner |
| PATCH | `/notifications/read-all` | Mark all as read | ✅ | Any |
| GET | `/notifications/unread-count` | Get unread count | ✅ | Any |

---

## 12. Dashboard — `/api/v1/dashboard`

| Method | Path | Description | Auth | Roles |
|--------|------|-------------|:----:|-------|
| GET | `/dashboard/stats` | Role-specific statistics | ✅ | Any |
| GET | `/dashboard/recent-activity` | Recent activity feed | ✅ | Any |
| GET | `/dashboard/alerts` | Active alerts | ✅ | Sup, Admin |

---

## 13. Exports — `/api/v1/exports`

| Method | Path | Description | Auth | Roles |
|--------|------|-------------|:----:|-------|
| POST | `/exports/legal-package/{case_id}` | Generate legal export package | ✅ | LO, Sup |
| GET | `/exports/status/{export_id}` | Check export status | ✅ | Requester |
| GET | `/exports/download/{export_id}` | Download export package | ✅ | Requester |

---

## 14. Admin — `/api/v1/admin`

| Method | Path | Description | Auth | Roles |
|--------|------|-------------|:----:|-------|
| GET | `/admin/system/health` | System health check | ✅ | Admin |
| GET | `/admin/system/stats` | System statistics | ✅ | Admin |
| GET | `/admin/security/events` | Security events list | ✅ | Admin |
| GET | `/admin/security/alerts` | Active security alerts | ✅ | Admin, Sup |
| POST | `/admin/security/alerts/{id}/resolve` | Resolve security alert | ✅ | Admin |

### Health Check — `GET /api/v1/admin/system/health`

**Response (200):**
```json
{
  "status": "healthy",
  "services": {
    "database": "up",
    "object_storage": "up",
    "redis": "up",
    "celery": "up"
  },
  "timestamp": "2026-01-15T10:30:00Z"
}
```

---

## 15. Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `AUTH_001` | 401 | Invalid credentials |
| `AUTH_002` | 401 | Token expired |
| `AUTH_003` | 403 | Account locked |
| `AUTH_004` | 401 | Invalid or blacklisted token |
| `AUTHZ_001` | 403 | Insufficient permissions for action |
| `AUTHZ_002` | 403 | Not a member of this case |
| `AUTHZ_003` | 403 | Not the current custodian |
| `CASE_001` | 404 | Case not found |
| `CASE_002` | 409 | Case number already exists |
| `CASE_003` | 400 | Invalid case status transition |
| `DOC_001` | 404 | Document not found |
| `DOC_002` | 400 | Invalid or disallowed file type |
| `DOC_003` | 413 | File exceeds size limit |
| `DOC_004` | 409 | Integrity check failed — hash mismatch |
| `DOC_005` | 404 | Document version not found |
| `EVD_001` | 404 | Evidence not found |
| `EVD_002` | 400 | Invalid custody transfer (not current custodian) |
| `EVD_003` | 409 | Custody chain integrity broken |
| `EVD_004` | 409 | Evidence integrity compromised |
| `SEARCH_001` | 400 | Invalid search parameters |
| `AI_001` | 503 | AI service unavailable |
| `AI_002` | 400 | Document not yet processed by AI |
| `RATE_001` | 429 | Rate limit exceeded |
| `VAL_001` | 422 | Validation error (Pydantic) |
| `SYS_001` | 500 | Internal server error |
| `SYS_002` | 503 | Service unavailable |

---

## 16. Future WebSocket Endpoints

| Path | Description | Auth |
|------|-------------|------|
| `/ws/notifications` | Real-time notification stream | Token-based |
| `/ws/processing/{doc_id}` | Document processing progress | Token-based |

