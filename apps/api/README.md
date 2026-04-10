# Axiom API

FastAPI service for the Axiom platform.

## Run locally

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

(`main.py` at the project root adds `src` to `sys.path`; alternatively use `uvicorn axiom_api.main:app` after `pip install -e .` with `PYTHONPATH=src`.)

Open [http://localhost:8000/docs](http://localhost:8000/docs).

`POST /scrape` **by default** enqueues `axiom.scrape` on Celery and returns **202** with **`task_id`**. Use `"async": false` for synchronous extraction in the API. Set `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` (same as workers; queue name **`axiom`**).

## PostgreSQL & migrations

ORM: **SQLAlchemy 2** (async via **asyncpg**). `DATABASE_URL` uses `postgresql+asyncpg://...`. **Alembic** uses a sync URL (`postgresql+psycopg://...`) derived automatically for `upgrade` / `downgrade`.

Start Postgres (e.g. `docker compose -f infra/docker-compose.yml up -d postgres`), then:

```bash
cd apps/api
pip install -e ".[dev]"
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://axiom:axiom@localhost:5432/axiom}"
alembic upgrade head
```

Create a new revision after model changes:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Docker

From the **repository root**:

```bash
docker build -f apps/api/Dockerfile -t axiom-api .
```

Or run the full stack from the repo root: `docker compose -f infra/docker-compose.yml up --build`.

## Test

```bash
pytest
ruff check src tests
```
