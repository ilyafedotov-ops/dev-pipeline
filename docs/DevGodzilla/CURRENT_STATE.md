# DevGodzilla Current State

> Status: Active
> Scope: Current runtime and supported local topologies
> Source of truth: `devgodzilla/api/app.py`, `devgodzilla/api/routes/`, `frontend/next.config.mjs`, `frontend/package.json`, `docker-compose*.yml`, `nginx*.conf`, `scripts/run-local-dev.sh`, `windmill/`
> Last updated: 2026-04-20

This document describes what is implemented in this repository today.

## Canonical Documentation

- Runtime truth: `docs/DevGodzilla/CURRENT_STATE.md`
- Architecture boundaries: `docs/DevGodzilla/ARCHITECTURE.md`
- API architecture: `docs/DevGodzilla/API-ARCHITECTURE.md`
- API route reference: `docs/DevGodzilla/API-REFERENCE.md`
- Backend lifecycle flows: `docs/DevGodzilla/BACKEND-FLOWS.md`
- State semantics: `docs/DevGodzilla/STATE-MODELS.md`
- Backend subsystem ownership: `docs/DevGodzilla/SUBSYSTEMS.md`
- Operations and observability: `docs/DevGodzilla/OPERATIONS-OBSERVABILITY.md`
- Frontend architecture: `docs/DevGodzilla/FRONTEND-ARCHITECTURE.md`
- Frontend workspaces: `docs/DevGodzilla/FRONTEND-WORKSPACES.md`
- Frontend data layer: `docs/DevGodzilla/FRONTEND-API-CONTRACTS.md`
- Frontend component taxonomy: `docs/DevGodzilla/FRONTEND-COMPONENT-SYSTEM.md`
- Windmill integration and assets: `docs/DevGodzilla/WINDMILL-WORKFLOWS.md`
- Windmill flow contracts: `docs/DevGodzilla/WINDMILL-CONTRACTS.md`
- Windmill operations: `docs/DevGodzilla/WINDMILL-OPERATIONS.md`
- Frontend behavior test map: `docs/DevGodzilla/FRONTEND-TEST-MAP.md`
- Documentation maintenance: `docs/DevGodzilla/DOCS-MAINTENANCE.md`
- Historical material: `docs/legacy/README.md`

## Supported Local Topologies

### Full Docker stack

Default repo startup uses:

- `docker-compose.yml`
- `nginx.devgodzilla.conf`

This topology runs nginx, backend, frontend, Windmill, workers, Postgres, Redis, and LSP in containers.

Convenience entrypoints:

- `docker compose up --build -d`
- `scripts/run-local-dev.sh up`

`docker-compose.local.yml` is a closely related full-stack variant that swaps some image/build choices but keeps the same containerized routing model.

### Host-backed / hybrid proxy topology

The repo also contains a host-proxy topology defined by:

- `docker-compose.devgodzilla.yml`
- `nginx.local.conf`

That setup keeps nginx, Windmill, workers, Postgres, Redis, and LSP in Docker while proxying backend and frontend traffic to host processes on `:8000` and `:3000`.

Important implementation detail:

- `scripts/run-local-dev.sh backend ...` and `scripts/run-local-dev.sh frontend ...` do start host processes.
- `scripts/run-local-dev.sh up` and `scripts/run-local-dev.sh dev` currently use `docker-compose.yml`, not `docker-compose.devgodzilla.yml`.

## Frontend

The primary console is the Next.js app in `frontend/`.

Current frontend facts:

- Next.js 16, React 19, TypeScript
- `basePath: "/console"` in `frontend/next.config.mjs`
- Browser API calls use `/api/v1/*` and rely on Next.js rewrites or nginx routing
- Package manager is `pnpm`
- Test surface includes Vitest and Playwright smoke coverage

Current page groups include:

- `/console/projects` and `/console/projects/[id]`
- project-scoped workflows such as `/console/projects/[id]/branches`, `/constitution`, `/design-solution`, `/execution`, `/generate-specs`, `/implement-feature`, `/onboarding`, `/policy`, `/protocols`, and `/sprint-board`
- `/console/protocols` and `/console/protocols/[id]`
- protocol drill-down pages such as `/console/protocols/[id]/steps`, `/runs`, `/events`, `/spec`, `/policy`, and `/clarifications`
- `/console/specifications` and `/console/specifications/[id]`
- `/console/steps`, `/console/runs`, `/console/sprints`
- `/console/execution` and `/console/executions`
- `/console/ops/*`
- `/console/policy-packs/*`
- `/console/templates`
- `/console/agents`
- `/console/profile`, `/console/settings`, `/console/login`
- `/console/windmill/*`

Windmill UI remains available at `/`.

## API Surface

FastAPI entrypoint: `devgodzilla/api/app.py`.

Current router mounting model:

1. Each main router is mounted under `/api/v1` as the canonical API.
2. The same routers are mounted again at the root for backward compatibility.

Current implemented route groups:

- Health: `/health`, `/health/live`, `/health/ready`, `/health/agents`
- Core lifecycle: `/projects`, `/protocols`, `/steps`, `/agents`, `/clarifications`
- SpecKit and specs: `/speckit/*`, `/projects/{id}/speckit/*`, `/specifications*`
- Project onboarding and discovery: `/projects/{id}/actions/onboard`, `/projects/{id}/onboarding`, `/projects/{id}/discovery/actions/retry`, `/projects/{id}/discovery/logs`
- Agile execution: `/sprints*`, `/tasks*`
- Governance and quality: `/policy_packs*`, `/quality*`, project policy endpoints
- Brownfield and template flows: `/projects/{id}/brownfield/run`, `/projects/{id}/task-cycle`, `/work-items/*`, `/templates*`
- Operations: `/events*`, `/logs*`, `/metrics*`, `/queues*`, `/cli-executions*`, `/runs*`
- Windmill passthrough and maintenance: `/flows*`, `/jobs*`, `/reconciliation*`
- Identity: `/auth/*`, `/users/*`, `/profile`
- Webhooks and sockets: `/webhooks/*`, `/ws/events`

Use `GET /openapi.json` for the exact request and response contracts.

Current SpecKit API behavior worth calling out explicitly:

- compatibility routes under `/speckit/*` delegate to the project-scoped `/projects/{id}/speckit/*` handlers
- long-running AI-backed SpecKit routes can return `202 Accepted` when they defer work to background execution
- `POST /speckit/specify` currently uses a 15-second synchronous window before background fallback
- failed SpecKit agent runs now persist `SpecRun` state as `failed` rather than leaving runs stuck in transitional statuses
- project-scoped `specify` emits both DB events and structured route-level logs for invocation, resolution, completion, and failure paths

## Planning and Execution Model

Current planning is protocol-file driven:

1. A protocol run exists in the DB.
2. Planning reads protocol step artifacts from the project workspace, including `.protocols/<protocol_name>/step-*.md`.
3. `StepRun` records are materialized from those protocol files or SpecKit-generated sources.

If step files are missing and auto-generation is enabled, the system can generate protocol files before planning proceeds.

Execution artifacts are written under the project worktree, for example:

- `.protocols/<protocol_name>/.devgodzilla/steps/<step_run_id>/artifacts/*`

QA can run automatically after successful execution and can also be re-triggered through step endpoints.

## SpecKit and Discovery Artifacts

SpecKit-style artifacts are generated inside `.specify/` through DevGodzilla services and prompts; the current implementation does not depend on an external `specify` binary.

Discovery output still preserves some legacy `tasksgodzilla/` artifact names for compatibility with downstream tooling, for example:

- `tasksgodzilla/ARCHITECTURE.md`
- `tasksgodzilla/API_REFERENCE.md`
- `tasksgodzilla/CI_NOTES.md`

These are generated outputs, not the active application package.

## Windmill Integration Model

Windmill scripts in this repo are thin API adapters. The supported pattern is:

- Windmill script -> helper in `windmill/scripts/devgodzilla/_api.py` -> DevGodzilla API

Repository asset locations:

- Scripts: `windmill/scripts/devgodzilla/`
- Flows: `windmill/flows/devgodzilla/`
- Apps: `windmill/apps/devgodzilla/`
- Resources: `windmill/resources/devgodzilla/`

Common local bootstrap path:

1. Start a compose topology.
2. Ensure backend and frontend are reachable in the chosen routing mode.
3. Run `scripts/run-local-dev.sh import`.

## Active Defaults and Configuration

Current agent defaults come from `devgodzilla/config/agents.yaml`.

Notable current defaults:

- default code generation / planning / QA / discovery engine: `opencode`
- current configured `opencode` default model: `zai-coding-plan/glm-5`
- current configured `codex` default model: `gpt-4.1`

Windmill support is considered enabled when `DEVGODZILLA_WINDMILL_URL` and `DEVGODZILLA_WINDMILL_TOKEN` are both configured.
