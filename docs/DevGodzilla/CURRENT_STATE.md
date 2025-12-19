# DevGodzilla Current State (What Runs Today)

This document describes the **actual** DevGodzilla runtime and workflow in this repository, as of 2025-12-17.

If you’re looking for aspirational design/roadmaps, start with:
- `docs/DevGodzilla/ARCHITECTURE.md`
- `docs/DevGodzilla/ARCHITECTURE_REVIEW.md`

## Runtime Topology (Docker Compose)

Default stack (`docker compose up --build -d`) runs:
- `nginx`: single entrypoint for UI + API
- `devgodzilla-api`: FastAPI service (`devgodzilla/api/app.py`)
- `windmill`: Windmill server + UI (built from `Origins/Windmill`)
- `windmill_worker` / `windmill_worker_native`: Windmill workers
- `db`: Postgres (shared by DevGodzilla + Windmill)
- `windmill_import`: one-shot job that imports local `windmill/` assets into Windmill

See: `docker-compose.yml`, `DEPLOYMENT.md`, `nginx.devgodzilla.conf`.

## Source of Truth (API + Services)

### API

DevGodzilla exposes a REST API (via nginx at `http://localhost:8080` by default).

Key route groups:
- Projects: `/projects`
- Protocols: `/protocols`
- Steps: `/steps`
- SpecKit artifacts: `/speckit/*` and `/projects/{id}/speckit/*`
- Windmill passthrough: `/flows`, `/jobs`
- Runs/artifacts (DevGodzilla job runs): `/runs`

### Services

Business logic lives under `devgodzilla/services/*` (planning, execution, quality, orchestration, git, policy, clarifications).

## Planning Model (Protocols → StepRuns)

The current planning path is **protocol-file driven**:

1. A protocol run exists in DB (`ProtocolRun`).
2. Planning reads step markdown files under:
   - `.protocols/<protocol_name>/step-*.md` (preferred), or
   - `specs/<protocol_name>/...` (SpecKit-backed runs)
3. Planning materializes `StepRun` rows from those step files.

Implementation references:
- Spec building: `devgodzilla/spec.py` (`build_spec_from_protocol_files`)
- Planning: `devgodzilla/services/planning.py` (parses protocol root, creates steps)

### Auto-generating protocol files (headless agent)

If `.protocols/<protocol_name>/step-*.md` are missing and `DEVGODZILLA_AUTO_GENERATE_PROTOCOL=true` (default), planning runs a headless agent to generate:
- `.protocols/<protocol_name>/plan.md`
- `.protocols/<protocol_name>/step-*.md`

Implementation reference:
- `devgodzilla/services/protocol_generation.py`

## SpecKit Artifacts (.specify/)

The SpecKit-style workflow in DevGodzilla is **agent-assisted**:

- `SpecificationService` creates `.specify/` structure, seeds templates, and invokes SWE agents (prompt-driven) to write:
  - `spec.md`
  - `plan.md`
  - `tasks.md`

It does **not** require an external `specify` binary for the current implementation.

Implementation reference:
- `devgodzilla/services/specification.py`

## Headless Repo Discovery (agent-written artifacts)

DevGodzilla supports a TasksGodzilla-style “discovery” phase driven by a headless agent (default engine `opencode`, default model `zai-coding-plan/glm-4.6`).

The discovery agent writes and validates these expected outputs under the repo root:
- `tasksgodzilla/DISCOVERY.md`
- `tasksgodzilla/DISCOVERY_SUMMARY.json`
- `tasksgodzilla/ARCHITECTURE.md`
- `tasksgodzilla/API_REFERENCE.md`
- `tasksgodzilla/CI_NOTES.md`

Entry points:
- API onboarding: `POST /projects/{id}/actions/onboard` with `run_discovery_agent=true`
- CLI: `devgodzilla project discover <id> --agent --pipeline`

Implementation reference:
- `devgodzilla/services/discovery_agent.py`

## Execution Artifacts (“git report”)

Step execution persists artifacts under the protocol root (in the protocol worktree):

`.protocols/<protocol_name>/.devgodzilla/steps/<step_run_id>/artifacts/*`

This includes `execution.json`, `stdout.log`, optional `stderr.log`, plus best-effort `git-status.txt` and diffs.

Implementation reference:
- `devgodzilla/services/execution.py`

## QA Completion Semantics

- `POST /steps/{id}/actions/qa` supports `"gates": []` to skip QA and still mark the step completed.
- After QA, DevGodzilla best-effort checks whether all steps are terminal and updates the protocol status to `completed` / `failed`.

Implementation references:
- `devgodzilla/services/quality.py`
- `devgodzilla/api/routes/steps.py`

## Sprint Integration (SpecKit Tasks -> Agile Board)

DevGodzilla supports bidirectional synchronization between SpecKit task definitions (markdown) and database-backed agile sprints.

- **Task Import**: `specs/<spec>/tasks.md` can be imported into a sprint via `POST /sprints/{id}/actions/import-tasks` (or Windmill `sync_tasks_to_sprint` flow).
- **Protocol Linkage**: Protocols are linked to sprints via `linked_sprint_id`.
- **Status Updates**: Step execution events (`StepCompleted`, `StepFailed`) automatically update corresponding sprint tasks and recalculate velocity.

Implementation reference:
- Service: `devgodzilla/services/sprint_integration.py`, `devgodzilla/services/task_sync.py`
- Event Handlers: `devgodzilla/services/sprint_event_handlers.py`

## Windmill Integration (Supported Pattern)

### Asset import

`windmill_import` (compose service) imports local assets into Windmill:
- `windmill/scripts/devgodzilla/` → `u/devgodzilla/*`
- `windmill/flows/devgodzilla/` → `f/devgodzilla/*`
- `windmill/apps/devgodzilla/` → apps in the workspace

### Supported execution model

**Supported**: Windmill scripts are thin API adapters that call DevGodzilla API.

Examples:
- `u/devgodzilla/protocol_plan_and_wait` (calls `/protocols/{id}/actions/start` and polls)
- `u/devgodzilla/step_execute_api` (calls `/steps/{id}/actions/execute`)
- `u/devgodzilla/step_run_qa_api` (calls `/steps/{id}/actions/qa`)
- `u/devgodzilla/onboard_to_tasks_api` (one-script pipeline alternative)

This avoids requiring the Windmill worker runtime to import the `devgodzilla` Python package.

### Supported flows

Recommended flows to use in the default stack:
- `f/devgodzilla/onboard_to_tasks`
- `f/devgodzilla/protocol_start`
- `f/devgodzilla/step_execute_with_qa`
- `f/devgodzilla/run_next_step` (selection only)

See: `docs/DevGodzilla/WINDMILL-WORKFLOWS.md`.
