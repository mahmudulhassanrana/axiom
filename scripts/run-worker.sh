#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
"$ROOT/scripts/ensure-redis.sh"
cd "$ROOT/apps/worker"
exec celery -A worker worker --loglevel=info
