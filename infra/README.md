# Infrastructure

Docker Compose stack for local development and integration testing: **PostgreSQL**, **Redis**, **API** (FastAPI), **worker** (Celery), and **web** (Next.js).

## Full stack

From the **repository root**:

```bash
docker compose -f infra/docker-compose.yml up --build
```

| Service    | Port (host) | Notes                                         |
| ---------- | ----------- | --------------------------------------------- |
| `postgres` | 5432        | User/password/db: `axiom` / `axiom` / `axiom` |
| `redis`    | 6379        | Broker/backend for Celery                     |
| `api`      | 8000        | [OpenAPI docs](http://localhost:8000/docs)    |
| `web`      | 3000        | [App](http://localhost:3000)                  |
| `worker`   | —           | Celery worker (no published port)             |
| `beat`     | —           | Celery Beat (cron schedule ticks; no port)    |

### Browser API URL

`NEXT_PUBLIC_API_URL` is baked in at **image build** time. Default is `http://localhost:8000` (correct when you open the app from your machine while API is published on port 8000). Override when building:

```bash
NEXT_PUBLIC_API_URL=https://api.example.com docker compose -f infra/docker-compose.yml build web
```

### Databases only

To run only PostgreSQL and Redis (e.g. while developing API/web on the host):

```bash
docker compose -f infra/docker-compose.yml up -d postgres redis
```

## Stop

```bash
docker compose -f infra/docker-compose.yml down
```

Remove volumes (wipes Postgres data):

```bash
docker compose -f infra/docker-compose.yml down -v
```

## Build contexts

| Image  | Context         | Dockerfile               |
| ------ | --------------- | ------------------------ |
| API    | repository root | `apps/api/Dockerfile`    |
| Worker | repository root | `apps/worker/Dockerfile` |
| Web    | repository root | `apps/web/Dockerfile`    |

The **API** and **web** images use the repository root so `packages/extractors` and pnpm workspaces resolve correctly.
