# TasksGodzilla Orchestrator (alpha)

Central API/queue/worker slice for coordinating TasksGodzilla protocols. Ships with SQLite/Postgres persistence, Redis/RQ queue, webhook-aware API, and a lightweight web console.

## Quickstart
Local (SQLite + fakeredis):
```bash
make orchestrator-setup
TASKSGODZILLA_REDIS_URL=fakeredis:// .venv/bin/python scripts/api_server.py
# API at http://localhost:8010 (console at /console)
```

Docker Compose (Postgres + Redis):
```bash
docker compose up --build
# API at http://localhost:8011 (token from TASKSGODZILLA_API_TOKEN)
```
Compose ports: API 8011->8010, Postgres 5433->5432, Redis 6380->6379. Use `docker compose logs -f api worker codex-worker` for troubleshooting and `docker compose down -v` to clean state.

Local host app + compose dependencies (Postgres + Redis containers):
```bash
make compose-deps  # brings up db (5433) + redis (6380) containers
TASKSGODZILLA_DB_URL=postgresql://tasksgodzilla:tasksgodzilla@localhost:5433/tasksgodzilla \
TASKSGODZILLA_REDIS_URL=redis://localhost:6380/0 \
.venv/bin/python scripts/api_server.py --host 0.0.0.0 --port 8010
```

Redis is required; the API fails fast if it cannot reach `TASKSGODZILLA_REDIS_URL`.
When `fakeredis://` is used, the API also starts a background RQ worker thread for inline job processing.

## Components
- `tasksgodzilla/storage.py`: SQLite/Postgres DAO for Projects/ProtocolRuns/StepRuns/Events; migrations under `alembic/`.
- `tasksgodzilla/domain.py`: status enums and dataclasses for the core entities.
- `tasksgodzilla/api/app.py`: FastAPI app with bearer/project-token auth, console assets at `/console`, queue stats, metrics, webhook listeners, and project/protocol/step actions.
- `tasksgodzilla/git_utils.py`: repo resolution helpers (honor stored `projects.local_path` or clone under `TASKSGODZILLA_PROJECTS_ROOT`) plus remote branch list/delete.
- `tasksgodzilla/jobs.py`: Redis/RQ-backed queue abstraction; fakeredis supported for tests/dev.
- `tasksgodzilla/worker_runtime.py`: job processors and background worker helper (auto-starts when using fakeredis); `scripts/rq_worker.py` runs dedicated workers.
- `tasksgodzilla/codemachine/*`: loader + runtime adapter for `.codemachine` workspaces, including loop/trigger policy helpers and prompt resolution with placeholders/specifications.
- `tasksgodzilla/spec.py` + `tasksgodzilla/spec_tools.py`: unified ProtocolSpec/StepSpec schema helpers, prompt/output resolver + engine registry hooks, and spec audit/backfill.
- `tasksgodzilla/logging.py`: structured logging helpers with request IDs.
- `scripts/api_server.py`: uvicorn runner for the API.
- `scripts/ci_trigger.py` and `scripts/ci/report.sh`: optional helpers to trigger CI and to post webhook-style results back into the orchestrator.

## Status model & automation knobs
- ProtocolRun: `pending → planning → planned → running → (paused | blocked | failed | cancelled | completed)`.
- StepRun: `pending → running → needs_qa → (completed | failed | cancelled | blocked)`.
- Auto QA: `TASKSGODZILLA_AUTO_QA_AFTER_EXEC` triggers QA after execution; `TASKSGODZILLA_AUTO_QA_ON_CI` triggers QA on successful CI webhooks.
- Token budgets: `TASKSGODZILLA_MAX_TOKENS_PER_STEP` / `TASKSGODZILLA_MAX_TOKENS_PER_PROTOCOL` with `TASKSGODZILLA_TOKEN_BUDGET_MODE=strict|warn|off`.
- Onboarding: uses stored `local_path` when present, otherwise clones under `TASKSGODZILLA_PROJECTS_ROOT` (namespaced host/owner/repo). Auto-configures `origin` (prefers GitHub SSH when `TASKSGODZILLA_GH_SSH=true`), optionally sets git identity from `TASKSGODZILLA_GIT_USER` / `TASKSGODZILLA_GIT_EMAIL`, and emits `setup_clarifications` (blocking when `TASKSGODZILLA_REQUIRE_ONBOARDING_CLARIFICATIONS=true`).
- Queue: Redis/RQ with retries/backoff (defaults: 3 attempts, capped backoff); jobs append Events and carry IDs for tracing.
- Policies: StepSpec policies (often from CodeMachine modules) attach loop/trigger behavior to steps; loops reset step statuses with bounded iteration counts, and triggers can enqueue or inline-run other steps (depth-limited to prevent recursion).

## API surface (non-exhaustive)
- `GET /health` → `{ "status": "ok" }`; `GET /metrics` for Prometheus output.
- `GET /console` serves the web console (static assets).
- Projects: `POST /projects`, `GET /projects`, `GET /projects/{id}`.
- CodeMachine: `POST /projects/{id}/codemachine/import` to ingest `.codemachine` workspaces and create steps.
- Protocols: `POST /projects/{id}/protocols`, `GET /projects/{id}/protocols`, `GET /protocols/{id}`, actions `start|pause|resume|cancel|run_next_step|retry_latest|open_pr`.
- Steps: `POST /protocols/{id}/steps`, `GET /protocols/{id}/steps`, `GET /steps/{id}`, actions `run`, `run_qa`, `approve`.
- Branches: `GET /projects/{id}/branches` to list origin branches; `POST /projects/{id}/branches/{branch}/delete` (body `{"confirm": true}`) to remove remote branches.
- Events: `GET /protocols/{id}/events`, `GET /events?project_id=...`.
- Queue inspection: `GET /queues`, `GET /queues/jobs?status=queued|started|failed|finished`.
- Webhooks: `POST /webhooks/github`, `POST /webhooks/gitlab` (optional `TASKSGODZILLA_WEBHOOK_TOKEN` HMAC). Map branches/IDs to runs, record events, auto-enqueue QA on CI success when configured.

## Auth & observability
- API bearer token via `TASKSGODZILLA_API_TOKEN`; optional per-project token via `X-Project-Token`.
- Console fields persist tokens locally and reuse them for API calls.
- Events carry request IDs; logs can be JSON via `TASKSGODZILLA_LOG_JSON=true`.
- Metrics exported via `/metrics`; queue state via `/queues*`; console shows recent events and protocol/step timelines.
