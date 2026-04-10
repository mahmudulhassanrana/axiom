#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../apps/api"
exec uvicorn main:app --reload
