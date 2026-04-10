# Axiom

**Axiom** is a full-stack SaaS-style web scraping platform: a **Next.js** dashboard and **FastAPI** API create **jobs**, a **Celery** worker fetches and extracts pages, and **PostgreSQL** stores jobs, runs, and extracted data. **Redis** backs the Celery broker and optional compliance rate limits.

---

## 📌 Project overview

Axiom lets teams submit URLs as **scrape jobs**, track **status** end-to-end (`queued` → `running` → `completed` / `failed`), and retrieve **normalized text and metadata** from stored results. Processing is **asynchronous** by default so the API stays responsive while workers handle I/O-heavy fetches.

**Capabilities**

| Area | What you get |
|------|----------------|
| **Job-based scraping** | One URL per job (with runs and extracted rows in Postgres). |
| **Async worker processing** | Celery tasks on the `axiom` queue; retries for transient errors. |
| **Result storage** | `extracted_data` linked to runs and jobs; JSON-friendly payloads. |
| **Dashboard UI** | Next.js app for auth-aware flows and job visibility. |

---

## 🏗 Architecture

```text
┌─────────────┐     HTTPS / JSON     ┌─────────────┐     enqueue      ┌─────────────┐
│  Next.js    │ ──────────────────► │   FastAPI   │ ───────────────► │    Redis    │
│  (apps/web) │                     │ (apps/api)  │                  │   (broker)  │
└─────────────┘                     └──────┬──────┘                  └──────▲──────┘
                                           │                               │
                                           │ SQLAlchemy                    │ consume
                                           ▼                               │
                                    ┌─────────────┐                 ┌──────┴──────┐
                                    │ PostgreSQL  │ ◄── status /    │   Celery    │
                                    │             │     inserts     │   worker    │
                                    └─────────────┘                 └─────────────┘
```

- **Frontend (Next.js)** → calls the **API (FastAPI)** with JWT (or API keys where supported).
- **API** → persists **jobs** and **runs**, enqueues **`axiom.scrape`** via **Redis** (Kombu/Celery).
- **Worker (Celery)** → claims runs, scrapes with **HTML requests** or **Playwright**, writes **`extracted_data`**, updates job/run status (sync DB access aligned with the same `DATABASE_URL`).
- **PostgreSQL** → source of truth for users, orgs, jobs, runs, extractions, audits, schedules.
- **Redis** → Celery broker/result backend defaults; compliance can use Redis for per-domain limits.
- **SQLAlchemy** → async ORM in the API (`asyncpg` driver).
- **JWT** → Bearer access tokens from `/auth/login` and `/auth/register`.

---

## ✨ Features

- 🔐 **Authentication** — Email/password, JWT access tokens, optional API keys (`/auth/*`).
- 📋 **Job creation & tracking** — `POST /jobs`, `GET /jobs`, `GET /jobs/{id}` with runs and payloads.
- 🕷 **Scraping engines** — `html_requests` (default) and `playwright`; compliance hooks (robots, lists, rate limits).
- ⚙️ **Worker queue** — Celery task `axiom.scrape`, dedicated queue, retries with backoff.
- 📊 **Job lifecycle** — `queued` → `running` → `completed` / `failed` mirrored on jobs and runs.
- 💾 **Data storage** — Extracted text, title, links, metadata in Postgres; audit events for operations.
- 🖥 **Dashboard UI** — Next.js app under `apps/web` (login, settings, sources, scrape flows).
- 📅 **Schedules** — Cron-style job schedules API (`/schedules`) and beat-driven ticks (worker).
- 📤 **Exports** — Download endpoints under `/exports` (run/job-oriented exports).
- 🩺 **Health** — `/health` and related checks for load balancers.

---

## 📁 Project structure

| Path | Role |
|------|------|
| `apps/web` | **Next.js 15** frontend (React 19, Tailwind). |
| `apps/api` | **FastAPI** app (`main.py` → `create_app()`), Alembic migrations, OpenAPI at `/docs`. |
| `apps/worker` | **Celery** worker (`celery -A worker worker`); tasks under `axiom_worker.tasks`. |
| `packages/compliance` | Shared compliance (robots, domain lists, Redis rate limiting). |
| `packages/extractors` | HTML / Playwright extractors and parsing helpers. |
| `packages/exporters` | Export helpers used by the API. |
| `packages/shared` | Shared TS types/utilities for the web app. |
| `packages/testkit` | Test fixtures / dev utilities. |
| `packages/typescript-config` | Shared **TypeScript** config. |
| `infra/` | Docker Compose and supporting infra (e.g. Redis). |
| `scripts/` | Helper scripts (Redis, worker, etc.). |

---

## 🚀 Setup

### A. Requirements

- **Python** 3.11+
- **Node.js** 20+ (LTS recommended)
- **PostgreSQL** (local or Docker)
- **Redis** (broker for Celery)

### B. Database

Create a database named **`axiom`**. Example (local PostgreSQL on port **5435**):

```bash
createdb -h 127.0.0.1 -p 5435 -U postgres axiom
```

Run API migrations from `apps/api` (Alembic) after installing deps:

```bash
cd apps/api && source .venv/bin/activate && alembic upgrade head
```

### C. Environment variables

Copy examples and adjust:

```bash
cp .env.example .env
# optional overrides:
# cp apps/api/.env.example apps/api/.env
# cp apps/worker/.env.example apps/worker/.env
```

**API (async SQLAlchemy)** — use the `asyncpg` scheme (worker reads the same variable and normalizes for `psycopg`):

```env
DATABASE_URL=postgresql+asyncpg://postgres:@127.0.0.1:5435/axiom
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
JWT_SECRET_KEY=change-me-to-a-long-random-string
```

If the worker cannot infer the monorepo root, set:

```env
AXIOM_REPO_ROOT=/absolute/path/to/axiom
```

### D. Run backend

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API base URL: `http://localhost:8000` · OpenAPI: `http://localhost:8000/docs`

### E. Run worker

From **`apps/worker`** (entry module loads repo root `.env`, then `apps/api/.env`, then `apps/worker/.env`):

```bash
cd apps/worker
python3.11 -m venv venv
source venv/bin/activate
pip install -U pip && pip install -r requirements.txt
celery -A worker worker --loglevel=info
```

Ensure **Redis** is reachable (e.g. `./scripts/run-redis.sh` from the repo root). Optional: `export $(grep -v '^#' ../../.env | xargs)` if you rely on shell-injected vars only.

### F. Run frontend

```bash
cd apps/web
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_URL` (e.g. in root `.env`) to your API origin, e.g. `http://localhost:8000`.

---

## 🔌 API usage (curl)

Replace `TOKEN` and IDs with values from your environment.

**Register (returns JWT)**

```bash
curl -sS -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"your-secure-password","full_name":"You"}'
```

**Login**

```bash
curl -sS -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"your-secure-password"}'
```

**Create scrape job**

```bash
curl -sS -X POST http://localhost:8000/jobs \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","engine":"html_requests"}'
```

**List jobs**

```bash
curl -sS http://localhost:8000/jobs \
  -H "Authorization: Bearer TOKEN"
```

**Get job detail (runs + embedded extraction payloads)**

```bash
curl -sS http://localhost:8000/jobs/JOB_UUID \
  -H "Authorization: Bearer TOKEN"
```

**Get extraction rows for a job**

```bash
curl -sS http://localhost:8000/jobs/JOB_UUID/results \
  -H "Authorization: Bearer TOKEN"
```

**Synchronous scrape (optional, no job row)**

```bash
curl -sS -X POST "http://localhost:8000/scrape?async=false" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","engine":"html_requests"}'
```

---

## 🔄 Job flow

```text
User / UI
   │  JWT
   ▼
FastAPI  ──►  validate + compliance (API)  ──►  INSERT job + run (queued)
   │
   │  enqueue axiom.scrape (Redis)
   ▼
Celery worker  ──►  claim run (running)  ──►  fetch + extract  ──►  INSERT extracted_data
   │                                                      │
   └────────────────────────  UPDATE job/run (completed | failed)
                                      │
                                      ▼
                               Dashboard polls GET /jobs/{id}
```

---

## 🛠 Troubleshooting

| Symptom | Likely cause | What to do |
|--------|----------------|------------|
| Worker logs `DATABASE_URL is not set` / status never updates | Worker cannot load DB URL | Put `DATABASE_URL` in **repo root** `.env`; set `AXIOM_REPO_ROOT`; restart worker. |
| Jobs stuck in **`queued`** | No consumer | Start Celery: `celery -A worker worker`; confirm Redis is up and queue `axiom` exists. |
| API **503** / DB errors | Postgres down or wrong URL | Check `DATABASE_URL`, port **5435**, and `alembic upgrade head`. |
| **`ModuleNotFoundError: axiom_api`** | Wrong cwd / path | Run `uvicorn` from `apps/api` so `main.py` adds `src` to `PYTHONPATH`. |
| **`ImportError` for worker packages | Missing install | `pip install -r requirements.txt` in `apps/worker` from that directory. |
| CORS errors from browser | Origin not allowed | Set `CORS_ALLOW_ORIGINS` (see `.env.example`). |

---

## 🧪 Development notes

- **Async-first API** — FastAPI + `AsyncSession` for non-blocking I/O; heavy sync work offloaded with `asyncio.to_thread` where needed.
- **Modular monorepo** — Shared packages under `packages/` keep compliance and extraction logic out of app code.
- **Scalable shape** — Stateless API, horizontal workers, external broker (Redis) and database (Postgres).

---

## 🗺 Future roadmap

- 🔁 Richer **scheduling** UX and monitoring
- 📄 **Multi-page crawling** and crawl budgets
- 📡 **Real-time** job updates (WebSockets / SSE)
- 🏢 Hardened **multi-tenant SaaS** (billing, quotas, regions)
- 📦 More **export** formats and bulk download UX

---

## 📄 License

See the repository’s `LICENSE` file if present; otherwise treat usage as defined by the project owner.
