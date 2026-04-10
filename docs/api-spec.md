# API specification

The HTTP API is implemented with **FastAPI**. The **machine-readable contract** is the OpenAPI document served by the running service:

| Resource | URL (default local) |
| -------- | --------------------- |
| Swagger UI | `http://localhost:8000/docs` |
| ReDoc | `http://localhost:8000/redoc` |
| OpenAPI JSON | `http://localhost:8000/openapi.json` |

Use OpenAPI for client generation, contract tests, and exhaustive schema detail (field types, enums, response models). This page summarizes **routes and auth** at a high level.

## Error responses

Most errors return a JSON body (except successful binary downloads) shaped as:

```json
{
  "error": {
    "code": "unauthorized",
    "message": "Human-readable message",
    "request_id": "uuid-or-null"
  }
}
```

- **`request_id`**: Correlates logs and support; also returned as the **`X-Request-ID`** response header. Clients may send **`X-Request-ID`** on requests to propagate their own trace id.
- **`422` validation** errors additionally include **`fields`**: FastAPI/Pydantic validation error entries.
- **`ENVIRONMENT=production`** (or `AXIOM_ENV`): suppresses internal details on **500** responses and uses conservative copy for upstream failures; development mode may include more diagnostic text where safe.

### Tracing and logs

- **`X-Request-ID`**: Clients may send a value; otherwise the API generates one. It is returned on the response and included in JSON error bodies as **`request_id`**.
- **`traceparent`**: Optional [W3C Trace Context](https://www.w3.org/TR/trace-context/) header. When valid, the trace id is stored for **structured logs** (`trace_id` field in JSON log lines) and correlates with OpenTelemetry-style systems.
- **Structured logging** (`LOG_FORMAT=json`): Application logs under the `axiom_api` logger are JSON lines with `timestamp`, `level`, `logger`, `message`, and when present `request_id`, `trace_id`, and event-specific fields (for example `http_request` access events with `method`, `path`, `status_code`, `duration_ms`). See `.env.example` for `LOG_LEVEL`, `LOG_ACCESS_LOG`, and `LOG_ACCESS_SKIP_PATHS`.

## Security notes

- **Passwords** (registration / admin-created users): at least **12** characters with **uppercase**, **lowercase**, and a **digit**. Login passwords are capped at **128** characters to limit bcrypt work.
- **JWTs** include `iss` and `aud` claims (see `JWT_ISSUER`, `JWT_AUDIENCE` in `.env.example`); tokens are validated with a small clock **leeway**.
- **Production**: set `ENVIRONMENT=production`, a long random `JWT_SECRET_KEY`, and `CORS_ALLOW_ORIGINS`. OpenAPI UIs are **disabled** unless `API_DOCS_ENABLED=true`.
- **Responses** include common browser headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, etc.); optional **HSTS** via `ENABLE_HSTS` when served over HTTPS.
- **Large bodies**: requests with `Content-Length` over `MAX_REQUEST_BODY_BYTES` receive **413** before the body is read.

## Authentication

Protected routes require **one** of:

| Mechanism | How |
| --------- | --- |
| **JWT** | `Authorization: Bearer <access_token>` from `POST /auth/login` or `POST /auth/register` |
| **API key** | `X-API-Key: <raw_key>` (returned once from `POST /auth/api-keys`) |

Unauthenticated requests receive **401** with a hint to use Bearer or `X-API-Key`.

**Admin-only** routes use dependency `RequireAdmin` (user `role` must be `admin`).

## Route map

Prefix is **none** unless noted; all paths are relative to the API origin (e.g. `https://api.example.com`).

### Health and meta

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| `GET` | `/health` | No | Liveness: `{ "status": "ok" }` |
| `GET` | `/` | No | Service name and version |

### Auth (`/auth`)

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| `POST` | `/auth/register` | No | Create organization + admin user; returns JWT |
| `POST` | `/auth/login` | No | Email/password; returns JWT |
| `GET` | `/auth/me` | Yes | Current user profile |
| `POST` | `/auth/api-keys` | Yes | Create API key (secret shown once) |
| `GET` | `/auth/api-keys` | Yes | List caller’s API keys (metadata only) |
| `DELETE` | `/auth/api-keys/{key_id}` | Yes | Revoke key |

### Admin (`/admin`)

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| `GET` | `/admin/ping` | Admin | Sanity check |
| `POST` | `/admin/users` | Admin | Create user in admin’s organization |

### Scrape

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| `POST` | `/scrape` | Yes | Scrape a URL (`ScrapeRequest`: `url`, `engine`, `include_html`, `async` / `async_execution`) |

**Behavior:**

- Default **`async`** / `async_execution`: **true** → enqueue Celery task **`axiom.scrape`**, response **202** with `task_id` (`ScrapeQueuedResponse`).
- **`async=false`** → run extraction in the API process, response **200** with `ExtractedDocument`.

Compliance runs before fetch; failures map to **403** (policy) or **429** (rate limit) among others. See OpenAPI `responses` on the operation.

### Jobs (`/jobs`)

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| `GET` | `/jobs` | Yes | List jobs for org (`limit` query) |
| `POST` | `/jobs` | Yes | Create scrape job (`JobCreateRequest`: `url`, `engine`, `include_html`, `source_id`, `max_retries`) |
| `GET` | `/jobs/{job_id}` | Yes | Job detail with runs |
| `GET` | `/jobs/{job_id}/runs` | Yes | Runs for job |
| `GET` | `/jobs/{job_id}/logs` | Yes | Audit log entries linked to job (`limit`) |
| `GET` | `/jobs/runs/{run_id}` | Yes | Single run |

**POST /jobs** runs compliance before enqueueing; broker errors may return **503**.

### Exports (`/exports`)

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| `POST` | `/exports/download` | Yes | Body: `ExtractedDocument` + `format` → file download |
| `GET` | `/exports/download` | Yes | Query: `format`, `document_json` (URL-encoded JSON) |
| `GET` | `/exports/runs/{run_id}/download` | Yes | Query: `format` — export first stored extraction for run |

Formats: **`json`**, **`csv`**, **`markdown`**, **`html`** (see `ExportFormat` in code / OpenAPI).

### Schedules (`/schedules`)

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| `GET` | `/schedules` | Yes | List schedules (`include_paused`, `limit`) |
| `POST` | `/schedules` | Yes | Create cron schedule |
| `GET` | `/schedules/{schedule_id}` | Yes | Get schedule |
| `PATCH` | `/schedules/{schedule_id}` | Yes | Update (e.g. `paused`, `name`); resume may recompute `next_run_at` |
| `DELETE` | `/schedules/{schedule_id}` | Yes | Delete schedule |

Immediate one-off runs use **`POST /jobs`**, not schedules.

## CORS

The API enables CORS for **`http://localhost:3000`** (browser dev) with credentials. Production frontends should align allowed origins with deployment configuration.

## Versioning

The service exposes its version on **`GET /`** and in the OpenAPI document. Breaking API changes should be communicated via version bumps and changelog; there is no URL prefix versioning in the current app.

## Related

- [Architecture](./architecture.md)
- [Compliance model](./compliance-model.md) — behavior behind scrape and job endpoints.
- [Deployment](./deployment.md) — TLS, secrets, and scaling.
