# Deployment

This document describes how Axiom components are run together, which **environment variables** matter, and operational practices for **migrations**, **workers**, and **scheduled jobs**.

## Processes

| Process | Command (typical) | Purpose |
| ------- | ----------------- | ------- |
| API | `uvicorn axiom_api.main:app --host 0.0.0.0 --port 8000` | HTTP API |
| Worker | `celery -A axiom_worker.celery_app worker --loglevel=info` | Execute `axiom.scrape` and other tasks |
| Beat | `celery -A axiom_worker.celery_app beat --loglevel=info` | Triggers **`axiom.tick_schedules`** every minute for cron schedules |
| Web | `next start` (or `pnpm` dev) | Next.js UI |

**Cron / recurring jobs** require **both** a Celery worker and **Beat**. Without Beat, `job_schedules` rows will not advance automatically.

## Docker Compose (local / demo)

From the repository root:

```bash
docker compose -f infra/docker-compose.yml up --build
```

Services include **postgres**, **redis**, **api**, **worker**, **beat**, and **web**. Ports **8000** (API) and **3000** (web) are published by default. See [`infra/README.md`](../infra/README.md) for partial stacks (e.g. databases only) and building the web image with a custom `NEXT_PUBLIC_API_URL`.

### Migrations in containers

The API **Dockerfile** does not automatically run Alembic. For a fresh database, run migrations **once** before or right after the API starts, for example:

```bash
docker compose -f infra/docker-compose.yml run --rm api alembic upgrade head
```

(Adjust service name and working directory to match your image layout; locally, `cd apps/api && alembic upgrade head` is equivalent.)

## Environment variables

### API

| Variable | Notes |
| -------- | ----- |
| `DATABASE_URL` | Async SQLAlchemy URL, e.g. `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | Used for compliance rate limiting when compliance reads it |
| `LOG_FORMAT` | `json` (one JSON object per line for aggregators) or `text` (default) |
| `LOG_LEVEL` | `INFO` (default), `DEBUG`, `WARNING`, etc. |
| `LOG_ACCESS_LOG` | `true` / `false` — disable per-request `http_request` access lines |
| `LOG_ACCESS_SKIP_PATHS` | Comma-separated paths excluded from access logs (default `/health`) |
| `JWT_SECRET_KEY` | **Required in production** — at least 32 characters; never use the dev default |
| `JWT_ISSUER` / `JWT_AUDIENCE` | Embedded in access tokens and validated on every request (defaults `axiom` / `axiom-api`) |
| `CORS_ALLOW_ORIGINS` | Comma-separated browser origins (default `http://localhost:3000` only) |
| `API_DOCS_ENABLED` | In production, must be `true` to expose `/docs` and `/openapi.json` |
| `MAX_REQUEST_BODY_BYTES` | Reject `POST`/`PUT`/`PATCH` bodies larger than this (default 10 MiB) |
| `ENABLE_HSTS` | Set `true` when the API is served only over HTTPS (adds `Strict-Transport-Security`) |
| `API_KEY_PEPPER` | Optional; defaults to `JWT_SECRET_KEY` for API key hashing |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Required for async `POST /scrape` and `POST /jobs` |

Compliance variables are documented in [compliance-model](./compliance-model.md) and `.env.example`.

### Worker and Beat

| Variable | Notes |
| -------- | ----- |
| `CELERY_BROKER_URL` | Must match API for task delivery |
| `CELERY_RESULT_BACKEND` | Task results (e.g. Celery task IDs) |
| `DATABASE_URL` | Required for **`axiom.tick_schedules`** (reads/writes `job_schedules` / jobs). Use a **sync** driver URL internally if you strip `+asyncpg` (worker code adapts). |
| Compliance vars | Same as API so worker enforcement matches API policy |

### Web

| Variable | Notes |
| -------- | ----- |
| `NEXT_PUBLIC_API_URL` | Browser-facing API origin; baked at **build** time for production images |

## Production checklist

1. **Secrets**: Strong `JWT_SECRET_KEY`, database credentials, and Redis ACLs if exposed.
2. **HTTPS**: Terminate TLS at a load balancer or ingress; forward to Uvicorn over HTTP internally.
3. **Database**: Run `alembic upgrade head` on deploy; keep migrations in CI.
4. **Redis**: Highly available instance or managed Redis for broker + rate limiting.
5. **Workers**: Scale Celery workers horizontally; keep **prefetch** low for long I/O tasks (already set in `celery_app`).
6. **Beat**: Run **exactly one** Beat scheduler per logical queue (or use distributed beat if you outgrow a single process).
7. **Playwright**: Worker and API images install Chromium; ensure runtime deps match target OS in Dockerfile.
8. **CORS**: Update `CORSMiddleware` allowlist in `apps/api` for real web origins (not only `localhost:3000`).

## CI

GitHub Actions runs **ruff**, **pytest**, and (for the API job) **Alembic upgrade** against a service Postgres. Mirror that order in deploy pipelines: migrations before turning traffic on new code when schema changes.

## Related

- [Architecture](./architecture.md)
- [API specification](./api-spec.md)
