# Deploying SIH-190 Platform to Render (Separate Services)

This guide provides step-by-step instructions for deploying the **FastAPI Backend** and **Next.js Frontend** as separate, independent Web Services on [Render](https://render.com).

---

## Architecture Overview on Render

```
                                    +----------------------------------+
                                    |         User's Browser           |
                                    +-----------------+----------------+
                                                      |
                                     HTTPS Requests   |   Direct Auth / DB
                                                      |   (Anon Key)
                                                      v
  +----------------------------------+        +-------+--------------------------+
  |      Render Backend Service      |        |      Render Frontend Service     |
  |      (FastAPI / Python 3.12)     |<-------|           (Next.js 14)           |
  |  https://sih190-backend.onrender |  REST  | https://sih190-frontend.onrender |
  +-----------------+----------------+        +-----------------+----------------+
                    |                                           |
                    +--------------------+----------------------+
                                         |
                                         v
                         +---------------+---------------+
                         |   Managed Database / Cloud    |
                         |   - PostgreSQL (Supabase/DB)  |
                         |   - Redis (Upstash/Render)    |
                         |   - S3 / Cloud Storage        |
                         +-------------------------------+
```

---

## Part 1: Deploy the FastAPI Backend

### Step 1: Create a New Web Service on Render
1. Log into your [Render Dashboard](https://dashboard.render.com).
2. Click **New +** &rarr; **Web Service**.
3. Connect your Git repository (`SIH-190` or your fork).
4. Configure the service settings:

| Field | Recommended Value | Description |
| :--- | :--- | :--- |
| **Name** | `sih190-backend` | Name of your backend service |
| **Region** | Singapore / Frankfurt / Oregon | Choose the region closest to your users |
| **Branch** | `main` | Your production deployment branch |
| **Root Directory** | `backend` | **Important**: Tells Render to run commands inside the `backend` folder |
| **Runtime** | `Python 3` | Render native Python runtime |
| **Build Command** | `pip install -r requirements.txt` | Installs Python packages |
| **Start Command** | `bash render_start.sh` | Runs Alembic migrations and launches Uvicorn on `$PORT` |
| **Instance Type** | Free or Starter | |

> [!TIP]
> Under **Advanced Settings**:
> - **Health Check Path**: `/health` (Render will automatically verify service readiness)
> - **Auto-Deploy**: Yes (triggers on git push)

---

### Step 2: Configure Backend Environment Variables
In the Render Web Service dashboard, go to the **Environment** tab and add the following variables:

| Key | Example / Recommended Value | Description |
| :--- | :--- | :--- |
| `APP_ENV` | `production` | Application runtime environment |
| `APP_DEBUG` | `false` | Disables debug mode in production |
| `JWT_SECRET_KEY` | *(Generate a 64-character random hex string)* | Key used to sign JWT tokens |
| `DATABASE_URL` | `postgresql://user:password@host:5432/dbname` | Full Postgres connection URI (Supabase or Render Postgres) |
| `REDIS_URL` | `redis://default:password@host:6379` | Optional Redis URL for caching & rate limiting |
| `BACKEND_CORS_ORIGINS` | `https://sih190-frontend.onrender.com,http://localhost:3000` | Comma-separated list of allowed frontend origins |
| `S3_ENDPOINT_URL` | `https://s3.amazonaws.com` or Supabase storage URL | S3 API endpoint |
| `S3_ACCESS_KEY` | *(Your storage access key)* | Cloud storage access key |
| `S3_SECRET_KEY` | *(Your storage secret key)* | Cloud storage secret key |
| `S3_BUCKET_DOCUMENTS` | `sih190-documents` | Bucket for case documents |
| `S3_BUCKET_EVIDENCE` | `sih190-evidence` | Bucket for cryptographic evidence |
| `GEMINI_API_KEY` | *(Your Google Gemini API Key)* | Required for AI OCR, summarization, and vector search |

Click **Save Changes**. Render will automatically trigger a build and launch your backend service. Once ready, copy your backend URL (e.g. `https://sih190-backend.onrender.com`).

---

## Part 2: Deploy the Next.js Frontend

### Step 1: Create a New Web Service on Render
1. Go back to the [Render Dashboard](https://dashboard.render.com).
2. Click **New +** &rarr; **Web Service**.
3. Connect the same Git repository.
4. Configure the service settings:

| Field | Recommended Value | Description |
| :--- | :--- | :--- |
| **Name** | `sih190-frontend` | Name of your frontend service |
| **Region** | *(Same region as backend)* | Minimizes latency |
| **Branch** | `main` | Production branch |
| **Root Directory** | `frontend` | **Important**: Tells Render to run commands inside `frontend` |
| **Runtime** | `Node` | Render native Node runtime |
| **Build Command** | `npm install && npm run build` | Compiles Next.js production bundle |
| **Start Command** | `npm start` | Starts Next.js production server (binds automatically to Render's `$PORT`) |
| **Instance Type** | Free or Starter | |

---

### Step 2: Configure Frontend Environment Variables
In the frontend service's **Environment** tab, set:

| Key | Example / Value | Description |
| :--- | :--- | :--- |
| `NODE_VERSION` | `20.16.0` | Node.js version |
| `NEXT_PUBLIC_APP_NAME` | `Secure Evidence & Legal Lifecycle Platform` | Application display title |
| `NEXT_PUBLIC_API_URL` | `https://sih190-backend.onrender.com/api/v1` | **Points to your Render backend URL + `/api/v1`** |
| `NEXT_PUBLIC_SUPABASE_URL` | `https://chfamfherxqidgkezahl.supabase.co` | Your Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `sb_publishable_...` | Your Supabase anon public key |

Click **Save Changes**. Render will build the Next.js frontend and provide your frontend live URL (e.g., `https://sih190-frontend.onrender.com`).

---

## Part 3: Link Frontend & Backend CORS

Once both services are provisioned:
1. Copy your Frontend URL: `https://sih190-frontend.onrender.com`.
2. Go to your **Backend Service** &rarr; **Environment**.
3. Update `BACKEND_CORS_ORIGINS` to include your live frontend URL:
   ```env
   BACKEND_CORS_ORIGINS=https://sih190-frontend.onrender.com,http://localhost:3000
   ```
4. Save changes so the backend automatically redeploys with the updated CORS policy.

---

## Part 4: Database & Migration Notes

### Using Supabase PostgreSQL:
- Supabase provides a direct connection string in your Supabase Project Settings &rarr; Database &rarr; Connection String &rarr; URI.
- Set this connection string as the `DATABASE_URL` in the Render Backend environment.
- The platform's `config.py` automatically translates standard PostgreSQL connection strings into `postgresql+asyncpg://` for async SQLAlchemy queries and `postgresql+psycopg://` for Alembic migrations.

### Running Migrations:
- `backend/render_start.sh` automatically runs `alembic upgrade head` before launching Uvicorn on Render.
- If you prefer running migrations manually, you can open Render's **Shell** tab on the backend service and run:
  ```bash
  alembic upgrade head
  ```

---

## Verification & Health Check

1. **Verify Backend Liveness**:
   ```bash
   curl -I https://sih190-backend.onrender.com/health
   # Expected: HTTP/1.1 200 OK
   ```

2. **Verify Backend Interactive Docs**:
   Visit `https://sih190-backend.onrender.com/docs` in your browser (if `DEBUG` or `APP_DEBUG=true`).

3. **Verify Frontend**:
   Visit `https://sih190-frontend.onrender.com` in your browser.
