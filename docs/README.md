# Axiom documentation

Product and engineering docs for the Axiom platform live here.

## Guides

| Document | Description |
| -------- | ----------- |
| [architecture.md](./architecture.md) | Components, data flow, jobs vs schedules, shared libraries |
| [api-spec.md](./api-spec.md) | Routes, authentication, OpenAPI entry points |
| [compliance-model.md](./compliance-model.md) | Compliance pipeline, env vars, exceptions |
| [deployment.md](./deployment.md) | Processes, Docker Compose, env, migrations, production notes |

## Layout

| Path          | Purpose                                                            |
| ------------- | ------------------------------------------------------------------ |
| `apps/api`    | FastAPI HTTP API, SQLAlchemy models, Alembic migrations; `axiom_api.types` for shared JSON/JWT/error shapes |
| `apps/web`    | Next.js customer / operator UI                                     |
| `apps/worker` | Celery workers and scheduled jobs                                  |
| `packages/*`  | Shared libraries (TS + Python extractors) and configs              |
| `infra/`      | Docker Compose (API, web, worker, Postgres, Redis) and future IaC  |

## Principles

- **Compliance first**: respect `robots.txt`, rate limits, and site protections; no bypass.
- **Modular boundaries**: API, web, and worker communicate via HTTP, queues, and the database—not shared mutable process state.
- **Observability**: structured logs and trace-friendly request IDs (expanded in later phases).
