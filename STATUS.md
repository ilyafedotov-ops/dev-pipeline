# Implementation Status – Orchestrator Track

## Recently completed
- Added Postgres adapter (psycopg3) alongside SQLite and wired a factory (`create_database`) to select based on `DEKSDENFLOW_DB_URL`.
- Added Alembic scaffolding and initial migration (projects, protocol_runs, step_runs, events); applied to the default SQLite DB.
- Token budgeting now configurable (`DEKSDENFLOW_MAX_TOKENS_*`, `DEKSDENFLOW_TOKEN_BUDGET_MODE` strict/warn/off) and enforced in pipeline/QA.
- Structured logging propagated to workers (config-driven log level; Codex worker emits plan/exec/QA/CI events).
- Makefile helpers: `orchestrator-setup` (venv + deps + migrate), plus `deps` and `migrate`.

## How to run now
```bash
make orchestrator-setup \
  DEKSDENFLOW_DB_URL=postgresql://user:pass@host:5432/dbname  # or use DEKSDENFLOW_DB_PATH for SQLite
```
Then start API: `.venv/bin/python scripts/api_server.py`

## Next focus
- Harden logging/error handling across all CLIs and workers (request IDs, consistent exit codes).
- Refine token accounting with real usage data instead of heuristic.
- Extend Postgres path with connection pooling and Alembic-managed upgrades in CI.
- Console/API polish: surface DB choice/status, expose migrations health endpoint.
