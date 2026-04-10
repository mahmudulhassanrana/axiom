# Compliance model

Scraping in Axiom is gated by a **shared Python package** (`packages/compliance`, import name **`axiom_compliance`**) used by the **API** and **worker** so policy is enforced consistently for synchronous requests, queued jobs, and scheduled runs.

## Goals

- Respect **robots.txt** and configurable **allow/block lists**.
- Apply **per-domain rate limiting** and **delay + jitter** to reduce load on targets.
- Emit **structured audit** events for observability and optional persistence.

Disabling compliance is supported for local testing only (`COMPLIANCE_ENABLED=false`); production deployments should leave it **enabled**.

## Pipeline entrypoint

The main API is:

```text
run_compliance_before_fetch(url, ctx=ScrapeComplianceContext, settings=..., preverified=False) -> str
```

- Returns the **normalized hostname** used for logging and downstream steps.
- Raises **`ComplianceError`** subclasses on violation (see below).
- **`preverified`**: when `True`, skips enforcement (used when the API already ran compliance and the worker only needs correlation/audit consistency).

`ScrapeComplianceContext` carries **`user_id`**, **`organization_id`**, **`audit_correlation_id`**, **`engine`**, **`source`** (`api` vs worker), and optional **`celery_task_id`** for log correlation.

### Order of enforcement (when enabled)

1. **Domain lists** — blocklist and optional non-empty allowlist (`enforce_domain_lists`).
2. **Redis rate limit** — sliding window per host (`acquire_per_domain_slot`). Requires a Redis URL.
3. **Delay + jitter** — sleep before fetch (`sleep_delay_with_jitter`).
4. **robots.txt** — fetch/parse and assert the URL is allowed for the configured **User-Agent** (`assert_robots_allow_fetch`).

Each step emits **`log_scrape_audit`** events (`compliance.step` with `step` = `domain_lists`, `rate_limit`, `delay`, `robots`), then `compliance.passed` on success.

When **`COMPLIANCE_ENABLED`** is false, the pipeline logs `compliance.disabled` and returns the hostname without enforcement.

## Configuration (`ComplianceSettings.from_env()`)

| Variable | Purpose |
| -------- | ------- |
| `COMPLIANCE_ENABLED` | Master switch (default **true**). |
| `COMPLIANCE_USER_AGENT` | UA string for HTTP fetch, Playwright, and robots.txt checks. |
| `COMPLIANCE_DOMAIN_BLOCKLIST` | Comma-separated hostnames to block. |
| `COMPLIANCE_DOMAIN_ALLOWLIST` | If non-empty, only these hosts are allowed. |
| `COMPLIANCE_REQUEST_DELAY_SECONDS` | Base delay before fetch. |
| `COMPLIANCE_REQUEST_JITTER_SECONDS` | Random extra delay spread. |
| `COMPLIANCE_RATE_LIMIT_PER_DOMAIN` | Max requests per host per window. |
| `COMPLIANCE_RATE_LIMIT_WINDOW_SECONDS` | Window length in seconds. |
| `COMPLIANCE_REDIS_URL` or `REDIS_URL` | Redis for rate limiting (required for limiter to be meaningful). |
| `COMPLIANCE_ROBOTS_TIMEOUT_SECONDS` | Timeout when fetching robots.txt. |
| `COMPLIANCE_ROBOTS_FAIL_OPEN` | If **true**, robots fetch failures do not block (default **true**). |
| `COMPLIANCE_ROBOTS_CACHE_TTL_SECONDS` | Cache TTL for robots data. |

See also `.env.example` in the repository root.

## Exception types

| Exception | Meaning |
| --------- | ------- |
| `DomainBlockedError` | Host on blocklist. |
| `DomainNotAllowedError` | Allowlist is active and host not listed. |
| `RateLimitExceededError` | Per-domain limit exceeded (**HTTP 429** when mapped in API). |
| `RobotsTxtDisallowedError` | robots.txt disallows the URL. |
| `RobotsTxtUnavailableError` | robots.txt could not be retrieved and strict behavior applies. |
| `ComplianceError` | Base class for policy failures. |

The FastAPI helper **`compliance_http_exception`** maps **`RateLimitExceededError`** to **429** and other compliance errors to **403** unless specialized elsewhere.

## Audit logging

- **`log_scrape_audit`** writes structured logs (event name + context) for pipeline steps.
- The API and worker can additionally persist rows (e.g. scrape audit events, job logs) using the same **correlation id** so operator views align with logs.

## Principles

- **No bypass** of robots or lists in product flows: compliance runs before fetch in both API and worker paths.
- **Fail-open vs fail-closed** for robots is controlled by **`COMPLIANCE_ROBOTS_FAIL_OPEN`**; tune per risk tolerance.

## Related

- [Architecture](./architecture.md) — where compliance runs in the system.
- [API specification](./api-spec.md) — scrape and job endpoints.
