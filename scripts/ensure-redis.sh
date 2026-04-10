#!/usr/bin/env bash
# If the default Redis broker is unreachable, start Redis via Docker (infra compose).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
URL="${CELERY_BROKER_URL:-${REDIS_URL:-redis://127.0.0.1:6379/0}}"
case "$URL" in
  redis://* | rediss://*) ;;
  *) exit 0 ;;
esac
if command -v redis-cli >/dev/null 2>&1; then
  if redis-cli -u "$URL" ping 2>/dev/null | grep -q PONG; then
    exit 0
  fi
fi
echo "ensure-redis: broker not reachable at $URL — starting Redis container…"
"$ROOT/scripts/run-redis.sh"
# Brief pause for the daemon to accept connections
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if command -v redis-cli >/dev/null 2>&1 && redis-cli -u "$URL" ping 2>/dev/null | grep -q PONG; then
    echo "ensure-redis: Redis is up."
    exit 0
  fi
  sleep 1
done
echo "ensure-redis: Redis still not reachable. Install/start Redis manually." >&2
exit 1
