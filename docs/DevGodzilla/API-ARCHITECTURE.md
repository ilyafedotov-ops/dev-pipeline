# DevGodzilla API Architecture

> Status: Active
> Scope: Current API architecture and access model
> Source of truth: `devgodzilla/api/app.py`, `devgodzilla/api/routes/*.py`, `GET /openapi.json`
> Last updated: 2026-04-19

## Summary

DevGodzilla API is a FastAPI service that exposes project and protocol lifecycle endpoints, SpecKit flows, agile execution artifacts, governance and quality surfaces, operations telemetry, auth flows, and Windmill passthrough endpoints.

For exact schemas, payloads, and required fields, use `GET /openapi.json`.

## Request Flow

```text
Client -> nginx or Next.js rewrite -> FastAPI route -> dependency injection -> service layer -> db / windmill / filesystem / agent runtime
```

- App entrypoint: `devgodzilla/api/app.py`
- Route modules: `devgodzilla/api/routes/*.py`
- Shared dependencies: `devgodzilla/api/dependencies.py`

## Router Mounting Model

Most main routers are mounted twice:

1. `/api/v1/*`: canonical versioned API used by the frontend
2. root-level routes such as `/projects` and `/protocols`: backward-compatible legacy surface

This dual mounting is implemented in `devgodzilla/api/app.py`, not at the nginx layer.

## Authentication and Access

Current access model by route category:

- API token required for most core, orchestration, governance, ops, and Windmill-facing routes
- webhook token required for `/webhooks/*`
- `/metrics*` is intentionally mounted without the API-token dependency
- `/ws/events` is mounted without auth dependencies
- `/auth/*` handles session/JWT-oriented login flow
- `/users/*` uses its own auth dependencies rather than the global API-token dependency

## Route Domains

### Core lifecycle

- `/projects*`
- `/protocols*`
- `/steps*`
- `/agents*`
- `/clarifications*`

### SpecKit and specification flows

- `/speckit/*`
- `/projects/{project_id}/speckit/*`
- `/specifications*`
- `/brownfield*`
- `/templates*`

Current compatibility behavior:

- `/speckit/*` remains the compatibility surface
- project-scoped `/projects/{project_id}/speckit/*` handlers are the underlying implementation path reused by those compatibility routes

### Agile execution

- `/sprints*`
- `/tasks*`

### Governance and quality

- `/policy_packs*`
- project policy endpoints under `/projects/{project_id}/policy*`
- `/quality*`

### Operations and observability

- `/events*`
- `/logs*`
- `/queues*`
- `/cli-executions*`
- `/runs*`
- `/metrics*`

### Windmill and maintenance

- `/flows*`
- `/jobs*`
- `/reconciliation*`

### Identity and profile

- `/auth/*`
- `/users/*`
- `/profile`

### Webhooks and streaming

- `/webhooks/github`
- `/webhooks/gitlab`
- `/webhooks/windmill/*`
- `/ws/events`

### Health

- `/health`
- `/health/live`
- `/health/ready`
- `/health/agents`

## Naming Notes

- API paths currently use underscores for some resources, for example `/policy_packs`.
- Frontend route slugs may use hyphens, for example `/console/policy-packs`.
- This mismatch is intentional and reflected in the existing UI code.

## Streaming and Long-Running Endpoints

The current API surface includes streaming or long-poll style endpoints for operations and logs, including:

- `/events/stream`
- `/logs/stream`
- `/runs/{run_id}/logs/stream`
- `/cli-executions/{execution_id}/logs/stream`
- `/ws/events`

## SpecKit Execution Semantics

Several SpecKit endpoints are intentionally hybrid synchronous/background operations.

Current behavior:

- compatibility endpoints such as `/speckit/specify`, `/speckit/plan`, `/speckit/tasks`, `/speckit/analyze`, and `/speckit/workflow` first attempt synchronous execution
- when work does not finish inside the synchronous window, they return `202 Accepted` and continue in a FastAPI background task
- `POST /speckit/specify` currently waits up to 15 seconds before switching to background execution
- the `202` payload is an `AsyncAcceptedResponse` with a pending-style status and polling guidance
- `GET /speckit/status/{project_id}` and spec-run endpoints are the recovery and inspection surface for deferred work
- `POST /speckit/spec-runs/{spec_run_id}/stop` exists for stuck transitional runs so cleanup can proceed
- `POST /speckit/spec-runs/{spec_run_id}/cleanup` removes worktree state after the run is terminal or manually stopped

Failure-state hardening in the current implementation:

- if the underlying SpecKit agent run fails during specify, plan, tasks, checklist, or analyze, the backend records the corresponding `SpecRun` as `failed`
- the `/projects/{project_id}/speckit/specify` handler emits structured logs and DB events around invocation, project resolution, completion, and failure

## Service Layer Relationship

Routes are intentionally thin and delegate orchestration and business logic to `devgodzilla/services/`.

Primary service domains used behind the API include:

- orchestration and planning
- execution and QA
- specification and SpecKit flows
- template and reconciliation flows
- telemetry, events, and health

## Related Docs

- Runtime truth: `docs/DevGodzilla/CURRENT_STATE.md`
- System architecture: `docs/DevGodzilla/ARCHITECTURE.md`
- Windmill workflows: `docs/DevGodzilla/WINDMILL-WORKFLOWS.md`
- CI notes: `docs/ci.md`
