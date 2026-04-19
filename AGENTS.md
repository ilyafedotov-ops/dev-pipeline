# Repository Guidelines

## Project Structure & Module Organization
- `devgodzilla/` is the primary backend: FastAPI app wiring, route modules, services, engines, DB access, and Windmill client code.
- `frontend/` is the Next.js 16 console mounted at `/console`; UI routes live under `frontend/app/`, shared client code under `frontend/lib/`, and component primitives under `frontend/components/`.
- `windmill/` contains Windmill scripts, flows, apps, resources, and the import manifest exported from this repo.
- `scripts/` holds operational CLIs, local-dev helpers, and `scripts/ci/*.sh` wrappers for backend/frontend checks.
- `tests/` contains the Python `pytest` suite, including backend unit/integration coverage plus `tests/e2e/` harness scenarios and adapters.
- `docs/` contains active project documentation; `docs/legacy/` is historical and should not be treated as authoritative.
- `templates/`, `schemas/`, `prompts/`, `projects/`, and `runs/` store reusable templates, JSON contracts, prompt assets, local project workspaces, and generated runtime artifacts.
- `Origins/` contains vendored upstream sources (Windmill, spec-kit, etc.); avoid editing unless explicitly required.

## Build, Test, and Development Commands
- Bootstrap backend env: `scripts/ci/bootstrap.sh` creates `.venv` and installs `requirements.txt` plus `ruff`.
- Backend lint: `scripts/ci/lint.sh` runs `ruff check devgodzilla windmill scripts tests --select E9,F63,F7,F82` plus the standalone guard.
- Backend type/import smoke: `scripts/ci/typecheck.sh`.
- Backend unit tests: `scripts/ci/test.sh` runs `pytest -q --disable-warnings --maxfail=1 tests/test_devgodzilla_*.py -k "not integration"`.
- Optional real-agent E2E in the backend test wrapper: set `DEVGODZILLA_RUN_E2E_REAL_AGENT=1`.
- Frontend checks: `scripts/ci/test_frontend.sh`, or in `frontend/`: `pnpm typecheck`, `pnpm lint`, `pnpm test:run`, `pnpm test:e2e:smoke`.
- Docker full stack (default compose): `docker compose up --build -d` or `scripts/run-local-dev.sh up`. This uses `docker-compose.yml` and `nginx.devgodzilla.conf`.
- Alternate full-stack local variant: `docker compose -f docker-compose.local.yml up -d`.
- Host dev servers only: `scripts/run-local-dev.sh backend start|stop|restart|status` and `scripts/run-local-dev.sh frontend start|stop|restart|status`.
- Combined local-dev helper: `scripts/run-local-dev.sh dev` starts the default compose stack, then starts host backend/frontend processes for direct debugging and hot reload.
- Explicit host-proxy topology: `docker compose -f docker-compose.devgodzilla.yml up -d` uses `nginx.local.conf` to proxy to backend/frontend on `host.docker.internal`.
- Windmill bootstrap import: `scripts/run-local-dev.sh import`.
- Stack monitor: `scripts/pipeline-ctl.sh status|health|watch|logs`.

## Coding Style & Naming Conventions
- Python 3.12, PEP 8 / black-like formatting with 4-space indents; prefer explicit imports and type hints.
- Module/files: `snake_case.py`; classes: `CamelCase`; functions/vars: `snake_case`; constants/env keys: `UPPER_SNAKE`.
- Frontend code is TypeScript-first. Follow existing App Router patterns in `frontend/app/` and shared hooks/utilities in `frontend/lib/`.
- Centralize backend config via `devgodzilla.config.get_config()` / `load_config()` and log through `devgodzilla.logging.get_logger()` for structured output.
- When touching Windmill scripts/flows/apps, mirror existing naming and paths under `windmill/`.

## Testing Guidelines
- Add or extend Python tests near existing patterns in `tests/`; use `tests/e2e/` only for harness or live-flow coverage.
- Use temp SQLite DBs or injected dependencies for deterministic backend tests; keep real Windmill and live agent usage out of default CI paths.
- Keep golden-path and error-path assertions together, especially for API contracts, orchestration state transitions, and QA verdicts.
- For frontend changes, add or update Vitest coverage in `frontend/__tests__/` or colocated tests and run the Playwright smoke flow when routes or interactions change.

## Commit & Pull Request Guidelines
- Follow the repo’s short typed subject style: `feat:`, `fix:`, `chore:`, `docs:`.
- Scope commits narrowly and keep messages imperative, for example `fix: align protocol route auth handling`.
- For protocol work, include the protocol tag (`[protocol-NNNN/YY]`) when relevant.
- PRs should summarize behavior changes, list commands run, call out config/env impacts, and include screenshots for user-visible console changes.

## Security & Configuration Tips
- Never commit real tokens or DB URLs; rely on env vars such as `DEVGODZILLA_DB_URL`, `DEVGODZILLA_API_TOKEN`, `DEVGODZILLA_WEBHOOK_TOKEN`, and `DEVGODZILLA_WINDMILL_TOKEN`.
- Current configured CLI agents live in `devgodzilla/config/agents.yaml`; the default engine is `opencode` with model `zai-coding-plan/glm-5`.
- For local Windmill imports, `DEVGODZILLA_WINDMILL_ENV_FILE` defaults to `windmill/apps/devgodzilla-react-app/.env.development` and is expected to stay local-only.
- Full-Docker backend runs can consume provider credentials from env (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GEMINI_API_KEY`) and optional per-engine model overrides such as `DEVGODZILLA_OPENCODE_MODEL`, `DEVGODZILLA_CODEX_MODEL`, and `DEVGODZILLA_CLAUDE_MODEL`.
