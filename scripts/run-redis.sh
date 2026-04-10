#!/usr/bin/env bash
# Start only Redis (port 6379) for local API/worker development.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not on PATH. Start Redis yourself, e.g.:"
  echo "  macOS: brew install redis && brew services start redis"
  echo "  Or install Docker and re-run this script."
  exit 1
fi
docker compose -f infra/docker-compose.yml up -d redis
echo "Redis should be available at redis://127.0.0.1:6379/0 (wait a few seconds if the container just started)."
