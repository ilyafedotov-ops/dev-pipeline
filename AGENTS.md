# Repository Guidelines

## Project Structure & Module Organization
- `deksdenflow/` houses the FastAPI orchestrator, queue workers, job definitions, and shared config/logging helpers. UI assets for the console live under `deksdenflow/api/frontend/`.
- `scripts/` holds operational CLIs (protocol pipeline, quality orchestrator, project bootstrap) plus `scripts/ci/*.sh` hooks invoked by both GitHub Actions and GitLab CI.
- `tests/` uses `pytest` for API, worker, and Codex coverage.
- `docs/` and `prompts/` contain process guidance and reusable agent prompts; `schemas/` stores JSON Schemas; `alembic/` tracks DB migrations.

## Build, Test, and Development Commands
- Bootstrap CI/local env: `scripts/ci/bootstrap.sh` (`python3 -m venv .venv`, install `requirements-orchestrator.txt` + `ruff`, defaults `DEKSDENFLOW_DB_PATH=/tmp/deksdenflow-ci.sqlite`, `DEKSDENFLOW_REDIS_URL=fakeredis://`).
- Lint: `scripts/ci/lint.sh` (`ruff check deksdenflow scripts tests --select E9,F63,F7,F82`).
- Typecheck: `scripts/ci/typecheck.sh` (compileall + import smoke for config, API app, and CLIs).
- Tests: `scripts/ci/test.sh` (`pytest -q --disable-warnings --maxfail=1` with fakeredis + temp SQLite). API locally: `.venv/bin/python scripts/api_server.py --host 0.0.0.0 --port 8010`; worker: `.venv/bin/python scripts/rq_worker.py`.
- Build: `scripts/ci/build.sh` (`docker build -t deksdenflow-ci .`; falls back to `docker-compose config -q` if Docker is absent). Full stack: `docker-compose up --build`.

## Coding Style & Naming Conventions
- Python 3.12, PEP8/black-like formatting with 4-space indents; prefer explicit imports and type hints.
- Module/files: `snake_case.py`; classes: `CamelCase`; functions/vars: `snake_case`; constants/env keys: `UPPER_SNAKE`.
- Centralize config via `deksdenflow.config.load_config()` and log through `deksdenflow.logging.setup_logging` to keep structured output consistent.
- When touching prompts or schemas, mirror existing naming (`protocol_pipeline`, `*_prompt.md`, `*.schema.json`).

## Testing Guidelines
- Add/extend `pytest` cases next to existing patterns (e.g., `tests/test_storage.py` for DB access, `tests/test_workers_auto_qa.py` for queue flows).
- Prefer small, isolated units; use `fakeredis://` for Redis-dependent tests and temp SQLite DBs for storage.
- Keep golden path + error path assertions; mock Codex/HTTP calls with `httpx` test clients where possible.

## Commit & Pull Request Guidelines
- Follow the repo’s short, typed subject style: `feat:`, `chore:`, `fix:`, `docs:` (see `git log`).
- Scope commits narrowly and keep messages imperative (`feat: add worker retry backoff`).
- PRs should summarize changes, list test commands run, call out config/env impacts (e.g., new `DEKSDENFLOW_*` vars), and link issues/tasks; include console/API screenshots when UI behavior changes.

## Security & Configuration Tips
- Never commit real tokens or DB/Redis URLs; rely on env vars (`DEKSDENFLOW_REDIS_URL`, `DEKSDENFLOW_DB_URL`/`DEKSDENFLOW_DB_PATH`, `DEKSDENFLOW_API_TOKEN`).
- Prefer `fakeredis://` and SQLite for local work; use Postgres + rotated tokens in shared stacks.
- Keep queue/CI callbacks consistent via `scripts/ci/report.sh` and `DEKSDENFLOW_PROTOCOL_RUN_ID` when branch detection is ambiguous.
