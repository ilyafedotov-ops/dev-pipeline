# Implementation Status – Orchestrator Track

## Recently completed
- Postgres adapter alongside SQLite with factory selection via `DEKSDENFLOW_DB_URL`; pool size configurable.
- Alembic scaffolding + initial migration (projects, protocol_runs, step_runs, events) applied to default SQLite.
- Token budgeting enforced in pipeline/QA (`DEKSDENFLOW_MAX_TOKENS_*`, strict/warn/off).
- Structured logging extended (JSON option via `DEKSDENFLOW_LOG_JSON`); workers/CLIs/API share logger init, request IDs, and standard exit codes; events now include protocol/step IDs and workers log job start/end with IDs.
- Makefile helpers: `orchestrator-setup`, `deps`, `migrate`.
- Compose stack + Dockerfile for `deksdenflow-core`; optional codex-worker service; K8s manifests for API/worker with probes and resource limits.
- Redis/RQ required for orchestration; fakeredis wired for tests/dev and API now fails fast when Redis is unreachable.
- Queue/worker updates: RQ enqueue includes retries; `RedisQueue.claim` supports in-process background worker for fakeredis/dev. Execution now lands in `needs_qa` and can auto-enqueue QA via `DEKSDENFLOW_AUTO_QA_AFTER_EXEC`; CI success can auto-enqueue QA via `DEKSDENFLOW_AUTO_QA_ON_CI`.
- CI callbacks: `scripts/ci/report.sh` posts GitHub/GitLab-style payloads back to `/webhooks/*` using `DEKSDENFLOW_API_BASE` (optional `DEKSDENFLOW_API_TOKEN`/`DEKSDENFLOW_WEBHOOK_TOKEN`).
- Console now includes a recent activity feed backed by `/events` (project-filterable) so ops can monitor runs without drilling into each protocol.
- CI reporter supports `DEKSDENFLOW_PROTOCOL_RUN_ID` to disambiguate branches when posting webhook-style status updates.
- Observability: events capture request IDs, token budgets are enforced in Codex workers with estimated token counters, and job durations are exported as Prometheus histograms.
- Logging: uvicorn runs with `log_config=None` so the shared formatter/filter stays active; workers/CodeMachine imports/loop+trigger flows now emit job/project/protocol/step IDs and errors via centralized `log_extra`.

## How to run now
```bash
make orchestrator-setup \
  DEKSDENFLOW_DB_URL=postgresql://user:pass@host:5432/dbname  # or use DEKSDENFLOW_DB_PATH for SQLite
```
Then start API: `.venv/bin/python scripts/api_server.py`
# Or use docker-compose: `docker-compose up --build` (API on :8010)
# Redis URL required: set `DEKSDENFLOW_REDIS_URL` (use `fakeredis://` for local/testing).

## Next focus
- Refine token accounting with real usage data instead of heuristic.
- Extend Postgres path with connection pooling and Alembic-managed upgrades in CI.
- Console/API polish: surface DB choice/status, expose migrations health endpoint, richer console filters.
- Logging follow-ups: harmonize CLI-only print paths and CI shell helpers with the structured logger.

## Phase 0 gaps to close
- Logging normalization: remaining gaps are CLI print paths and CI shell helpers that bypass the logger; everything else now emits protocol/step/job/project IDs.
- Container hardening: publish images, add secrets templates for DB/Redis/API tokens, and include readiness/liveness for codex/generic workers.
