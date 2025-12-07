# Step 03: Run demo workflow

## Briefing
- **Goal:** Execute the real end-to-end demo app workflow using TasksGodzilla components and capture outputs.
- **Key files:**
  - `scripts/api_server.py`
  - `scripts/rq_worker.py`
  - `tasksgodzilla/` job definitions and configs
  - `scripts/ci/test.sh` (for smoke or integration coverage)
- **Additional info:** Use fakeredis and SQLite defaults unless the chosen workflow requires different backends. Capture run IDs, logs, and any generated artifacts.

## Sub-tasks
1. Define the demo scenario
   - Pick a concrete workflow from docs/tests (e.g., a known sample job or protocol case) and note the target entrypoint (CLI vs API).
   - Capture expected input payload shape, required headers/auth (if any), and the observable success criteria (status, output fields, artifacts).
   - Decide where to persist run artifacts/logs (e.g., `./.protocols/0002-demo-app-workflow/artifacts/step-03/`).
2. Prep environment and shells
   - Confirm `.venv` exists and dependencies are installed from Step 02; ensure no other API/worker processes occupy port 8010 or Redis URL.
   - Export required env vars in both API and worker shells (e.g., `TASKSGODZILLA_DB_PATH=/tmp/tasksgodzilla-ci.sqlite`, `TASKSGODZILLA_REDIS_URL=fakeredis://`, `TASKSGODZILLA_API_TOKEN=<if needed>`).
   - Open two terminals (API, worker) plus one control terminal for triggering/monitoring; note current working directory in each.
3. Start API server
   - In API terminal, run `.venv/bin/python scripts/api_server.py --host 0.0.0.0 --port 8010`.
   - Verify readiness (e.g., quick HTTP GET to a health endpoint or observing “running” log line); save logs to file if possible.
4. Start worker
   - In worker terminal, run `.venv/bin/python scripts/rq_worker.py` with the same env vars to ensure it binds to the fakeredis/SQLite config.
   - Confirm it connects to Redis and is waiting for jobs; capture startup logs.
5. Trigger the demo workflow
   - From control terminal, submit the chosen payload via the decided interface (CLI script, curl/httpx POST to API, or test helper).
   - Record any returned identifiers (job/run IDs, queue names) and timestamps.
6. Monitor and collect evidence
   - Watch API and worker logs for acceptance, processing, completion, and any errors; capture durations and output artifacts.
   - If artifacts/files are produced, move or copy references to the artifacts folder and note paths.
7. Validate via tests (if applicable)
   - Run `scripts/ci/test.sh` or targeted `pytest` cases covering the same path to confirm no regressions; capture pass/fail and key output.
8. Record outcomes
   - Append to `log.md` the scenario, payload summary, env vars used (non-secret), run IDs, log file locations, artifacts, and observed results (pass/fail plus notes).

## Workflow
1. Execute sub-tasks in order; keep API/worker terminals open until completion.
2. Verify: run `lint`, `typecheck`, `test` (scope as needed). Fix failures.
3. Fix/record:
   - Add to `log.md` what/why (non-obvious decisions).
   - Update `context.md`: increment `Current Step`, set `Next Action`.
   - Check `main` for stray files from our branch.
4. Commit: `git add .` then `git commit -m "feat(scope): subject [protocol-0002/03]"`. Push.
5. Report to user using the step report format above.