# Step 02: Bootstrap environment

## Briefing
- **Goal:** Prepare a clean Python 3.12 environment with all dependencies and configuration needed for the demo workflow.
- **Key files:**
  - `scripts/ci/bootstrap.sh`
  - `requirements-orchestrator.txt`, `requirements.txt` (if applicable)
  - `.env` or env var exports for `TASKSGODZILLA_*`
- **Additional info:** Default local settings use `TASKSGODZILLA_DB_PATH=/tmp/tasksgodzilla-ci.sqlite` and `TASKSGODZILLA_REDIS_URL=fakeredis://`. Prefer the provided scripts over manual installs.

## Sub-tasks
1. Confirm Python toolchain
   - From the worktree, run `python3 --version` and ensure it is 3.12.x; note the path with `which python3`.
   - If the default `python` differs, plan to invoke `python3` explicitly for all commands in this step.
2. Create or refresh the virtualenv
   - If a stale `.venv` exists or points to the wrong interpreter, recreate it with `python3 -m venv .venv` in the worktree root.
   - Activate the venv (`source .venv/bin/activate`) and upgrade packaging tools (`python -m pip install --upgrade pip wheel setuptools`); verify `which python` points inside `.venv`.
3. Install dependencies via bootstrap script
   - Run `scripts/ci/bootstrap.sh` from the worktree root to install orchestrator requirements and `ruff`; capture any errors for troubleshooting.
   - If overrides are needed, set `TASKSGODZILLA_DB_PATH` and `TASKSGODZILLA_REDIS_URL` inline when invoking the script; avoid editing the script itself.
4. Set required environment variables locally
   - Export or place in an untracked `.env` the values for `TASKSGODZILLA_DB_PATH=/tmp/tasksgodzilla-ci.sqlite`, `TASKSGODZILLA_REDIS_URL=fakeredis://`, and any `TASKSGODZILLA_API_TOKEN` if required for the demo.
   - Confirm they are loaded in the active shell (`env | grep TASKSGODZILLA`).
5. Smoke-check the installation
   - Validate the environment can import project modules with a quick script (e.g., `python - <<'PY'\nimport tasksgodzilla\nprint(tasksgodzilla.__version__)\nPY`).
   - Run a lightweight check such as `scripts/ci/typecheck.sh` to ensure the venv is functional; note any missing binaries (e.g., `ruff`) and resolve in the venv.
6. Capture and document environment details
   - Record Python version, key tool versions (`ruff --version`, `pip show tasksgodzilla` if applicable), and any deviations from defaults.
   - Update `log.md` with what was installed/configured and why; flag any follow-ups needed before the demo run.

## Workflow
1. Execute the sub-tasks above in order from the worktree root, using the `.venv` Python for all commands.
2. Verify: run `scripts/ci/lint.sh`, `scripts/ci/typecheck.sh`, and `scripts/ci/test.sh` as needed to confirm the bootstrapped environment works; address failures immediately.
3. Fix/record:
   - Add to `log.md` what/why (non-obvious decisions), including version snapshots and any deviations.
   - Update `context.md`: increment `Current Step`, set `Next Action`.
   - Check `main` for stray files from our branch.
4. Commit: `git add .` then `git commit -m "feat(scope): subject [protocol-0002/02]"`. Push.
5. Report to the user using the step report format above.