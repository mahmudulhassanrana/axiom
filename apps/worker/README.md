# Axiom worker

Celery workers for async jobs (scraping pipelines, ingestion, schedules).

### Tasks

| Name           | Description                                                                                                                                                                               |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `axiom.ping`   | Health probe for the worker process.                                                                                                                                                      |
| `axiom.scrape` | Normalized URL extraction via `axiom-extractors` (`html_requests` or `playwright`). Retries transient failures with exponential backoff + jitter (max 5 retries, backoff capped at 600s). |

## Run locally

**Requires Redis** on `localhost:6379` (broker + results). The `worker` module loads the monorepo root `.env` and uses `REDIS_URL` as the broker when `CELERY_BROKER_URL` is unset. If Redis is down, Celery exits immediately with a short message (instead of retrying forever). Start Redis first:

- From the **repository root**: `./scripts/run-redis.sh` (Docker), or
- **Docker manually**: `docker compose -f infra/docker-compose.yml up -d redis`, or
- **macOS (Homebrew)**: install first, then start — `brew install redis && brew services start redis`  
  (If you see *Formula redis is not installed*, run `brew install redis`.)  
  One-shot from repo root: `./scripts/install-redis-brew.sh` or `pnpm redis:brew`

Wait until `redis-cli -u redis://localhost:6379 ping` prints `PONG`, then start Celery again.

This checkout must stay a **monorepo** so `../../packages/*` path dependencies resolve.

```bash
cd apps/worker
python3.11 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
# Optional: browsers for Playwright-backed scrapes (first run may download binaries)
python -m playwright install chromium
export CELERY_BROKER_URL="${CELERY_BROKER_URL:-redis://localhost:6379/0}"
export CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND:-redis://localhost:6379/0}"
celery -A worker worker --loglevel=info
```

See [`.env.example`](.env.example) for broker URLs. Use a `.venv` directory instead of `venv` if you prefer; both are gitignored.

(`worker.py` adds `src` to `sys.path` so `axiom_worker` resolves without a prior editable install; you can still use `celery -A axiom_worker.celery_app` after `pip install -e .`.)

## Docker

From the **repository root**:

```bash
docker build -f apps/worker/Dockerfile -t axiom-worker .
```

Or use `docker compose -f infra/docker-compose.yml up --build` from the repository root.

## Test

```bash
pytest
ruff check src tests
```
