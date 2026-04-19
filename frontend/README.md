# DevGodzilla Console

This directory contains the Next.js console for DevGodzilla. The app uses the App Router and is mounted under `/console`.

## Stack

- Next.js 16
- React 19
- TypeScript
- Tailwind CSS
- TanStack Query
- Vitest
- Playwright

## Local Development

From `frontend/`:

```bash
pnpm install
pnpm dev
```

The dev server runs on port `3000` by default.

Useful variants:

```bash
pnpm build
pnpm start
pnpm typecheck
pnpm lint
pnpm test:run
pnpm test:e2e:smoke
pnpm check
```

## API Connectivity

Current frontend routing facts:

- `basePath` is `/console`
- browser API calls target `/api/v1/*`
- `frontend/next.config.mjs` rewrites `/api/v1/:path*`
- if `NEXT_PUBLIC_API_BASE_URL` is unset, the default rewrite target is `http://localhost:8000/api/v1/:path*`

Common local setups:

- direct backend dev: run the backend on `:8000` and use the default rewrite
- nginx-backed dev: set `NEXT_PUBLIC_API_BASE_URL=http://localhost:8080/api/v1` or use the repo helper that exports `NEXT_PUBLIC_API_BASE_URL=http://localhost:8080`

## Route Surface

Current page groups under `app/` include:

- dashboard: `app/page.tsx`
- projects: `app/projects/`, `app/projects/[id]/`
- protocols: `app/protocols/`, `app/protocols/[id]/`
- specifications: `app/specifications/`, `app/specifications/[id]/`
- steps: `app/steps/`, `app/steps/[id]/`
- runs: `app/runs/`, `app/runs/[runId]/`
- sprints: `app/sprints/`
- ops: `app/ops/`, `app/ops/events/`, `app/ops/logs/`, `app/ops/metrics/`, `app/ops/queues/`
- policy packs: `app/policy-packs/`
- agents, templates, profile, settings, login
- Windmill console pages under `app/windmill/`

## Authentication

The frontend includes:

- auth context and guards under `lib/auth/`
- login UI under `app/login/`
- Next route handlers under `app/api/auth/`

Current auth-related API calls are wired against backend `/api/v1/auth/*` endpoints.

## Tests

- Unit/component tests: `pnpm test:run`
- Playwright smoke coverage: `pnpm test:e2e:smoke`

From the repo root, you can also run:

```bash
scripts/ci/test_frontend.sh
```
