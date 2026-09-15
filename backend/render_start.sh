#!/usr/bin/env bash
set -e

echo "=================================================="
echo " Starting SIH-190 FastAPI Backend on Render"
echo " Environment: ${APP_ENV:-production}"
echo " Listening on Port: ${PORT:-10000}"
echo "=================================================="

# Validate DATABASE_URL format
if [[ "$DATABASE_URL" =~ ^https?:// ]]; then
    echo "=================================================="
    echo "[render_start] ERROR: DATABASE_URL is set to an HTTP(S) URL: $DATABASE_URL"
    echo "[render_start] DATABASE_URL must be a PostgreSQL connection URI, e.g.:"
    echo "  postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres"
    echo "  OR postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres"
    echo "[render_start] If using Supabase, obtain the Connection String from:"
    echo "  Supabase Dashboard -> Project Settings -> Database -> Connection string -> URI"
    echo "[render_start] Do NOT use the Project API URL (https://xyz.supabase.co)."
    echo "=================================================="
    exit 1
fi

# Run database migrations if DATABASE_URL or POSTGRES_SERVER is configured
if [ -n "$DATABASE_URL" ] || [ -n "$POSTGRES_SERVER" ]; then
    echo "[render_start] Checking and applying database migrations with Alembic..."
    alembic upgrade head || echo "[render_start] Migration warning encountered. Proceeding with application startup..."
else
    echo "[render_start] No database configuration detected. Skipping migrations."
fi

echo "[render_start] Launching Uvicorn server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
