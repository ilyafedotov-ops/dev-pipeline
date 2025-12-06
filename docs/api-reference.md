# DeksdenFlow Orchestrator API Reference (alpha)

HTTP API for managing projects, protocol runs, steps, events, queues, and CI/webhook signals. Default base: `http://localhost:8000`.

- Auth: set `DEKSDENFLOW_API_TOKEN` in the API env and send `Authorization: Bearer <token>`. If unset, auth is skipped.
- Per-project token (optional): `X-Project-Token: <project secrets.api_token>`.
- Content type: `application/json` for all JSON bodies. Responses use standard HTTP codes (400/401/404/409 on validation/auth/state conflicts).

## Status enums
- ProtocolRun: `pending`, `planning`, `planned`, `running`, `paused`, `blocked`, `failed`, `cancelled`, `completed`.
- StepRun: `pending`, `running`, `needs_qa`, `completed`, `failed`, `cancelled`, `blocked`.

## Health & metrics
- `GET /health` → `{"status": "ok"|"degraded"}`.
- `GET /metrics` → Prometheus text format.

## Projects
- `POST /projects`
  - Body: `{ "name": str, "git_url": str, "base_branch": "main", "ci_provider": str|null, "default_models": obj|null, "secrets": obj|null }`
  - Creates project and enqueues a `project_setup_job` protocol run.
- `GET /projects` → list of projects.
- `GET /projects/{id}` → project (401 if project token required and missing).

## CodeMachine import
- `POST /projects/{id}/codemachine/import`
  - Body: `{ "protocol_name": str, "workspace_path": str, "base_branch": "main", "description": str|null, "enqueue": bool }`
  - When `enqueue=true`, returns `{ protocol_run, job, message }` after enqueuing `codemachine_import_job`.
  - When `enqueue=false` (default), imports immediately and returns `{ protocol_run, job: null, message }`.

## Protocol runs
- `POST /projects/{id}/protocols`
  - Body: `{ "protocol_name": str, "status": "pending"|..., "base_branch": "main", "worktree_path": str|null, "protocol_root": str|null, "description": str|null, "template_config": obj|null, "template_source": obj|null }`
- `GET /projects/{id}/protocols` → list protocol runs for project.
- `GET /protocols/{id}` → protocol run.

### Protocol actions
All return `{ "message": str, "job": obj|null }` unless noted.
- `POST /protocols/{id}/actions/start` → enqueues `plan_protocol_job` (409 if not pending/planned/paused).
- `POST /protocols/{id}/actions/pause` / `resume` / `cancel` → updates status, cancels pending steps on cancel.
- `POST /protocols/{id}/actions/run_next_step` → moves first pending/blocked/failed step to running and enqueues `execute_step_job`.
- `POST /protocols/{id}/actions/retry_latest` → retries latest failed/blocked step.
- `POST /protocols/{id}/actions/open_pr` → enqueues `open_pr_job`.

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

## Webhooks & CI callbacks
- `POST /webhooks/github?protocol_run_id=<optional>`
  - Headers: `X-GitHub-Event`, optional `X-Hub-Signature-256` when `DEKSDENFLOW_WEBHOOK_TOKEN` set.
  - Body: standard GitHub webhook payload. Maps by branch (or `protocol_run_id` query) to update step/protocol status, enqueue QA on success when `DEKSDENFLOW_AUTO_QA_ON_CI`=true, mark protocol completed on PR merge.
- `POST /webhooks/gitlab?protocol_run_id=<optional>`
  - Headers: `X-Gitlab-Event`, token via `X-Gitlab-Token` or `X-Deksdenflow-Webhook-Token`, optional HMAC `X-Gitlab-Signature-256`.
  - Similar mapping and QA/autocomplete behavior to GitHub handler.
- `scripts/ci/report.sh success|failure` can call these endpoints from CI with `DEKSDENFLOW_API_BASE`, `DEKSDENFLOW_API_TOKEN`, `DEKSDENFLOW_WEBHOOK_TOKEN`, `DEKSDENFLOW_PROTOCOL_RUN_ID` for explicit mapping.

## Queue/runtime notes
- Backend: Redis/RQ; when `DEKSDENFLOW_REDIS_URL=fakeredis://`, the API starts a background RQ worker thread for inline job processing.
- Jobs: `project_setup_job`, `plan_protocol_job`, `execute_step_job`, `run_quality_job`, `open_pr_job`, `codemachine_import_job`.
- CodeMachine policies: loop/trigger policies on steps may reset statuses or inline-trigger other steps (depth-limited) with events and `runtime_state` recorded.

## Curl examples

Create project:
```bash
curl -X POST http://localhost:8000/projects \
  -H "Authorization: Bearer $DEKSDENFLOW_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"demo","git_url":"/path/to/repo","base_branch":"main"}'
```

Start planning a protocol:
```bash
curl -X POST http://localhost:8000/protocols/1/actions/start \
  -H "Authorization: Bearer $DEKSDENFLOW_API_TOKEN"
```

Run QA for a step:
```bash
curl -X POST http://localhost:8000/steps/10/actions/run_qa \
  -H "Authorization: Bearer $DEKSDENFLOW_API_TOKEN"
```
