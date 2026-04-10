# axiom-compliance

Shared scraping policy layer used by the API and Celery worker:

- **Blocklist / allowlist** — hostname suffix matching (`COMPLIANCE_DOMAIN_BLOCKLIST`, `COMPLIANCE_DOMAIN_ALLOWLIST`).
- **robots.txt** — `urllib.robotparser` with HTTP fetch (cached per host).
- **Per-domain rate limiting** — Redis fixed-window counter (`REDIS_URL` / `COMPLIANCE_REDIS_URL`).
- **Delay + jitter** — sleep before origin fetch (`COMPLIANCE_REQUEST_DELAY_*`).
- **Audit logging** — structured logs on logger `axiom.compliance.audit` (JSON-friendly `extra` fields).

See environment variables in `axiom_compliance.config.ComplianceSettings.from_env`.
