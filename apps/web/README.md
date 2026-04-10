# Axiom web

Next.js frontend for operators and customers.

## Run locally

From the repository root (after `pnpm install`):

```bash
pnpm dev:web
```

Open [http://localhost:3000](http://localhost:3000). The UI uses a **dashboard layout** (sidebar + header) with routes: `/` (overview), `/jobs`, `/sources`, `/settings`.

## Docker (production image)

Build context must be the **repository root** (monorepo):

```bash
docker build -f apps/web/Dockerfile -t axiom-web .
```

Or use the full stack in [`infra/docker-compose.yml`](../../infra/docker-compose.yml).

## Lint & typecheck

```bash
pnpm --filter @axiom/web lint
pnpm --filter @axiom/web typecheck
```
