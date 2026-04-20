# DevGodzilla Backend API Reference

> Status: Active
> Scope: Contributor-facing REST, SSE, WebSocket, and auth contracts implemented by the current backend
> Source of truth: `devgodzilla/api/app.py`, `devgodzilla/api/routes/*.py`, `devgodzilla/api/schemas.py`, `devgodzilla/models/domain.py`, backend API tests under `tests/`
> Last updated: 2026-04-20

## Read This First

- Canonical HTTP paths are mounted under `/api/v1`.
- The same routers are also mounted at the root for backward compatibility. Those root routes are still live but should be treated as deprecated aliases.
- Exact request and response schema details live in the route modules and `GET /openapi.json`.
- Runtime status strings come from DB/domain models more often than from the narrower request enums in `api/schemas.py`. Document and test against the domain values, not legacy assumptions.

## Authentication Model

- `GET /health`, `GET /health/live`, `GET /health/ready`, `GET /health/agents` are public.
- Most API routers use `require_api_token`. If `DEVGODZILLA_API_TOKEN` is unset, those routes are effectively open; if it is set, callers may authenticate with:
  - `Authorization: Bearer <token>`
  - `X-DevGodzilla-Token: <token>`
  - `?token=<token>` for stream-style consumers
- `/metrics` and `/metrics/summary` are mounted without the API-token dependency.
- `/webhooks/*` use `require_webhook_token`. GitHub/GitLab webhook signature headers are accepted when a webhook token is configured.
- `/auth/*` is JWT-based and self-contained.
- `/users/*` uses JWT user auth dependencies rather than the API token.
- `/ws/events` is mounted without auth at the FastAPI layer.

## Route Families

### Projects

- `POST /projects`, `GET /projects`, `GET /projects/{id}`, `PUT /projects/{id}`, `DELETE /projects/{id}`, plus archive/unarchive actions.
- Project creation/update masks `github_token` from responses and persists it in project secrets. Tests cover this masking contract.
- Onboarding entrypoints are `POST /projects/{id}/actions/onboard` and the alias `POST /projects/{id}/onboarding/actions/start`.
- Onboarding tries a synchronous path first and falls back to `202 Accepted` background work when it cannot finish quickly; callers then poll `GET /projects/{id}/onboarding`.
- Onboarding can also run repository discovery and surface discovery state through:
  - `POST /projects/{id}/discovery/actions/retry`
  - `GET /projects/{id}/discovery/logs`
- Project-scope convenience routes expose related resources and repo state:
  - `/projects/{id}/protocols`
  - `/projects/{id}/sprints`
  - `/projects/{id}/tasks`
  - `/projects/{id}/policy`, `/policy/effective`, `/policy/findings`
  - `/projects/{id}/branches`, branch create/delete actions
  - `/projects/{id}/clarifications`
  - `/projects/{id}/commits`, `/pulls`, `/worktrees`

### Protocols

- Creation paths:
  - `POST /projects/{project_id}/protocols`
  - `POST /protocols`
  - `POST /protocols/from-spec`
- Listing and detail:
  - `GET /protocols`
  - `GET /protocols/{id}`
  - `GET /protocols/{id}/steps`
  - `GET /protocols/{id}/runs`
  - `GET /protocols/{id}/events`
  - `GET /protocols/{id}/spec`
  - `GET /protocols/{id}/flow`
  - `POST /protocols/{id}/flow`
  - `GET /protocols/{id}/artifacts`
  - `GET /protocols/{id}/quality`
  - `GET /protocols/{id}/policy/findings`
  - `GET /protocols/{id}/policy/snapshot`
  - `GET /protocols/{id}/feedback`
  - `GET /protocols/{id}/clarifications`
  - `GET /protocols/{id}/sprint`
- Control actions:
  - `POST /protocols/{id}/actions/start`
  - `POST /protocols/{id}/actions/run_next_step`
  - `POST /protocols/{id}/actions/pause`
  - `POST /protocols/{id}/actions/resume`
  - `POST /protocols/{id}/actions/cancel`
  - `POST /protocols/{id}/actions/retry_latest`
  - `POST /protocols/{id}/actions/open_pr`
  - `POST /protocols/{id}/actions/create-sprint`
  - `POST /protocols/{id}/actions/sync-to-sprint`
- `GET /protocols/{id}/next-step` is preview-only. Tests assert it does not execute the step.

### Steps

- `GET /steps`, `GET /steps/{id}`, `GET /steps/{id}/runs`
- `POST /steps/{id}/actions/assign_agent`
- `POST /steps/{id}/actions/execute`
- `POST /steps/{id}/actions/qa`
- `GET /steps/{id}/quality`
- `GET /steps/{id}/policy/findings`
- Artifact and feedback surfaces:
  - `GET /steps/{id}/artifacts`
  - `GET /steps/{id}/artifacts/{artifact_id}/content`
  - `GET /steps/{id}/artifacts/{artifact_id}/download`
  - `GET /steps/{id}/feedback`
  - `POST /steps/{id}/feedback`
  - `POST /steps/{id}/retry`
  - `POST /steps/{id}/escalate`
- Step execution writes best-effort artifacts into the protocol runtime tree, including logs, execution metadata, and a git diff when available.

### SpecKit and Specifications

- Project-scoped SpecKit routes are the implementation path:
  - `/projects/{id}/speckit/init`
  - `/projects/{id}/speckit/constitution`
  - `/projects/{id}/speckit/constitution/sync`
  - `/projects/{id}/speckit/specify`
  - `/projects/{id}/speckit/plan`
  - `/projects/{id}/speckit/tasks`
  - `/projects/{id}/speckit/clarify`
  - `/projects/{id}/speckit/checklist`
  - `/projects/{id}/speckit/analyze`
  - `/projects/{id}/speckit/implement`
- Compatibility wrappers live under `/speckit/*` and reuse the project-scoped handlers.
- Long-running compatibility routes can return `202 Accepted` with an `AsyncAcceptedResponse`; the caller should poll `/speckit/status/{project_id}` or inspect spec-run records.
- Spec-run maintenance routes:
  - `POST /speckit/spec-runs/{spec_run_id}/cleanup`
  - `POST /speckit/spec-runs/{spec_run_id}/stop`
- Cross-project spec inventory:
  - `GET /specifications`
  - `GET /specifications/{spec_id}`
  - `GET /specifications/{spec_id}/content`
  - `POST /specifications/{spec_id}/link-sprint`

### Brownfield / Task Cycle

- `GET /projects/{project_id}/task-cycle`
- `POST /projects/{project_id}/brownfield/run`
  - Required request field: `feature_request`
  - Supported `output_mode` values: `task_cycle`, `tasks_only`, `tasks_to_sprint`, `protocol`, `protocol_to_sprint`
  - Optional protocol controls: `feature_name`, `protocol_name`, `branch`, `overwrite_protocol`
  - Optional sprint controls: `sprint_id`, `sprint_name`, `auto_sync_sprint`, `overwrite_existing_tasks`
  - `200 OK` returns `BrownfieldRunOut` with artifact paths plus mode-specific payload such as `protocol`, `sprint`, `tasks_synced`, `task_ids`, `work_items`, and `next_work_item_id`
  - `202 Accepted` returns the same envelope with `warnings` and a `poll_hint`; callers should follow that hint because polling differs by mode
- Work-item actions under `/work-items/{work_item_id}`:
  - detail
  - artifact content
  - build-context
  - implement
  - review
  - qa
  - mark-pr-ready

### Agile Execution

- Sprints: create/get/list/update/delete plus:
  - `/sprints/{id}/tasks`
  - `/sprints/{id}/metrics`
  - `/sprints/{id}/velocity`
  - `actions/link-protocol`
  - `actions/sync-from-protocol`
  - `actions/complete`
  - `actions/import-tasks`
- Tasks: create/get/list/update/patch/delete under `/tasks`.

### Quality

- `GET /quality/dashboard`
- Step- and protocol-scoped quality views are also available under:
  - `/steps/{id}/quality`
  - `/protocols/{id}/quality`

### Agents, Templates, Policy, Profile

- Agents cover inventory, health, metrics, tests, defaults, prompt templates, assignments, and per-project overrides.
- Templates support list/get/create/patch/delete, render, duplicate, and export.
- Policy packs expose list/get/create-or-update under `/policy_packs`.
- `/profile`, `/auth/*`, and `/users/*` cover admin JWT login plus user-profile maintenance.

### Operations and Runtime Introspection

- Runs:
  - `GET /runs`
  - `GET /runs/{run_id}`
  - `GET /runs/{run_id}/logs`
  - `GET /runs/{run_id}/logs/stream`
  - `GET /runs/{run_id}/artifacts`
  - `GET /runs/{run_id}/artifacts/{artifact_id}/content`
- CLI executions:
  - list, active, detail
  - log fetch and SSE log stream
  - cancel
- Events and logs:
  - `GET /events`
  - `GET /events/stream`
  - `GET /events/recent`
  - `GET /logs/stream`
  - `GET /logs/recent`
- Queues:
  - `GET /queues`
  - `GET /queues/stats`
  - `GET /queues/jobs`
- Reconciliation:
  - `POST /reconciliation/run`
  - `GET /reconciliation/status`
  - `GET /reconciliation/protocols/{protocol_run_id}`
  - `GET /reconciliation/steps/{step_run_id}`
- Windmill passthrough:
  - `/flows`
  - `/flows/{flow_path}/runs`
  - `/jobs`
  - `/jobs/{job_id}`
  - `/jobs/{job_id}/logs`

## Streaming Contracts

- SSE event streams support `Last-Event-ID` and `since_id`.
- `/events` emits named SSE events using the persisted `event_type`.
- `/events/stream` emits default browser `message` events instead.
- Run logs, CLI execution logs, and app logs emit periodic heartbeat frames when idle.
- `/ws/events` is a WebSocket subscription channel for protocol/project-scoped event fanout.

## Health and Metrics

- Health:
  - `/health`
  - `/health/live`
  - `/health/ready`
  - `/health/agents`
- Metrics:
  - `/metrics/summary` returns JSON for the frontend and marks responses as `degraded` when partial DB queries fail.
  - `/metrics` returns Prometheus text when `prometheus_client` is available; the route still exists with stubs when it is not.

## Contributor Notes

- Add new routes in a route module and register them through `devgodzilla/api/app.py`; the dual-mount behavior is centralized there.
- When adding new status values, update `devgodzilla/models/domain.py`, any relevant response shaping logic, and tests before editing docs.
- For behavior changes, prefer the project-scoped SpecKit routes as the primary contract and keep compatibility wrappers thin.
