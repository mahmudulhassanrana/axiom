#!/usr/bin/env bash
# Install and start Redis on macOS/Linux via Homebrew (fixes "Formula redis is not installed").
set -euo pipefail
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is not installed or not on PATH." >&2
  echo "  Install: https://brew.sh" >&2
  echo "  Or start Redis with Docker from the repo root: ./scripts/run-redis.sh" >&2
  exit 1
fi
brew install redis
brew services start redis
echo ""
echo "Redis should be listening on port 6379."
echo "Verify:  redis-cli ping   # expect PONG"
