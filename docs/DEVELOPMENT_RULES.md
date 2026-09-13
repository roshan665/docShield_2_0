# Development Rules — Secure Digital Evidence & Legal Case Lifecycle Management Platform

---

## 1. General Rules

1. **No architecture changes without approval.** The architecture defined in `ARCHITECTURE.md` is the source of truth.
2. **No stack changes without approval.** The technology stack is locked.
3. **Inspect before modifying.** Always read existing code before changing a subsystem.
4. **Do not make unrelated changes.** Keep PRs focused and reviewable.
5. **Do not rewrite working code without reason.** Refactor only when necessary.
6. **Do not introduce unnecessary dependencies.** Justify every new package.

---

## 2. Security Rules (Non-Negotiable)

1. **Never remove security controls to make something work.**
2. **Never bypass authorization.** Backend enforces all access control.
3. **Never trust frontend permissions.** Frontend hides UI elements; backend enforces.
4. **Never let AI make authorization decisions.** Auth happens before retrieval.
5. **Never store sensitive documents in the database.** Use S3/MinIO.
6. **Never store actual documents on blockchain.** Only cryptographic proofs.
7. **Never overwrite evidence.** Create new versions.
8. **Never delete audit events** from the application layer.
9. **Never expose secrets.** No hardcoded API keys, passwords, or tokens.
10. **Never commit `.env` files.** Use `.env.example` with placeholder values.
11. **Never use fake security and call it production-grade.** Clearly label demo/mock implementations.
12. **Never expose sensitive information in error messages or logs.**
13. **Never sacrifice security for convenience.**

---

## 3. Code Organization

### Backend

- Every module follows: **Router → Service → Repository → Model**
- **Router**: HTTP handling only — parse request, call service, format response
- **Service**: Business logic, authorization checks, orchestration
- **Repository**: Data access only — SQL queries via SQLAlchemy
- **Model**: SQLAlchemy ORM definitions
- **Schema**: Pydantic models for request/response validation

### Frontend

- Organize by feature, not by file type
- Use shadcn/ui components; don't build custom low-level UI primitives
- Keep API calls in `services/` directory
- Keep type definitions in `types/` directory
- Use custom hooks for data fetching and state

---

## 4. Coding Standards

### Python (Backend)

```
- Python 3.12+
- Type hints on all functions
- Docstrings on all public functions and classes
- Pydantic v2 models for all API input/output
- SQLAlchemy 2.0 style (mapped_column, etc.)
- async/await for database and HTTP operations
- f-strings for string formatting
- pathlib for file paths
- Black formatter (line length 88)
- isort for import sorting
- ruff for linting
```

### TypeScript (Frontend)

```
- Strict TypeScript (no 'any' types except justified cases)
- Functional components only (no class components)
- React hooks for state and side effects
- Proper error boundaries
- ESLint + Prettier
- Named exports preferred
```

---

## 5. Git Workflow

### Branch Naming

```
main            — production-ready code
develop         — integration branch
feature/<name>  — new features
bugfix/<name>   — bug fixes
security/<name> — security improvements
docs/<name>     — documentation updates
```

### Commit Messages

```
feat: add document upload endpoint
fix: correct RBAC check for evidence transfer
security: add rate limiting to auth endpoints
docs: update API specification
test: add integration tests for custody chain
refactor: extract file validation into service
chore: update dependencies
```

### Pull Request Rules

1. Every PR must be reviewed before merge
2. All tests must pass
3. No security warnings ignored
4. Update relevant documentation

---

## 6. Environment & Configuration

### Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/sih190
DATABASE_URL_SYNC=postgresql://user:password@localhost:5432/sih190

# Redis
REDIS_URL=redis://localhost:6379/0

# Object Storage
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET_NAME=sih190-documents
S3_EVIDENCE_BUCKET=sih190-evidence

# JWT
JWT_SECRET_KEY=<random-256-bit-key>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Gemini AI
GEMINI_API_KEY=<api-key>

# Application
APP_ENV=development
APP_DEBUG=true
CORS_ORIGINS=http://localhost:3000
LOG_LEVEL=INFO
```

### Rules

- All configuration via environment variables
- `Pydantic BaseSettings` for config management
- `.env` file for local development (never committed)
- `.env.example` committed with placeholder values
- Secrets rotated regularly in production
- Different configs for dev/test/production

---

## 7. Testing Strategy

### Test Categories

| Category | Purpose | Location | Tools |
|----------|---------|----------|-------|
| **Unit Tests** | Individual functions/methods | `tests/unit/` | pytest, unittest.mock |
| **Integration Tests** | Module interactions, DB queries | `tests/integration/` | pytest, testcontainers |
| **Security Tests** | Auth bypass, IDOR, injection | `tests/security/` | pytest |
| **API Tests** | Endpoint behavior | `tests/integration/` | pytest, httpx (TestClient) |

### Minimum Test Coverage

| Module | Required Coverage |
|--------|------------------|
| Authentication | 90%+ |
| Authorization/RBAC | 90%+ |
| Document Upload & Validation | 85%+ |
| Evidence Management | 85%+ |
| Chain of Custody | 90%+ |
| Integrity Verification | 90%+ |
| Audit Trail | 85%+ |
| Other modules | 70%+ |

### Security Test Examples

```python
# Every endpoint must reject unauthenticated requests
def test_endpoint_requires_auth(client):
    response = client.get("/api/v1/cases")
    assert response.status_code == 401

# Users cannot access other users' cases
def test_idor_case_access(client, other_user_case):
    response = client.get(f"/api/v1/cases/{other_user_case.id}")
    assert response.status_code == 403

# Users cannot download documents from unauthorized cases
def test_unauthorized_document_download(client, other_case_doc):
    response = client.get(f"/api/v1/documents/{other_case_doc.id}/download")
    assert response.status_code == 403

# Malicious file uploads rejected
def test_reject_executable_upload(client, case_id):
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("malware.exe", b"MZ...", "application/x-executable")},
        data={"case_id": case_id}
    )
    assert response.status_code == 400
```

---

## 8. Documentation Rules

1. All API endpoints documented in `API_SPEC.md`
2. All database schema changes documented in `DATABASE_DESIGN.md`
3. FastAPI auto-generates OpenAPI docs at `/docs`
4. All public functions have docstrings
5. Architecture changes require `ARCHITECTURE.md` update
6. Security changes require `SECURITY_MODEL.md` update

---

## 9. Dependency Management

### Backend

```
- requirements.txt for production dependencies
- requirements-dev.txt for development/testing
- Pin major versions, allow minor updates
- Security audit dependencies regularly
- No unnecessary dependencies
```

### Frontend

```
- package.json with exact versions (lockfile)
- npm audit regularly
- No unnecessary dependencies
- Prefer well-maintained, popular packages
```

---

## 10. Docker Rules

```
- Multi-stage builds for smaller images
- Non-root user in containers
- Health checks defined
- No secrets in Dockerfiles or images
- Use .dockerignore
- Pin base image versions
```

---

## 11. Logging Rules

```
- Structured JSON logging
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Never log passwords, tokens, or API keys
- Never log full document content
- Log user actions with actor ID (not PII)
- Log security events separately
- Include request ID for tracing
```

---

## 12. Error Handling Rules

```
- Use custom exception hierarchy
- Return consistent error responses: {detail, error_code, timestamp}
- Never expose stack traces to clients
- Log detailed errors server-side
- Frontend shows user-friendly messages
- 4xx for client errors, 5xx for server errors
- Fail closed (deny on error)
```

---

## 13. Demo vs Production

| Aspect | Demo/Development | Production |
|--------|-----------------|------------|
| Auth | Real JWT (can use simple secret) | RS256 with key rotation |
| Passwords | Argon2id (can use simpler params) | Argon2id with full params |
| Storage | MinIO local | Managed S3 |
| Database | Docker PostgreSQL | Managed PostgreSQL |
| TLS | Not required | Required |
| Rate Limiting | Relaxed | Strict |
| Malware Scan | Optional/mock | ClamAV required |
| Blockchain | Hash-chained ledger | Hyperledger Fabric |

**All demo shortcuts must be clearly labeled in code with `# DEMO:` or `# TODO: Production` comments.**

