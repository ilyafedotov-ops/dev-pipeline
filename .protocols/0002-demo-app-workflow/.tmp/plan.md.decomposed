# 0002 — demo-app-workflow

## ADR-style Summary:
- **Context**: Real end-to-end demo app workflow harness run across TasksGodzilla stack in a dedicated worktree.
- **Problem Statement**: We need a reproducible plan to prepare the environment, run the demo workflow end-to-end, and capture outputs.
- **Decision**: Follow a structured multi-step protocol covering setup, environment bootstrap, execution, validation, and closeout.
- **Alternatives**: (1) Skip full E2E and rely on unit tests only; (2) Run partial components without workers/API; (3) Use synthetic mocks instead of fakeredis/SQLite.
- **Consequences**: Produces traceable artifacts, clear exit criteria, and validated harness outputs at the cost of extra setup and runtime.

---

## High-Level Plan:
This section is a **contract**; do not change during implementation.

- **[Step 0: Prepare and lock plan](./00-setup.md)**: Create and commit protocol artifacts.
- **[Step 1: Review scope and baseline](./01-review-and-scope.md)**: Read requirements, map the demo flow, and capture baseline repo state.
- **[Step 2: Bootstrap environment](./02-bootstrap-environment.md)**: Set up Python tooling, dependencies, and env vars for the demo run.
- **[Step 3: Run demo workflow](./03-run-demo-workflow.md)**: Start services and execute the end-to-end harness; capture outputs and logs.
- **[Step 4: Validate and stabilize](./04-validate-and-stabilize.md)**: Verify results, run CI checks, and address issues or document gaps.
- **[Step 5: Finalize](./05-finalize.md)**:
  * Mark PR Ready
  * Close out work

---

## Step Breakdown (Sub-tasks)
### Step 0: Prepare and lock plan
1. Read `AGENTS.md`, this `plan.md`, and the current `context.md` to confirm scope and the current step.
2. Ensure `.protocols/0002-demo-app-workflow` exists with `plan.md`, step files, and `context.md` tracked; create missing folders/files if needed.
3. Verify git status is clean; record current branch and HEAD in notes for traceability.
4. If any setup files changed, stage and commit per commit style; update `log.md` with the plan lock reference.

### Step 1: Review scope and baseline
1. Review `00-setup.md` outcome and read `01-review-and-scope.md` to list required artifacts and success criteria.
2. Skim key project docs: `README`, `AGENTS.md`, `scripts/ci/*`, `tasksgodzilla/config`, and any demo-related docs in `docs/` or `prompts/`.
3. Map the end-to-end demo flow: identify entrypoints (`scripts/api_server.py`, `scripts/rq_worker.py`), required env vars, data paths, and expected outputs/logs.
4. Capture baseline state: note git status, active branch, and current commit hash; record any existing artifacts or sample data relevant to the demo.

### Step 2: Bootstrap environment
1. Confirm Python 3.12 availability; create/activate `.venv` via `scripts/ci/bootstrap.sh` (installs requirements and `ruff`).
2. Set env defaults for local run: `TASKSGODZILLA_DB_PATH=/tmp/tasksgodzilla-ci.sqlite`, `TASKSGODZILLA_REDIS_URL=fakeredis://`, and any API tokens or URLs required by the harness.
3. Validate tooling: ensure `python`, `pip`, `ruff`, and `pytest` are available in the venv; note versions if discrepancies arise.
4. Run a quick import/compile smoke: `python -m compileall tasksgodzilla scripts` (or rely on `scripts/ci/typecheck.sh`) to catch missing deps early.
5. Document the bootstrap result and any manual steps in `log.md`; update `context.md` if moving to the next step.

### Step 3: Run demo workflow
1. Prepare runtime folders and sample inputs needed by the demo; ensure DB and Redis URLs point to local SQLite/fakeredis.
2. Start API server (`scripts/api_server.py`) with the configured env; capture logs to a file under `.protocols/0002-demo-app-workflow/logs`.
3. Start worker (`scripts/rq_worker.py`) under the same env; confirm it connects to fakeredis and the SQLite DB.
4. Trigger the demo workflow harness (CLI or API request per `03-run-demo-workflow.md`): submit the job, watch progress, and collect outputs/artifacts (responses, generated files, logs).
5. On completion, gracefully stop services; archive run artifacts (logs, outputs, timestamps, commands used) under the protocol folder.

### Step 4: Validate and stabilize
1. Verify demo results against expectations: check output correctness, logs for errors, and any generated artifacts.
2. Run CI scripts locally: `scripts/ci/typecheck.sh`, `scripts/ci/lint.sh`, `scripts/ci/test.sh`; note pass/fail and remediate issues.
3. Fix defects found during validation or demo run; re-run affected checks until green.
4. Summarize findings, gaps, and remaining risks in `log.md`; update `context.md` to reflect current status and next step.

### Step 5: Finalize
1. Ensure workspace cleanliness: no stray files, services stopped, and git status clean except intended changes.
2. Stage changes and commit with `type(scope): subject [protocol-0002/YY]`; confirm push readiness and branch tracking.
3. Update `log.md` with final actions and commit hash; refresh `context.md` to indicate protocol completion.
4. Prepare final report per the required format (Done/Checks/Git/Working directory/Protocol status); if applicable, mark PR ready and link.
5. Hand off artifacts (logs, outputs, instructions) stored in `.protocols/0002-demo-app-workflow` for future reference.

---

## Protocol Workflow (How to execute)
Follow `High-Level Plan` and this cycle for each step.

- **PROJECT_ROOT**: /home/ilya/Documents/dev-pipeline
- **CWD (worktree)**: /home/ilya/Documents/worktrees/0002-demo-app-workflow
- **Protocol folder**: /home/ilya/Documents/worktrees/0002-demo-app-workflow/.protocols/0002-demo-app-workflow

All work happens in the worktree (CWD).

### A. Before a new step (restore context)
1. Read `Current Step` from `context.md`.
2. Open the step file (e.g., `01-step-name.md`).
3. Ensure previous changes are committed.

### B. During the step (execute)
1. Do the sub-tasks in the step file.
2. Do **not** change plan files (`plan.md`, `XX-*.md`). They are the contract.
3. Follow Generic Principles below.

### C. After the step (verify & fix)
1. Run checks: `typecheck`, `lint`, `test`. Fix until green.
2. Add a `log.md` entry describing what and why (include commit ID).
3. Rewrite `context.md` for the next step.
4. Verify `main` has no stray files from our branch. Commit with `type(scope): subject [protocol-0002/YY]`. Push.
5. Report to the user in the format:
<report_format>
(Protocol, step):

**Done**: what/where/why (also in Log).

**Checks**: which ran (lint/typecheck/test), pass/fail, why.

**Git**: PR link; current branch; commit message; push status; main-branch cleanliness check.

**Working directory**: absolute CWD path.

**Protocol status**: where we are and what’s next.
</report_format>

---

## Generic Principles (MUST follow, shared)
- Balance & simplicity; avoid overengineering.
- No legacy; greenfield decisions allowed.
- Respect coding standards/linters/formatters/JSDoc.
- Keep docs current (Memory Bank), atomic.
- Quality tests: positive/negative/boundaries; reuse helpers.
- Detail & decomposition: plans executable without this chat.

---

## Reference Materials
- AGENTS and repository guidelines in `AGENTS.md`.
- Build/test scripts under `scripts/ci/*.sh` (bootstrap, lint, typecheck, test, build).
- Runtime entrypoints: `scripts/api_server.py`, `scripts/rq_worker.py`; config via `tasksgodzilla.config.load_config`.
- Project docs in `docs/`, prompts in `prompts/`, schemas in `schemas/`, migrations in `alembic/`.