#!/usr/bin/env bash
set -e

echo "=================================================="
echo " Starting SIH-190 FastAPI Backend on Render"
echo " Environment: ${APP_ENV:-production}"
echo " Listening on Port: ${PORT:-10000}"
echo "=================================================="

# Run database migrations if DATABASE_URL or POSTGRES_SERVER is configured
if [ -n "$DATABASE_URL" ] || [ -n "$POSTGRES_SERVER" ]; then
    echo "[render_start] Checking and applying database migrations with Alembic..."
    alembic upgrade head || echo "[render_start] Migration warning encountered. Proceeding with application startup..."
else
    echo "[render_start] No database configuration detected. Skipping migrations."
fi

echo "[render_start] Launching Uvicorn server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
