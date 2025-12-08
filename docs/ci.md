# CI Notes for TasksGodzilla_Ilyas_Edition_1.0

Both GitHub Actions and GitLab CI call the same shell hooks under `scripts/ci/`. Replace the stubs with real commands for your stack.

## Scripts implemented
- `scripts/ci/bootstrap.sh` — creates `.venv`, installs `requirements-orchestrator.txt` + `ruff`, exports `TASKSGODZILLA_DB_PATH=/tmp/tasksgodzilla-ci.sqlite` and `TASKSGODZILLA_REDIS_URL=redis://localhost:6379/15` (Redis must be running).
- `scripts/ci/lint.sh` — `ruff check tasksgodzilla scripts tests --select E9,F63,F7,F82` (syntax/undefined names).
- `scripts/ci/typecheck.sh` — `compileall` + import smoke for `tasksgodzilla.config`, API app, and CLI entrypoints.
- `scripts/ci/test.sh` — `pytest -q --disable-warnings --maxfail=1` with temp SQLite and a real Redis URL from `TASKSGODZILLA_REDIS_URL`.
- `scripts/ci/build.sh` — `docker build -t tasksgodzilla-ci .` if Docker exists; otherwise `docker-compose config -q`.
- Optional: `scripts/codex_ci_bootstrap.py` (bash) to run Codex discovery for a target repo:  
  `bash scripts/codex_ci_bootstrap.py --model gpt-5.1-codex-max --prompt-file prompts/repo-discovery.prompt.md --repo-root <repo-root> --sandbox workspace-write [--skip-git-check]` (requires `codex` CLI; writes discovery docs under `tasksgodzilla/` in the target repo).

## Local parity
```bash
./scripts/ci/bootstrap.sh
./scripts/ci/lint.sh
./scripts/ci/typecheck.sh
./scripts/ci/test.sh
./scripts/ci/build.sh
```

## GitHub Actions
- File: `.github/workflows/ci.yml`
- Jobs: `checks` (bootstrap → lint → typecheck → test → build)
- Triggered on `push` and `pull_request`.

## GitLab CI
- File: `.gitlab-ci.yml`
- Stages: `bootstrap`, `lint`, `typecheck`, `test`, `build`
- Jobs mirror the GitHub Actions order and reuse the same scripts.

## CI detail checklist (recommended)
1) Bootstrap: install deps, set env (e.g., `NODE_ENV=ci`), verify versions (`node --version`, `python --version`), and cache deps where applicable.
2) Lint: run linters with full exit-on-error; surface reports if available.
3) Typecheck: run type checker separately from lint to catch typing issues explicitly.
4) Test: run unit/integration tests; consider `CI=true` flags; produce coverage if desired.
5) Build: optional packaging or artifact build; fail fast on errors.
6) Skip behavior: scripts are optional; missing/executable check is already handled in workflows.
7) Artifacts: if your stack supports reports (e.g., JUnit XML), add upload steps in workflow as needed.

## Caching
Add cache steps per stack as needed (npm, pip, pnpm, cargo, go build cache, Maven/Gradle). Keep cache keys stable across both CI systems for consistency.
