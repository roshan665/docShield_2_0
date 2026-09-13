#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== [SIH-190] Starting Infrastructure Services (PostgreSQL + Redis + MinIO) ==="
docker compose -f "$ROOT_DIR/infrastructure/docker-compose.yml" up -d

echo "Waiting for services to become healthy..."
sleep 3
docker compose -f "$ROOT_DIR/infrastructure/docker-compose.yml" ps
echo "=== Infrastructure is operational ==="
