# DocShield Portable Demo Dataset & Reproduction Guide

> **National Digital Evidence & Legal Intelligence Platform (NCRB • MHA India)**  
> **SIH 2026 Problem Statement SIH26190**

This document details how the DocShield demo environment is packaged, seeded, and reproduced across developer machines and cloud deployment platforms (such as Render) with **zero frontend mocks** and **100% real backend, database, and storage integration**.

---

## 1. Architectural Philosophy

DocShield avoids static UI templates and mock data. All cases, documents, evidence registries, and audit feeds displayed in the frontend originate from real database rows and physical files:

1. **Storage-Backed Documents**: Every document points to physical files (`.pdf`, `.docx`, `.jpg`, `.png`) stored in an S3/MinIO compatible bucket (`sih190-documents`), with immutable SHA-256 baseline hashes.
2. **Cryptographic Chain of Custody**: Evidence transfer events form an unbroken sequential cryptographic hash chain ($H_n = \text{SHA256}(\text{canonical\_payload} \parallel H_{n-1})$). The endpoint `GET /api/v1/evidence/{id}/custody/verify` cryptographically audits this chain on-demand.
3. **Tamper-Evident Audit Ledger**: System actions are logged into an append-only audit ledger verified via `GET /api/v1/admin/audit/verify`.
4. **Pre-Computed Vector Embeddings**: Document text chunks include pre-computed 768-dimensional `pgvector` embeddings, ensuring semantic vector search and hybrid search function out-of-the-box without requiring live Gemini API access during demonstrations.

---

## 2. Demo User Accounts & Credentials

The demo environment provisions accounts for all 5 official roles defined in the DocShield Security Model:

| Role | Email | Password | Primary Permissions |
|------|-------|----------|---------------------|
| **Investigating Officer** | `officer@ncrb.gov.in` | `Investigator@2026!` | Case creation, document upload, evidence registration, custody transfer |
| **System Administrator** | `admin@ncrb.gov.in` | `Admin@DocShield2026!` | User provisioning, role management, audit verification, security monitoring |
| **Supervisory Officer (SP)** | `supervisor@ncrb.gov.in` | `Supervisor@2026!` | Case review, closure, supervisory approval, high-level audit oversight |
| **Forensic Expert / Analyst** | `forensic@ncrb.gov.in` | `Forensic@2026!` | Evidence reception, forensic imaging, lab analysis, artifact verification |
| **Legal Officer / Prosecutor** | `legal@ncrb.gov.in` | `Legal@2026!` | Court filings, prosecution exhibit intake, legal export packaging |
| **Secondary Investigator** | `officer2@ncrb.gov.in` | `Investigator2@2026!` | Joint task force member for multi-officer custody handover demonstrations |
| **Court Liaison Clerk** | `court@docshield.gov.in` | `CourtClerk@2026!` | Sessions Court registry liaison |

All passwords are cryptographically hashed using **Argon2id** (`m=65536, t=3, p=4`).

---

## 3. Flagship Demo Cases Catalog

The seeded dataset includes 6 diverse investigation cases representing different lifecycle states, crime categories, and jurisdictional entities:

1. **`CR-2026-CYBER01`** — *Cyber Extortion & Dark Web Ransomware Syndicate*
   - **Status**: `under_investigation` | **Priority**: `critical`
   - **Category**: `cybercrime` | **Police Station**: Cyber Crime Special Cell, Lodhi Road
   - **Documents**: FIR 901 (`fir_report.pdf`), Data Center CCTV & Intrusion Log (`cctv_log.pdf`), Witness Deposition v1/v2 (`statement_v1.pdf`, `statement_v2.pdf`).
   - **Evidence**: Encrypted USB Drive (`EVID-2026-00009`), Primary Server SSD (`EVID-2026-00012`).
   - **Custody Events**: 4-hop custody sequence (Registration $\rightarrow$ Handover to CFSL $\rightarrow$ Recipient Ack $\rightarrow$ In-Analysis).

2. **`CR-2026-FIN002`** — *Offshore Hawala & Multi-Crore Banking Fraud*
   - **Status**: `pending_review` | **Priority**: `high`
   - **Category**: `financial_fraud` | **Police Station**: Economic Offences Wing (EOW), Mandir Marg
   - **Documents**: FIR 555 (`fir_555.docx`), Bank of Baroda Audit Ledger (`bank_ledger.docx`), Hawala Transfer Transcript (`hawala.docx`), SEBI Forensic Audit (`audit.docx`).
   - **Legal Sections**: IPC 420 (Cheating), IPC 406 (Criminal Breach of Trust), CrPC 154.
   - **Evidence**: Notebook of Accounts (`EVID-2026-00011`).

3. **`CR-2026-HOM003`** — *Rohini Industrial Area Armed Homicide & Ballistics*
   - **Status**: `open` | **Priority**: `critical`
   - **Category**: `violent_crime` | **Police Station**: Sector 3 PS, Rohini
   - **Documents**: FSL Ballistics Examination (`ballistics.docx`), Striation Report (`ballistic_report.docx`), Section 161 Witness Statement (`witness_statement.docx`), Scene Photograph (`crime_scene.jpg`).
   - **Evidence**: Blood Sample Vial (`EVID-2026-00047`), Country-Made 9mm Pistol (`EVID-2026-00021`).
   - **Custody Events**: Complete 5-hop lifecycle (Registered $\rightarrow$ In-Analysis $\rightarrow$ Analyzed $\rightarrow$ Submitted to Court $\rightarrow$ Archived).

4. **`CR-2026-NAR004`** — *Cross-Border Contraband & Synthetic Narcotics Syndicate*
   - **Status**: `pending_legal` | **Priority**: `high`
   - **Category**: `narcotics` | **Police Station**: Narcotics Control Cell, RK Puram
   - **Documents**: Tactical Radio Intercept Log (`intercept.pdf`), Intelligence Note (`confidential.pdf`).
   - **Evidence**: Encrypted Memory Card (`EVID-2026-00013`).

5. **`CR-2026-CORR005`** — *State Infrastructure Tender Bribery & Wiretap Operation*
   - **Status**: `pending_legal` | **Priority**: `high`
   - **Category**: `corruption` | **Police Station**: Anti-Corruption Bureau (ACB), Barakhamba Road
   - **Documents**: Sworn Section 164 Deposition (`deposition_test.docx`), Tender Markup Audit (`fesibility.png`).
   - **Evidence**: Wiretap Audio & Transcript Evidence (`EVID-2026-00014`).

6. **`CR-2025-ARCH006`** — *Customs Duty Evasion & Luxury Goods Smuggling (Concluded)*
   - **Status**: `archived` | **Priority**: `medium`
   - **Category**: `economic_offences` | **Police Station**: IGI Airport Police Station
   - **Documents**: Sessions Court Judgment Order (`verified.pdf`), Cargo Seizure Memo (`fir_record.docx`).
   - **Evidence**: Impounded Commercial Consignment Box (`EVID-2026-00077`).

---

## 4. Directory Layout of Demo Assets

All seed data lives within the project repository under version control:

```
backend/
├── demo_data/
│   ├── fixtures.json          # Structured declarative seed catalog (users, cases, evidence, custody)
│   ├── embeddings.json        # Pre-computed 768-dimensional pgvector text embeddings
│   └── files/                 # Physical binary documents uploaded to MinIO/S3
│       ├── fir_report.pdf
│       ├── cctv_log.pdf
│       ├── statement_v1.pdf
│       ├── statement_v2.pdf
│       ├── intercept.pdf
│       ├── confidential.pdf
│       ├── verified.pdf
│       ├── fir_555.docx
│       ├── bank_ledger.docx
│       ├── hawala.docx
│       ├── audit.docx
│       ├── ballistics.docx
│       ├── ballistic_report.docx
│       ├── witness_statement.docx
│       ├── deposition_test.docx
│       ├── fir_record.docx
│       ├── alpha.docx
│       ├── bravo.docx
│       ├── crime_scene.jpg
│       └── fesibility.png
├── app/
│   └── seed_demo.py           # Core idempotent seeding engine
scripts/
├── seed_demo_data.py          # Convenience CLI wrapper
└── reset_demo_data.py         # Development-only clean reset utility
```

---

## 5. Local Setup & Reproduction on a New Machine

Follow these simple steps on any fresh clone:

### Step 1: Start Infrastructure Containers
```bash
docker compose -f infrastructure/docker-compose.yml up -d
```
This launches:
- PostgreSQL 16 with `pgvector` on port `5432`
- Redis 7 on port `6379`
- MinIO S3 Object Storage on port `9000` (Console on `9001`)

### Step 2: Run Database Migrations
```bash
cd backend
alembic upgrade head
```

### Step 3: Seed Demo Data & Object Storage
```bash
python scripts/seed_demo_data.py
# Or from backend/:
python -m app.seed_demo
```

### Step 4: Launch Backend & Frontend
```bash
# Terminal 1: Backend
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` and use the evaluation quick-fill buttons or enter `officer@ncrb.gov.in` / `Investigator@2026!`.

---

## 6. Idempotency & Safe Reset

### Idempotent Seeding
The seeding command `python scripts/seed_demo_data.py` is **100% idempotent**:
- Running it on a fresh database creates the full demo environment.
- Running it again on an existing database detects existing records, updates missing linkages, and skips duplicating entities or hash chains.

### Safe Development-Only Reset
To purge demo data and clean storage buckets for a fresh demonstration run:
```bash
python scripts/reset_demo_data.py --force
```
> [!CAUTION]
> The reset utility includes a strict environment guard (`if settings.APP_ENV == "production"`), preventing accidental execution in production deployments.

---

## 7. Cloud Deployment (e.g. Render)

When deploying to cloud platforms like Render:

### Environment Variables
Configure the following in the Render dashboard:

| Variable | Recommended Render Value | Description |
|----------|--------------------------|-------------|
| `APP_ENV` | `production` | Enables strict security guards |
| `APP_DEBUG` | `False` | Disables verbose debug logging |
| `POSTGRES_SERVER` | `${dbservice.RENDER_INTERNAL_HOSTNAME}` | Managed PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_USER` | `${dbservice.USER}` | Database user |
| `POSTGRES_PASSWORD` | `${dbservice.PASSWORD}` | Database password |
| `POSTGRES_DB` | `${dbservice.DATABASE}` | Database name |
| `REDIS_HOST` | `${redisservice.RENDER_INTERNAL_HOSTNAME}` | Managed Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_PASSWORD` | `${redisservice.PASSWORD}` | Redis password |
| `S3_ENDPOINT_URL` | `https://s3.<region>.amazonaws.com` or MinIO URL | S3 API endpoint |
| `S3_ACCESS_KEY` | `<access-key>` | Storage credentials |
| `S3_SECRET_KEY` | `<secret-key>` | Storage credentials |
| `S3_BUCKET_DOCUMENTS` | `docshield-documents` | Documents bucket |
| `S3_BUCKET_EVIDENCE` | `docshield-evidence` | Evidence bucket |
| `JWT_SECRET_KEY` | `<generate-64-char-hex-key>` | Cryptographic session signing key |

### Render Build & Release Command
Set the **Release Command** (runs automatically after build, before traffic cutover):
```bash
alembic upgrade head && python scripts/seed_demo_data.py
```
This guarantees every deployment automatically creates missing buckets, seeds the flagship cases and documents, and verifies the cryptographic audit and custody ledgers.

---

## 8. Verification Commands

Verify the live seeded environment using HTTP requests:

```bash
# 1. Authenticate as Investigator
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"officer@ncrb.gov.in","password":"Investigator@2026!"}' | jq -r .access_token)

# 2. List Seeded Cases
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/cases | jq '.items[] | {case_number, title, status, priority}'

# 3. Verify Custody Chain of Seeded Evidence
# Replace <evidence_id> with any evidence UUID from CR-2026-CYBER01
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/evidence/<evidence_id>/custody/verify | jq .

# 4. Authenticate as System Admin & Verify Audit Ledger
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@ncrb.gov.in","password":"Admin@DocShield2026!"}' | jq -r .access_token)

curl -s -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8000/api/v1/admin/audit/verify | jq .
```
Expected verification response:
```json
{
  "valid": true,
  "events_checked": 30,
  "first_invalid_event": null,
  "reason": null
}
```

