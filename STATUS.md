# Implementation Status – Orchestrator Track

## Recently completed
- Postgres adapter alongside SQLite with factory selection via `TASKSGODZILLA_DB_URL`; pool size configurable.
- Alembic scaffolding + initial migration (projects, protocol_runs, step_runs, events) applied to default SQLite.
- Token budgeting enforced in pipeline/QA (`TASKSGODZILLA_MAX_TOKENS_*`, strict/warn/off).
- Structured logging extended (JSON option via `TASKSGODZILLA_LOG_JSON`); workers/CLIs/API share logger init, request IDs, and standard exit codes; events now include protocol/step IDs and workers log job start/end with IDs.
- Makefile helpers: `orchestrator-setup`, `deps`, `migrate`.
- Compose stack + Dockerfile for `tasksgodzilla-core`; optional codex-worker service; K8s manifests for API/worker with probes and resource limits.
- Redis/RQ required for orchestration; fakeredis wired for tests/dev and API now fails fast when Redis is unreachable.
- Queue/worker updates: RQ enqueue includes retries; `RedisQueue.claim` supports in-process background worker for fakeredis/dev. Execution now lands in `needs_qa` and can auto-enqueue QA via `TASKSGODZILLA_AUTO_QA_AFTER_EXEC`; CI success can auto-enqueue QA via `TASKSGODZILLA_AUTO_QA_ON_CI`.
- CI callbacks: `scripts/ci/report.sh` posts GitHub/GitLab-style payloads back to `/webhooks/*` using `TASKSGODZILLA_API_BASE` (optional `TASKSGODZILLA_API_TOKEN`/`TASKSGODZILLA_WEBHOOK_TOKEN`).
- Console now includes a recent activity feed backed by `/events` (project-filterable) so ops can monitor runs without drilling into each protocol.
- CI reporter supports `TASKSGODZILLA_PROTOCOL_RUN_ID` to disambiguate branches when posting webhook-style status updates.
- Observability: events capture request IDs, token budgets are enforced in Codex workers with estimated token counters, and job durations are exported as Prometheus histograms.
- Logging: uvicorn runs with `log_config=None` so the shared formatter/filter stays active; workers/CodeMachine imports/loop+trigger flows now emit job/project/protocol/step IDs and errors via centralized `log_extra`. CLI prints are mirrored to structured logs and CI shell helpers emit JSON-style lines via `scripts/ci/logging.sh`.
- Project onboarding improvements: Projects accept and persist `local_path`; onboarding resolves that path before cloning (namespaced under `TASKSGODZILLA_PROJECTS_ROOT`), records the resolved path, configures git origin (prefers GitHub SSH when enabled), optionally sets git identity from env, and emits `setup_clarifications` (blocking when configured) with recommended CI/model/branch policies.
- Git/branch controls: new API endpoints to list remote branches and delete a branch on origin with confirmation; events are recorded for audit.

## How to run now
```bash
make orchestrator-setup \
  TASKSGODZILLA_DB_URL=postgresql://user:pass@host:5433/dbname  # compose host port; or use TASKSGODZILLA_DB_PATH for SQLite
```
Then start API: `.venv/bin/python scripts/api_server.py`
# Or use docker-compose: `docker compose up --build` (API on :8011)
# Redis URL required: set `TASKSGODZILLA_REDIS_URL` (use `fakeredis://` for local/testing; compose host is redis://localhost:6380/0).

## Next focus
- Refine token accounting with real usage data instead of heuristic.
- Extend Postgres path with connection pooling and Alembic-managed upgrades in CI.
- Console/API polish: surface DB choice/status, expose migrations health endpoint, richer console filters.
- Console UX for onboarding clarifications and branch management: surface `setup_clarifications` prompts in UI/TUI and add controls to confirm/resolve; wire branch list/delete actions into the console.

## Phase 0 gaps to close
- Container hardening: publish images, add secrets templates for DB/Redis/API tokens, and include readiness/liveness for codex/generic workers.
