#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== [SIH-190] Stopping Infrastructure Services ==="
docker compose -f "$ROOT_DIR/infrastructure/docker-compose.yml" down
echo "=== Infrastructure stopped ==="
