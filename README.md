# Axiom

Compliant, rate-limited, multi-format scraping and ingestion platform.

## Monorepo layout

```
apps/
  api/       FastAPI service
  web/       Next.js application
  worker/    Celery workers (Redis broker)
packages/
  shared/              Shared TypeScript utilities and constants
  typescript-config/   Base TypeScript configs for apps
  extractors/          Python extractors (requests/BS4 + Playwright)
docs/                  Product and engineering documentation
infra/                 Docker Compose and future infrastructure code
scripts/               Local run helpers (API, worker, web)
```

## Prerequisites

- **Node.js** 20+ and **npm** (or **pnpm** 9 with `corepack enable`)
- **Python** 3.11+ (API, worker, and `packages/extractors`)
- **PostgreSQL** and **Redis** on the host (or only Redis/Postgres via Docker)

## Local development without Docker (full stack on the host)

1. **PostgreSQL and Redis** — start services locally (example: `brew services start postgresql redis` on macOS), or run only databases:

   ```bash
   docker compose -f infra/docker-compose.yml up -d postgres redis
   ```

2. **Environment**

   - API: copy [`apps/api/.env.example`](apps/api/.env.example) to `apps/api/.env` and set `DATABASE_URL`, Redis/Celery URLs, and `JWT_SECRET_KEY`.
   - Web: copy [`apps/web/.env.example`](apps/web/.env.example) to `apps/web/.env.local` (optional; defaults to `http://localhost:8000`).
   - Alternatively, copy the combined [`.env.example`](.env.example) at the repo root to `.env` for a single file used when tooling loads env from the root.

3. **API (FastAPI)**

   ```bash
   cd apps/api
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   alembic upgrade head
   uvicorn main:app --reload
   ```

   Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). If PostgreSQL is not up yet, the API still starts; connectivity is logged at startup.

4. **Worker (Celery)**

   ```bash
   cd apps/worker
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   celery -A worker worker --loglevel=info
   ```

   Default broker: `redis://localhost:6379/0` (override with `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`).

5. **Web (Next.js)**

   Install **from the repository root** (workspaces + [`/.npmrc`](.npmrc); avoids an npm 10 bug when installing only inside `apps/web`):

   ```bash
   npm install
   cd apps/web && npm run dev
   ```

   Open [http://localhost:3000](http://localhost:3000). Use **Settings** to paste a JWT from `POST /auth/login`, then **Scrape** to call `POST /scrape`.

### Run scripts (from repository root)

| Command | Description |
| --- | --- |
| `./scripts/run-api.sh` | `uvicorn main:app --reload` in `apps/api` |
| `./scripts/run-worker.sh` | `celery -A worker worker --loglevel=info` in `apps/worker` |
| `./scripts/run-redis.sh` | Start Redis (`6379`) via Docker Compose for local Celery/API |
| `./scripts/run-web.sh` | `npm run dev` in `apps/web` |

Make scripts executable once: `chmod +x scripts/run-*.sh`.

### pnpm (optional)

From the repo root: `pnpm install` and `pnpm dev:web` still work; `apps/web` uses `file:` links compatible with both npm and pnpm.

### npm: `Cannot read properties of null (reading 'matches')`

That comes from npm’s arborist when deduping **workspace** + **`file:`** dependencies. The repo root [`.npmrc`](.npmrc) sets `install-strategy=nested` to avoid it. Run **`npm install` from the repo root**, not only under `apps/web`.

## Quick start (Docker — full stack)

From the repository root:

```bash
docker compose -f infra/docker-compose.yml up --build
```

Then open [http://localhost:3000](http://localhost:3000) (web) and [http://localhost:8000/docs](http://localhost:8000/docs) (API). See [`infra/README.md`](infra/README.md) for ports and build args.

## Scripts (root, pnpm)

| Command | Description |
| --- | --- |
| `pnpm dev:web` | Next.js dev server |
| `pnpm build:web` | Production build |
| `pnpm lint:web` | ESLint (web) |
| `pnpm format` | Prettier write |
| `pnpm format:check` | Prettier check |

## CI

GitHub Actions runs lint/tests for `apps/api`, `apps/worker`, and `apps/web` on push and pull requests to `main`.

## License

Proprietary — All rights reserved.
