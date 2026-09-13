# Secure Digital Evidence & Legal Case Lifecycle Management Platform

> **Smart India Hackathon 2026 &bull; Problem Statement SIH26190**  
> **Organization**: Ministry of Home Affairs / National Crime Records Bureau (NCRB) / Women Safety Division  
> **Theme**: Blockchain & Cybersecurity  

---

## 1. Project Overview

A zero-trust, AI-assisted digital evidence lifecycle platform where every sensitive legal and investigation document is searchable, access-controlled, cryptographically verifiable, version-controlled, and traceable from creation to court submission.

### Core Architectural Principles
- **Zero-Trust Security**: Continuous authentication and case-membership verification on every resource access.
- **Cryptographic File Integrity**: Permanent SHA-256 baseline hashing on ingest with live tamper detection.
- **Tamper-Evident Ledger**: Hash-chained, append-only audit trail and chain of custody.
- **AI Document Intelligence**: Automated OCR, legal classification, entity extraction, and authorized RAG case assistant.

---

## 2. Monorepo Structure

```
SIH-190/
├── backend/                  # Python FastAPI application
│   ├── app/
│   │   ├── api/v1/           # API routes & endpoints
│   │   ├── core/             # Config, security, database, logging, middleware
│   │   ├── models/           # SQLAlchemy ORM models & mixins
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── storage/          # S3/MinIO abstraction service
│   │   └── workers/          # Celery background queue & tasks
│   ├── alembic/              # Database migrations & pgvector setup
│   ├── tests/                # Pytest unit & security test suite
│   ├── pyproject.toml        # Ruff, mypy, & pytest configurations
│   └── requirements.txt      # Production backend dependencies
├── frontend/                 # Next.js 14 App Router application
│   ├── src/
│   │   ├── app/              # App Router routes ((auth), (dashboard))
│   │   ├── components/       # Reusable UI & layout components
│   │   ├── lib/              # API client & utilities
│   │   └── types/            # TypeScript definitions
│   ├── package.json          # Node dependencies
│   └── tailwind.config.ts    # Tailwind styling system
├── infrastructure/           # Docker Compose for local development
│   ├── docker-compose.yml    # PostgreSQL (pgvector), Redis, MinIO
│   └── init-pgvector.sql     # Database extensions bootstrap
├── scripts/                  # Automation & verification scripts
│   ├── start_infra.sh        # Start docker infrastructure
│   └── stop_infra.sh         # Stop docker infrastructure
└── docs/                     # Architectural source of truth (Locked)
    ├── ARCHITECTURE.md
    ├── SECURITY_MODEL.md
    ├── DATABASE_DESIGN.md
    ├── API_SPEC.md
    ├── AI_PIPELINE.md
    ├── DEVELOPMENT_RULES.md
    └── IMPLEMENTATION_ROADMAP.md
```

---

## 3. Prerequisites

- **Node.js**: >= 20.0 (v24.x tested)
- **Python**: >= 3.12 (v3.14.x tested)
- **Docker & Docker Compose**: >= 24.0

---

## 4. Environment Setup

Copy the environment templates before starting:

```bash
# Root template
cp .env.example .env

# Backend configuration
cp backend/.env.example backend/.env

# Frontend configuration
cp frontend/.env.example frontend/.env.local
```

> **Security Note**: Never commit `.env` files or secret keys into version control.

---

## 5. Local Infrastructure Startup

Start the required local backing services (PostgreSQL 16 with pgvector, Redis 7, and MinIO S3):

```bash
./scripts/start_infra.sh
```

Service endpoints:
- **PostgreSQL**: `localhost:5432` (database: `sih190`)
- **Redis**: `localhost:6379`
- **MinIO S3 API**: `http://localhost:9000`
- **MinIO Web Console**: `http://localhost:9001` (user: `minio_admin`)

To stop infrastructure:
```bash
./scripts/stop_infra.sh
```

---

## 6. Backend Startup

1. **Set up virtual environment & install dependencies**:
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```

2. **Run database migrations**:
   ```bash
   alembic upgrade head
   ```

3. **Start the FastAPI development server**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Start the Celery worker** (optional for test tasks):
   ```bash
   celery -A app.workers.celery_app.celery_app worker --loglevel=info
   ```

Interactive API documentation will be accessible at `http://localhost:8000/docs`.

---

## 7. Frontend Startup

1. **Install dependencies**:
   ```bash
   cd frontend
   npm install
   ```

2. **Start the Next.js development server**:
   ```bash
   npm run dev
   ```

Access the application in your browser at `http://localhost:3000`.

---

## 8. Running Tests & Quality Checks

### Backend Quality Suite
```bash
cd backend
source .venv/bin/activate

# Run test suite
pytest -v

# Run linting
ruff check .
```

### Frontend Quality Suite
```bash
cd frontend

# Run linting
npm run lint

# Run production build
npm run build
```

---

## 9. Health & Diagnostic Probes

- **Liveness Probe**: `GET http://localhost:8000/health`
- **Readiness Probe**: `GET http://localhost:8000/health/ready` (checks DB, Redis, MinIO, and Celery)
