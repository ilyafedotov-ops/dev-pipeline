# Work Log: 0002 — demo-app-workflow

This is an append-only log:

{add entries about actions, decisions, gotchas, solved issues}

## Step 0 — Prepare and lock the plan (task breakdown)
1. Confirm workspace state: `pwd` matches /home/ilya/Documents/worktrees/0002-demo-app-workflow, on branch `0002-demo-app-workflow`, `git status` clean, `main` untouched.
2. Inventory protocol artifacts in `.protocols/0002-demo-app-workflow/` (plan.md, context.md, log.md, 00-setup.md through 05-finalize.md); create/fix placeholders if any missing, without editing the contract content.
3. Re-read `plan.md` and step files to align with the contract; ensure `context.md` reflects Step 0 before proceeding.
4. Stage protocol artifacts only, then run `scripts/ci/lint.sh`, `scripts/ci/typecheck.sh`, `scripts/ci/test.sh`; note in log if any are skipped or fail and why.
5. Commit staged protocol artifacts with typed message `feat(<scope>): <subject> [protocol-0002/00]` (e.g., `feat(protocol): lock protocol files [protocol-0002/00]`).
6. Push branch to origin and open a draft PR to `main` summarizing protocol 0002 scope and current status.
7. Update `.protocols/0002-demo-app-workflow/context.md` to `Current Step` 1, `Status` In Progress, and `Next Action` pointing to Step 1; leave this change uncommitted.
8. Append log.md with commit hash, check results, PR link, and any gotchas; verify `main` has no stray files from this branch after push.

## Step 0 — Execution log
- Generated protocol artifacts via Codex planning/decompose; committed as `chore: add protocol plan [protocol-0002/00]` (27b228c) on branch `0002-demo-app-workflow`.
- CI checks from worktree using root venv: `scripts/ci/lint.sh`, `scripts/ci/typecheck.sh`, `scripts/ci/test.sh` all passed (VENV_PATH=/home/ilya/Documents/dev-pipeline/.venv).
- Draft PR opened to main for tracking: https://github.com/ilyafedotov-ops/dev-pipeline/pull/1.

## Step 1 — Scope and baseline (notes)
- Read `AGENTS.md` for repo/CI conventions and env guidance; `README.md` for orchestration overview and quick start; docs and prompts reference the demo harness (`scripts/demo_harness.py`, `tests/test_demo_harness.py`).
- Candidate demo workflow: reuse the offline demo harness flow (onboarding → planning stub → spec audit → step execution → QA skip) via `scripts/demo_harness.py` / `tests/test_demo_harness.py`; uses fakeredis + temp SQLite with `TASKSGODZILLA_AUTO_CLONE=false`.
- Baseline repo state: branch `0002-demo-app-workflow` clean except for context updates, head `bba50d6`; CI scripts available in `scripts/ci/*.sh`.
- Env/services: fakeredis (`TASKSGODZILLA_REDIS_URL=fakeredis://`), SQLite (`TASKSGODZILLA_DB_PATH=/tmp/tasksgodzilla-ci.sqlite`); API/worker entrypoints `scripts/api_server.py`, `scripts/rq_worker.py`.
- Pending: proceed to execute Step 1 tasks and then advance context to Step 2.
