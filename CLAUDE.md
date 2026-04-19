# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Big-Picture Architecture

DevGodzilla is a spec-driven, agent-executed software development platform. Three things to understand before making non-trivial changes:

**1. Layers (top → bottom).** Browser → nginx (`:8080`) → Next.js console (`/console`, `frontend/`) **or** FastAPI (`devgodzilla/api/`) **or** Windmill UI (`/`). The FastAPI app (`devgodzilla/api/app.py`) delegates to services (`devgodzilla/services/`), which dispatch work to engines (`devgodzilla/engines/`) and/or Windmill flows (`devgodzilla/windmill/` + `windmill/flows/devgodzilla/`). State lives in Postgres/SQLite (`devgodzilla/db/`, migrations in `devgodzilla/alembic/`) plus the filesystem (`projects/`, `worktrees/`, `.protocols/*`, `specs/discovery/_runtime/*`).

**2. Agent-driven workflow.** The platform does not write code directly; it prompts a headless SWE-agent (default `opencode`, model overridden by `DEVGODZILLA_OPENCODE_MODEL`) using prompts from `prompts/`. The agent writes artifacts into a per-protocol git worktree (under `worktrees/`), and DevGodzilla validates/records those outputs. Key artifact paths:
- Discovery: `specs/discovery/_runtime/{DISCOVERY,ARCHITECTURE,API_REFERENCE,CI_NOTES}.md`
- Protocol plan/steps: `.protocols/<protocol_name>/{plan.md,step-*.md}`
- Execution reports: `.protocols/<protocol_name>/.devgodzilla/steps/<step_run_id>/artifacts/*`

**3. Engine adapter pattern.** Any file in `devgodzilla/engines/` (e.g. `opencode.py`, `claude_code.py`, `codex.py`, `gemini.py`, `dummy.py`) implements `interface.py` (`plan()`, `execute()`, `qa()`). `registry.py` resolves engines by id; `agents.yaml` (under `devgodzilla/config/`, loaded through `devgodzilla.config.load_config()`) declares capabilities and default models. Per-project overrides flow through `AgentConfigService`. When adding a new engine, mirror an existing adapter rather than extending the interface.

**Canonical docs (trust these over legacy):** `docs/DevGodzilla/{CURRENT_STATE,ARCHITECTURE,API-ARCHITECTURE,WINDMILL-WORKFLOWS,BROWNFIELD-WORKFLOW}.md`. Anything under `docs/legacy/` is non-authoritative. If docs and code disagree, trust code first, then update the canonical doc.

**Vendored sources.** `Origins/` holds vendored upstream (Windmill, spec-kit). Do not edit unless explicitly requested.

## Commands

### Python backend
- Bootstrap: `scripts/ci/bootstrap.sh` (creates `.venv`, installs `requirements.txt` + `ruff`).
- Lint: `scripts/ci/lint.sh` → `ruff check devgodzilla windmill scripts tests --select E9,F63,F7,F82` (runtime-breaking checks only, not full style).
- Typecheck: `scripts/ci/typecheck.sh` (compileall + import smoke — no mypy).
- Tests (unit, default): `scripts/ci/test.sh` → `pytest -q tests/test_devgodzilla_*.py -k "not integration"`.
- Run a single test: `.venv/bin/pytest tests/test_devgodzilla_windmill_workflows.py::TestName::test_case -q`.
- Integration tests (live services): `DEVGODZILLA_RUN_LIVE_INTEGRATION_TESTS=1 pytest tests/test_devgodzilla_frontend_integration.py` or mark with `@pytest.mark.integration`.
- Real-agent E2E (requires installed `opencode`): `DEVGODZILLA_RUN_E2E_REAL_AGENT=1 scripts/ci/test_e2e_real_agent.sh`.
- Migrations: `make migrate` (or `.venv/bin/alembic upgrade head`).

### Frontend (`frontend/`, pnpm)
- `pnpm dev` / `pnpm build` / `pnpm start`
- `pnpm typecheck` (`tsc --noEmit`), `pnpm lint`, `pnpm check` (typecheck + lint + format:check)
- `pnpm test:run` (Vitest one-shot), `pnpm test:e2e:smoke` (Playwright smoke)

### Stack lifecycle
- Full Docker stack: `docker compose up --build -d` (nginx, windmill, workers, db, redis, devgodzilla-api, frontend). Console at `http://localhost:8080/console`, API docs at `/docs`, Windmill UI at `/`.
- Unified helper: `scripts/run-local-dev.sh {up|down|clean|status|logs|dev|import|backend …|frontend …}`. `dev` = infra in Docker + backend/frontend on host (hybrid).
- Stack monitor: `scripts/pipeline-ctl.sh {status|health --exit-code|watch|logs|restart|fix}`. Shortcuts: `make ctl-status`, `make ctl-health`, `make ctl-watch`, `make ctl-logs`.
- Windmill one-shot bootstrap import: `scripts/run-local-dev.sh import`.

## Conventions

- Python 3.12, 4-space indents, type hints preferred. `snake_case.py`, `CamelCase` classes, `UPPER_SNAKE` env keys. All env keys are `DEVGODZILLA_*`.
- Config must route through `devgodzilla.config.load_config()`; logs through `devgodzilla.logging.get_logger()` (structured).
- When touching Windmill assets, mirror existing paths: scripts → `windmill/scripts/devgodzilla/` (→ `u/devgodzilla/*`), flows → `windmill/flows/devgodzilla/` (→ `f/devgodzilla/*`).
- Tests use temp SQLite DBs and dependency-inject a fake Windmill client. Do not hit real Windmill from unit tests; gate live calls behind `DEVGODZILLA_RUN_LIVE_INTEGRATION_TESTS=1` or the `integration` marker.
- Commit subjects use typed prefixes (`feat:`, `fix:`, `chore:`, `docs:`). For protocol work include a protocol tag `[protocol-NNNN/YY]` when relevant.

## Windmill feature flag

`WINDMILL_FEATURES` defaults to `static_frontend python deno_core`. Dropping `deno_core` breaks any flow that uses JavaScript `input_transforms` — keep it unless intentionally building a Python-only subset.

## Agent defaults

Default engine is `opencode` with the model from `DEVGODZILLA_OPENCODE_MODEL` (or `devgodzilla/config/agents.yaml`). For Docker-hosted API, run `opencode auth login` on the host first so the mounted auth state is visible inside the container. Check `/agents/health` to verify the runtime can actually execute configured agents (vs. just listing them via `/agents`).

## Notes for Claude Code

- `AGENTS.md` currently duplicates part of this file and targets the `nginx.local.conf` / hybrid-dev workflow; prefer `CLAUDE.md` + the canonical docs in `docs/DevGodzilla/` when they diverge.
- `frontend/package.json` still has `"name": "my-v0-project"` — cosmetic leftover from scaffolding, not a sign of a different project.
- `projects/`, `runs/`, `worktrees/`, `archive/` are runtime working directories — do not commit their contents.
