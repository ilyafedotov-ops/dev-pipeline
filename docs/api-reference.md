# TasksGodzilla Orchestrator API Reference (alpha)

HTTP API for managing projects, protocol runs, steps, events, queues, and CI/webhook signals. Default base: `http://localhost:8011` (compose; use 8010 for direct local runs).

- Auth: set `TASKSGODZILLA_API_TOKEN` in the API env and send `Authorization: Bearer <token>`. If unset, auth is skipped.
- Per-project token (optional): `X-Project-Token: <project secrets.api_token>`.
- Content type: `application/json` for all JSON bodies. Responses use standard HTTP codes (400/401/404/409 on validation/auth/state conflicts).

## Status enums and models
- ProtocolRun.status: `pending`, `planning`, `planned`, `running`, `paused`, `blocked`, `failed`, `cancelled`, `completed`.
- StepRun.status: `pending`, `running`, `needs_qa`, `completed`, `failed`, `cancelled`, `blocked`.
- StepRun.policy/runtime_state: arbitrary JSON from CodeMachine modules (loop/trigger metadata, inline trigger depth, loop_counts, etc.).

## Health & metrics
- `GET /health` → `{"status": "ok"|"degraded"}`.
- `GET /metrics` → Prometheus text format.

## Projects
- `POST /projects`
  - Body: `{ "name": str, "git_url": str, "base_branch": "main", "ci_provider": str|null, "default_models": obj|null, "secrets": obj|null, "local_path": str|null }`
  - Response: Project object with `id`, timestamps.
  - Behavior: persists `local_path` when provided so future jobs resolve the repo without recomputing; falls back to cloning under `TASKSGODZILLA_PROJECTS_ROOT` (default `projects/<project_id>/<repo_name>`) when missing.
  - Side effects: enqueues `project_setup_job` protocol run for onboarding progress visibility and onboarding clarifications.
- `GET /projects` → list of projects.
- `GET /projects/{id}` → project (401 if project token required and missing).
- `GET /projects/{id}/onboarding` → onboarding summary (status, workspace, stages, recent events) for `setup-{id}`.
- `GET /projects/{id}/branches`
  - Response: `{ "branches": [str] }`
  - Behavior: resolves repo via stored `local_path` or `git_url` (defaulting to `projects/<project_id>/<repo_name>`); clones when allowed; records an event.
- `POST /projects/{id}/branches/{branch:path}/delete`
  - Body: `{ "confirm": true }` (required)
  - Behavior: deletes the remote branch on origin, records an event; 409 when the repo is unavailable locally.

Event visibility
- Onboarding emits `setup_discovery_*` events (started/skipped/completed/warning) around Codex repo discovery so console/TUI/CLI can show discovery progress per project.

## CodeMachine import
- `POST /projects/{id}/codemachine/import`
  - Body: `{ "protocol_name": str, "workspace_path": str, "base_branch": "main", "description": str|null, "enqueue": bool }`
  - Response:
    - `enqueue=true`: `{ protocol_run: ProtocolRun, job: {job_id,...}, message }` after enqueuing `codemachine_import_job`.
    - `enqueue=false` (default): `{ protocol_run: ProtocolRun, job: null, message }` after immediate import.
  - Behavior: parses `.codemachine/config/*.js` + `template.json`, persists `template_config`/`template_source`, and creates StepRuns for main agents with module policies attached.

## Protocol runs
- `POST /projects/{id}/protocols`
  - Body: `{ "protocol_name": str, "status": "pending"|..., "base_branch": "main", "worktree_path": str|null, "protocol_root": str|null, "description": str|null, "template_config": obj|null, "template_source": obj|null }`
  - Response: ProtocolRun object.
- `GET /projects/{id}/protocols` → list protocol runs for project.
- `GET /protocols/{id}` → protocol run.

### Protocol actions
All return `{ "message": str, "job": obj|null }` unless noted.
- `POST /protocols/{id}/actions/start` → enqueues `plan_protocol_job` (409 if not pending/planned/paused).
- `POST /protocols/{id}/actions/pause` / `resume` / `cancel` → updates status, cancels pending steps on cancel.
- `POST /protocols/{id}/actions/run_next_step` → moves first pending/blocked/failed step to running and enqueues `execute_step_job`.
- `POST /protocols/{id}/actions/retry_latest` → retries latest failed/blocked step.
- `POST /protocols/{id}/actions/open_pr` → enqueues `open_pr_job`.
Status conflicts return 409 (e.g., starting an already-running protocol).

## Steps
- `POST /protocols/{id}/steps`
  - Body: `{ "step_index": int>=0, "step_name": str, "step_type": str, "status": "pending"|..., "model": str|null, "summary": str|null, "engine_id": str|null, "policy": obj|[obj]|null }`
  - Creates a StepRun (no job enqueued).
- `GET /protocols/{id}/steps` → list StepRuns.
- `GET /steps/{id}` → StepRun.

### Step actions
- `POST /steps/{id}/actions/run` → sets to running, enqueues `execute_step_job`.
- `POST /steps/{id}/actions/run_qa` → sets to `needs_qa`, enqueues `run_quality_job`.
- `POST /steps/{id}/actions/approve` → marks completed, may complete protocol.

## Events & queues
- `GET /protocols/{id}/events` → events for a protocol.
- `GET /events?project_id=<id>&limit=<int>` → recent events (default limit 50).
- `GET /queues` → queue stats (per queue).
- `GET /queues/jobs?status=queued|started|failed|finished` → jobs snapshot with payload/metadata.
  - Jobs include `job_id`, `job_type`, `payload`, `status`, timestamps, and error/meta where present.

## Webhooks & CI callbacks
- `POST /webhooks/github?protocol_run_id=<optional>`
  - Headers: `X-GitHub-Event`, optional `X-Hub-Signature-256` when `TASKSGODZILLA_WEBHOOK_TOKEN` set.
  - Body: standard GitHub webhook payload. Maps by branch (or `protocol_run_id` query) to update step/protocol status, enqueue QA on success when `TASKSGODZILLA_AUTO_QA_ON_CI`=true, mark protocol completed on PR merge.
- `POST /webhooks/gitlab?protocol_run_id=<optional>`
  - Headers: `X-Gitlab-Event`, token via `X-Gitlab-Token` or `X-TasksGodzilla-Webhook-Token`, optional HMAC `X-Gitlab-Signature-256`.
  - Similar mapping and QA/autocomplete behavior to GitHub handler.
- `scripts/ci/report.sh success|failure` can call these endpoints from CI with `TASKSGODZILLA_API_BASE`, `TASKSGODZILLA_API_TOKEN`, `TASKSGODZILLA_WEBHOOK_TOKEN`, `TASKSGODZILLA_PROTOCOL_RUN_ID` for explicit mapping.

## Queue/runtime notes
- Backend: Redis/RQ; when `TASKSGODZILLA_REDIS_URL=fakeredis://`, the API starts a background RQ worker thread for inline job processing.
- Jobs: `project_setup_job`, `plan_protocol_job`, `execute_step_job`, `run_quality_job`, `open_pr_job`, `codemachine_import_job`.
- CodeMachine policies: loop/trigger policies on steps may reset statuses or inline-trigger other steps (depth-limited) with events and `runtime_state` recorded.
- Token budgets: `TASKSGODZILLA_MAX_TOKENS_PER_STEP` / `TASKSGODZILLA_MAX_TOKENS_PER_PROTOCOL` with mode `TASKSGODZILLA_TOKEN_BUDGET_MODE=strict|warn|off`; overruns raise (strict) or log (warn).

## Curl examples

Create project:
```bash
curl -X POST http://localhost:8011/projects \
  -H "Authorization: Bearer $TASKSGODZILLA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"demo","git_url":"/path/to/repo","base_branch":"main"}'
```

Start planning a protocol:
```bash
curl -X POST http://localhost:8011/protocols/1/actions/start \
  -H "Authorization: Bearer $TASKSGODZILLA_API_TOKEN"
```

Run QA for a step:
```bash
curl -X POST http://localhost:8011/steps/10/actions/run_qa \
  -H "Authorization: Bearer $TASKSGODZILLA_API_TOKEN"
```

List queue jobs:
```bash
curl -X GET "http://localhost:8011/queues/jobs?status=queued" \
  -H "Authorization: Bearer $TASKSGODZILLA_API_TOKEN"
```
