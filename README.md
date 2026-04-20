# DevGodzilla

DevGodzilla is an AI-assisted development orchestration platform built from a FastAPI backend, a Next.js console, and Windmill automation assets. This repository contains both the application code and the local infrastructure needed to run it.

## Documentation Source of Truth

- `docs/DevGodzilla/CURRENT_STATE.md`: what is implemented and how the local runtime is wired today
- `docs/DevGodzilla/ARCHITECTURE.md`: system boundaries and current architecture
- `docs/DevGodzilla/API-ARCHITECTURE.md`: API mounting, auth model, and route domains
- `docs/DevGodzilla/API-REFERENCE.md`: human-oriented backend route reference
- `docs/DevGodzilla/BACKEND-FLOWS.md`: onboarding, SpecKit, protocol, QA, and sprint lifecycles
- `docs/DevGodzilla/STATE-MODELS.md`: protocol, step, spec-run, and onboarding state semantics
- `docs/DevGodzilla/SUBSYSTEMS.md`: backend service-domain ownership
- `docs/DevGodzilla/OPERATIONS-OBSERVABILITY.md`: health, logs, events, runs, queues, and reconciliation
- `docs/DevGodzilla/FRONTEND-ARCHITECTURE.md`: console architecture and route groups
- `docs/DevGodzilla/FRONTEND-WORKSPACES.md`: project and protocol workspace model
- `docs/DevGodzilla/FRONTEND-API-CONTRACTS.md`: client, hooks, query keys, and websocket invalidation
- `docs/DevGodzilla/FRONTEND-COMPONENT-SYSTEM.md`: component taxonomy and extension points
- `docs/DevGodzilla/WINDMILL-WORKFLOWS.md`: Windmill assets, flows, and integration model
- `docs/DevGodzilla/WINDMILL-CONTRACTS.md`: per-flow purpose and script-chain contracts
- `docs/DevGodzilla/WINDMILL-OPERATIONS.md`: Windmill bootstrap and troubleshooting runbook
- `docs/DevGodzilla/FRONTEND-TEST-MAP.md`: UI behavior mapped to tests
- `docs/DevGodzilla/DOCS-MAINTENANCE.md`: canonical-doc ownership and drift checks
- `docs/ci.md`: CI wrappers, local parity, and live harness notes

Historical material lives under `docs/legacy/` and should not be treated as authoritative.

## Repository Layout

| Directory | Purpose |
|-----------|---------|
| `devgodzilla/` | FastAPI app, services, engine adapters, DB layer, Windmill client |
| `frontend/` | Next.js 16 console mounted at `/console` |
| `windmill/` | Windmill scripts, flows, apps, resources, import manifest |
| `scripts/` | Local-dev helpers, operational CLIs, CI wrappers |
| `tests/` | Python `pytest` suite plus `tests/e2e/` harness support |
| `docs/` | Active documentation and archived history |
| `templates/` | Reusable project and workflow templates |
| `schemas/` | JSON schema contracts |
| `projects/` | Local project workspaces and generated protocol artifacts |
| `runs/` | Local diagnostics, logs, and harness output |
| `Origins/` | Vendored upstream sources; avoid editing by default |

## Runtime Modes

The repo currently contains two distinct local topologies.

### 1. Full Docker stack

This is the simplest way to boot the whole platform.

```bash
docker compose up --build -d
# or
scripts/run-local-dev.sh up
```

This mode uses:

- `docker-compose.yml`
- `nginx.devgodzilla.conf`

In this topology, nginx proxies to containerized backend and frontend services.

### 2. Host-backed / hybrid routing

The repo also includes assets that proxy nginx to backend/frontend processes running on the host:

- `docker-compose.devgodzilla.yml`
- `nginx.local.conf`

Use that topology when you explicitly want Docker-hosted infra with host-run backend/frontend:

```bash
docker compose -f docker-compose.devgodzilla.yml up -d
scripts/run-local-dev.sh backend start
scripts/run-local-dev.sh frontend start
```

`scripts/run-local-dev.sh dev` also starts host backend/frontend processes after bringing up the default compose stack, which is useful for local debugging and hot reload.

## Quick Start

### Prerequisites

- Docker with Compose support
- Python 3.12 for local backend development
- Node.js 20+ and `pnpm` for local frontend development

### Start the platform

```bash
scripts/ci/bootstrap.sh
docker compose up --build -d
scripts/run-local-dev.sh import
```

Primary interfaces:

- Console: `http://localhost:8080/console`
- API docs: `http://localhost:8080/docs`
- Windmill UI: `http://localhost:8080/`

### Host development commands

```bash
scripts/run-local-dev.sh backend start
scripts/run-local-dev.sh frontend start

# or run the helper that starts compose + host dev servers
scripts/run-local-dev.sh dev
```

Useful ops commands:

```bash
scripts/run-local-dev.sh status
scripts/run-local-dev.sh logs
scripts/pipeline-ctl.sh status
scripts/pipeline-ctl.sh health --exit-code
scripts/pipeline-ctl.sh watch
```

## Development Commands

### Backend

```bash
scripts/ci/bootstrap.sh
scripts/ci/lint.sh
scripts/ci/typecheck.sh
scripts/ci/test.sh
scripts/ci/build.sh
```

`scripts/ci/test.sh` runs the deterministic backend unit slice by default and only runs real-agent E2E coverage when `DEVGODZILLA_RUN_E2E_REAL_AGENT=1`.

### Frontend

```bash
cd frontend
pnpm install
pnpm typecheck
pnpm lint
pnpm test:run
pnpm test:e2e:smoke
```

Or use the wrapper from the repo root:

```bash
scripts/ci/test_frontend.sh
```

## API Surface

FastAPI lives in `devgodzilla/api/app.py`.

Routers are mounted twice:

- canonical versioned routes under `/api/v1/*`
- backward-compatible root routes such as `/projects` and `/protocols`

High-level domains:

| Domain | Examples |
|--------|----------|
| Core lifecycle | `/projects`, `/protocols`, `/steps`, `/agents`, `/clarifications` |
| SpecKit and specs | `/speckit/*`, `/projects/{id}/speckit/*`, `/specifications*` |
| Agile execution | `/sprints*`, `/tasks*` |
| Governance and quality | `/policy_packs*`, `/quality*`, project policy endpoints |
| Operations | `/events*`, `/logs*`, `/metrics*`, `/queues*`, `/runs*`, `/cli-executions*` |
| Windmill passthrough | `/flows*`, `/jobs*`, `/reconciliation*` |
| Auth and identity | `/auth/*`, `/users/*`, `/profile` |
| Webhooks and streaming | `/webhooks/*`, `/ws/events` |

Use `GET /openapi.json` for the exact contract.

## Frontend Console

The console under `frontend/` is a Next.js App Router application with `basePath: "/console"`.

Current route groups include:

- `/console/projects` and `/console/projects/[id]`
- `/console/protocols` and `/console/protocols/[id]`
- `/console/specifications` and `/console/specifications/[id]`
- `/console/steps`, `/console/runs`, `/console/sprints`
- `/console/ops`, `/console/ops/events`, `/console/ops/logs`, `/console/ops/metrics`, `/console/ops/queues`
- `/console/policy-packs`, `/console/templates`, `/console/agents`, `/console/profile`, `/console/settings`
- `/console/windmill`, `/console/windmill/flows`, `/console/windmill/jobs`, `/console/windmill/reconciliation`

## Windmill Integration

Windmill is used as workflow runtime and operator-facing UI. The repo’s Windmill scripts are thin adapters that call the DevGodzilla API rather than importing backend internals into the worker runtime.

Key asset locations:

- `windmill/scripts/devgodzilla/`
- `windmill/flows/devgodzilla/`
- `windmill/apps/devgodzilla/`
- `windmill/resources/devgodzilla/`

Import assets into a local Windmill workspace with:

```bash
scripts/run-local-dev.sh import
```

## Configuration Notes

Common environment variables:

| Variable | Purpose |
|----------|---------|
| `DEVGODZILLA_DB_URL` | Backend database URL |
| `DEVGODZILLA_API_TOKEN` | Bearer token for protected API routes |
| `DEVGODZILLA_WEBHOOK_TOKEN` | Shared secret for webhook endpoints |
| `DEVGODZILLA_WINDMILL_URL` | Windmill base URL |
| `DEVGODZILLA_WINDMILL_TOKEN` | Windmill API token |
| `DEVGODZILLA_WINDMILL_WORKSPACE` | Windmill workspace name |
| `DEVGODZILLA_OPENCODE_MODEL` / `DEVGODZILLA_CODEX_MODEL` / `DEVGODZILLA_CLAUDE_MODEL` | Optional engine model overrides |
| `WINDMILL_JOB_TIMEOUT_SECONDS` | Windmill job timeout used by local compose files |

Current default CLI agent configuration is defined in `devgodzilla/config/agents.yaml`.
