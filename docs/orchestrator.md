# DeksdenFlow Orchestrator (alpha)

Central API/queue/worker slice for coordinating DeksdenFlow protocols. Ships with SQLite/Postgres persistence, Redis/RQ queue, webhook-aware API, and a lightweight web console.

## Quickstart
Local (SQLite + fakeredis):
```bash
make orchestrator-setup
DEKSDENFLOW_REDIS_URL=fakeredis:// .venv/bin/python scripts/api_server.py
# API at http://localhost:8000 (console at /console)
```

Docker Compose (Postgres + Redis):
```bash
docker-compose up --build
# API at http://localhost:8000 (token from DEKSDENFLOW_API_TOKEN)
```

Redis is required; the API fails fast if it cannot reach `DEKSDENFLOW_REDIS_URL`.

## Components
- `deksdenflow/storage.py`: SQLite/Postgres DAO for Projects/ProtocolRuns/StepRuns/Events; migrations under `alembic/`.
- `deksdenflow/domain.py`: status enums and dataclasses for the core entities.
- `deksdenflow/api/app.py`: FastAPI app with bearer/project-token auth, console assets at `/console`, queue stats, metrics, webhook listeners, and project/protocol/step actions.
- `deksdenflow/jobs.py`: Redis/RQ-backed queue abstraction; fakeredis supported for tests/dev.
- `deksdenflow/worker_runtime.py`: job processors and background worker helper (auto-starts when using fakeredis); `scripts/rq_worker.py` runs dedicated workers.
- `deksdenflow/logging.py`: structured logging helpers with request IDs.
- `scripts/api_server.py`: uvicorn runner for the API.
- `scripts/ci_trigger.py` and `scripts/ci/report.sh`: optional helpers to trigger CI and to post webhook-style results back into the orchestrator.

## Status model & automation knobs
- ProtocolRun: `pending → planning → planned → running → (paused | blocked | failed | cancelled | completed)`.
- StepRun: `pending → running → needs_qa → (completed | failed | cancelled | blocked)`.
- Auto QA: `DEKSDENFLOW_AUTO_QA_AFTER_EXEC` triggers QA after execution; `DEKSDENFLOW_AUTO_QA_ON_CI` triggers QA on successful CI webhooks.
- Token budgets: `DEKSDENFLOW_MAX_TOKENS_PER_STEP` / `DEKSDENFLOW_MAX_TOKENS_PER_PROTOCOL` with `DEKSDENFLOW_TOKEN_BUDGET_MODE=strict|warn|off`.
- Queue: Redis/RQ with retries/backoff (defaults: 3 attempts, capped backoff); jobs append Events and carry IDs for tracing.

## API surface (non-exhaustive)
- `GET /health` → `{ "status": "ok" }`; `GET /metrics` for Prometheus output.
- `GET /console` serves the web console (static assets).
- Projects: `POST /projects`, `GET /projects`, `GET /projects/{id}`.
- Protocols: `POST /projects/{id}/protocols`, `GET /projects/{id}/protocols`, `GET /protocols/{id}`, actions `start|pause|resume|cancel|run_next_step|retry_latest|open_pr`.
- Steps: `POST /protocols/{id}/steps`, `GET /protocols/{id}/steps`, `GET /steps/{id}`, actions `run`, `run_qa`, `approve`.
- Events: `GET /protocols/{id}/events`, `GET /events?project_id=...`.
- Queue inspection: `GET /queues`, `GET /queues/jobs?status=queued|started|failed|finished`.
- Webhooks: `POST /webhooks/github`, `POST /webhooks/gitlab` (optional `DEKSDENFLOW_WEBHOOK_TOKEN` HMAC). Map branches/IDs to runs, record events, auto-enqueue QA on CI success when configured.

## Auth & observability
- API bearer token via `DEKSDENFLOW_API_TOKEN`; optional per-project token via `X-Project-Token`.
- Console fields persist tokens locally and reuse them for API calls.
- Events carry request IDs; logs can be JSON via `DEKSDENFLOW_LOG_JSON=true`.
- Metrics exported via `/metrics`; queue state via `/queues*`; console shows recent events and protocol/step timelines.
