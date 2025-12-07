# Step 01: Review scope and baseline

## Briefing
- **Goal:** Confirm objectives, identify the demo workflow path, and capture current repo/branch state before execution.
- **Key files:**
  - `README.md`, `docs/`
  - `tasksgodzilla/` (jobs, orchestrator, API, worker)
  - `scripts/` (protocol pipeline, CI helpers)
- **Additional info:** Paths are relative to `/home/ilya/Documents/dev-pipeline`. Keep notes in `log.md` about assumptions and selected demo scenario.

## Sub-tasks
1. Background scan
   - Read `AGENTS.md` for repo conventions and CI expectations.
   - Skim `README.md` plus any `docs/` and `prompts/` sections that describe the demo or protocol pipeline.
   - Note any prescribed env vars, services, or entrypoints mentioned.
2. Identify candidate demo workflow
   - Inspect `tasksgodzilla/jobs/`, `tasksgodzilla/api/`, and `tasksgodzilla/workers/` for existing job definitions and orchestrations.
   - Check `tests/` for example payloads or end-to-end style cases that reveal the intended demo flow.
   - Decide which job/workflow to run for the demo; capture its inputs, outputs, and success signals.
3. Baseline repository state
   - Run `git status -sb` to record branch and dirty files; note any pre-existing changes to preserve.
   - If needed, record the current commit (e.g., `git rev-parse --short HEAD`) for traceability.
4. Dependencies and fixtures
   - List required services (fakeredis, SQLite path from `TASKSGODZILLA_DB_PATH` or `TASKSGODZILLA_DB_URL`) and any sample payloads/fixtures needed.
   - Identify scripts/commands used to start components (e.g., `scripts/api_server.py`, `scripts/rq_worker.py`) and CI helpers (`scripts/ci/*.sh`) relevant to the chosen workflow.
5. Document scope and criteria
   - Write a brief note in `log.md` capturing the chosen workflow, assumptions, env vars, and expected success criteria/artifacts (logs, outputs).
   - Note any open questions or risks to resolve in later steps.

## Workflow
1. Execute sub-tasks.
2. Verify: run `scripts/ci/lint.sh`, `scripts/ci/typecheck.sh`, `scripts/ci/test.sh` (scope as needed). Fix failures.
3. Fix/record:
   - Add to `log.md` what/why (non-obvious decisions).
   - Update `context.md`: increment `Current Step`, set `Next Action`.
   - Check `main` for stray files from our branch.
4. Commit: `git add .` then `git commit -m "feat(scope): subject [protocol-0002/01]"`. Push.
5. Report to user using the step report format above.