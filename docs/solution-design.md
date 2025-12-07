# Detailed Solution Design

This document captures the current state of the system, the risks that block full automation, and the target architecture centered on a global orchestrator and console. It is intended to sit next to `docs/architecture.md` and expand the design depth needed to drive the implementation plan.

## 1. Short review of the current design

### 1.1 Strengths
- Protocol-driven, git-first workflow. Each protocol lives in its own worktree/branch under `.protocols/NNNN-[task]/`, giving deterministic naming, isolation, and traceability.
- Codex CLI as the core engine. `protocol_pipeline.py` enforces a JSON schema for planning and step decomposition; `quality_orchestrator.py` builds rich QA context and gates pipelines via `quality-report.md` and exit codes.
- Good bootstrap story. `project_setup.py` and `codex_ci_bootstrap.py` simplify repo prep and CI hook generation; dual GitHub/GitLab CI entrypoints keep portability.
- Prompt library + schemas. Prompts live in `prompts/*.prompt.md`, separated from orchestration code, with JSON schemas defining contracts for agent output.
- Early orchestrator slice already exists. `tasksgodzilla/storage.py`, `tasksgodzilla/api/app.py`, and `scripts/api_server.py` show the direction and reduce greenfield risk.

### 1.2 Risks and pain points (especially for full automation)
- No persistent global orchestrator. State is fragmented across Git branches/worktrees, `.protocols/` folders, and CI logs; there is no service that understands Projects, ProtocolRuns, Steps, and lifecycle.
- CLI/CI-only control surface. Power-user friendly but hard to scale or integrate. There is no API to open/resume protocols, run QA, or list failing steps across projects.
- Limited observability and cost tracking. No central metrics for Codex usage, protocol/step success rates, durations, or QA patterns; hard to do SRE/governance.
- CI is wired but not orchestrated. `scripts/ci/*.sh` are stubs; there is no feedback loop where CI outcomes change orchestration decisions.
- No first-class console or onboarding UI. Onboarding relies on scripts/docs; there is no console to register projects, select models, or see live protocol runs.
- Coupled to local filesystem layout. Assumes `../worktrees/` and `.protocols/` on disk, which complicates multi-tenant or multi-runner deployments.

## 2. Improved target architecture (global orchestrator + console)

### 2.1 Control-plane overview
- User interacts via a central console (initially TUI, later web) that calls an Orchestrator API.
- Orchestrator API (FastAPI) owns state machines for Projects, ProtocolRuns, and StepRuns and persists to a database (Postgres in prod, SQLite for dev).
- A job queue sits between the API and workers. Workers handle long-running or LLM-heavy work with retries/backoff.
- Workers are split by concern: an execution/QA worker that plans/executes/QA via the engine registry (Codex + CodeMachine) and a Git/CI worker (clones, worktrees, pushes, PR/MR, CI webhooks). Both call the shared `tasksgodzilla` library functions instead of shelling out directly.
- Events and metrics are emitted throughout to enable observability and cost controls.

### 2.2 Core components
- **Orchestrator API service**: Stateless FastAPI app exposing REST/GraphQL endpoints for project/protocol/step CRUD and actions (`start`, `run`, `run_qa`, `approve`, `pause/resume`). Auth via API tokens initially; multi-tenancy via project/org tags.
- **Persistence layer**: Projects, ProtocolRuns, StepRuns, Events stored in Postgres/SQLite with migrations (Alembic). Fields include git metadata, model selection, retries, timestamps, and summaries. Prompt versions/config are recorded for auditability.
- **Job queue**: Redis/RQ/Celery or a DB-backed queue. Payloads carry only IDs; workers fetch context from the database. Per-job retry limits and exponential backoff govern behavior.
- **Workers**:
  - Execution/QA Worker: uses ProtocolSpec/StepSpec and the engine registry (Codex + CodeMachine) to plan/decompose, resolve prompts/outputs, execute steps, and run QA; creates worktrees/protocol folders; writes artifacts; updates DB state; emits Events.
  - Git/CI Worker: manages clones (persisting resolved local paths), worktrees, branch pushes, PR/MR creation, remote branch cleanup/listing, and processes CI/webhook signals to update statuses.
- **Console**:
  - TUI (Rich/Textual) first for speed, consuming only the API.
  - Web UI later (React/Next.js or server-rendered) with dashboards, step timelines, QA verdicts, and controls to run/retry/approve steps.
- **Onboarding wizard**: Frontend flow to register projects (git URL, base branch, CI platform, model defaults) and trigger `project_setup` jobs; displays progress via Events.

### 2.3 Domain model
- **Project**: id, name, git_url, base_branch, CI provider, persisted `local_path` (resolved clone path), enabled protocol templates, default models/configs, org/team tags.
- **ProtocolRun**: id, project_id, protocol_name (`NNNN-[task]`), status (`pending`, `planning`, `planned`, `running`, `blocked`, `failed`, `completed`), base_branch, worktree_path, protocol_root.
- **StepRun**: id, protocol_run_id, step_index, step_type (`setup`, `work`, `qa`), status, retries, Codex model used, last result summary.
- **Event**: timestamped log with actor/context: step started/completed, QA verdicts, CI signals, approvals, failures.

### 2.4 State machines
- **ProtocolRun lifecycle**: `pending -> planning -> planned -> running -> completed`; failures move to `blocked` (recoverable) or `failed` (terminal). CI or QA outcomes can advance or halt the run.
- **StepRun lifecycle**: `pending -> running -> needs_qa -> completed`; failures move to `failed` with optional retries/backoff. Manual `approve` can override to `completed`.
- All transitions append Events with correlation IDs to keep a full audit trail.

### 2.5 Core flows
- **Project onboarding**: Console calls `/projects` to register; orchestrator enqueues `project_setup` job to clone and run `project_setup.py`/`codex_ci_bootstrap.py`; user selects models/QA strictness; project shows as ready.
  - Repos resolve via stored `local_path` or namespaced clones under `TASKSGODZILLA_PROJECTS_ROOT`; onboarding records the path, configures git origin/identity when env vars are set, and emits clarifications (blocking when `TASKSGODZILLA_REQUIRE_ONBOARDING_CLARIFICATIONS=true`) for CI/model/branch policy choices.
- **Open a protocol**: `/projects/{id}/protocols` creates a ProtocolRun; orchestrator enqueues `plan_protocol` to run planning/decomposition; artifacts live under `.protocols/NNNN-[task]/`.
- **Execute steps**: `/steps/{id}/actions/run` dispatches execution; the execution worker resolves prompts/outputs from the StepSpec and dispatches via the engine registry; status and summaries recorded; optional auto-PR/MR via Git/CI Worker.
- **QA loop**: `/steps/{id}/actions/run_qa` builds the QA context and runs the validator prompt; verdict updates StepRun and may block/unblock the protocol.
- **CI integration**: GitHub/GitLab webhooks mapped by branch name update StepRun/ProtocolRun status (`ci_passed`, `ci_failed`); automation policies can trigger follow-up protocols (e.g., fix CI).
- **Console controls**: Start/resume protocol, run next step, rerun with a different model, run QA only, mark manually approved, open PR/MR, view events/metrics.

### 2.6 Configuration and safety
- Central config (Pydantic) for paths, model defaults, retries, cost budgets, allowed models per project, max tokens per step/protocol, and step-type retry policies.
- Feature flags for prompts/model variants; prompt versions recorded per run for reproducibility.
- Secrets management for git/CI/Codex tokens; API auth required for non-health endpoints.

### 2.7 Observability, metrics, and governance
- Structured logging with correlation IDs per ProtocolRun/StepRun; Events persisted for timeline views and audits.
- Metrics: jobs per type/status, step/protocol durations, Codex token usage/cost by project, QA pass/fail rates, error rates by model.
- Export to Prometheus/OpenTelemetry; budget alerts when usage crosses thresholds.
- Spec validation and outputs: ProtocolSpec/StepSpec paths are validated; missing prompts/outputs emit `spec_validation_error` and block execution. Codex execution writes stdout to spec-declared protocol and aux outputs, mirroring CodeMachine artifact behavior.

### 2.8 Deployment and compatibility
- Containerized services: `tasksgodzilla-core` (API + library), `codex-worker`, `git-ci-worker`, plus Redis/DB. Local dev uses SQLite and in-process queue; prod uses Postgres and external Redis.
- Existing CLIs stay as thin wrappers over the library, keeping current workflows intact while enabling the orchestrator/console path.

### 2.9 Stack decisions (proposed defaults)
- Database: Postgres in production for durability and concurrency; SQLite for local/dev and tests.
- Queue: Redis + RQ to start (simple, Pythonic, already hinted by `scripts/rq_worker.py`); keep queue abstraction so Celery/DB-backed queues remain pluggable.
- API: FastAPI (already present) with Pydantic config for env overrides.
- Packaging: container images for API and workers; compose file for local; Kubernetes manifests later.

## 3. Current implementation alignment
- Storage and migrations: SQLite default with Postgres available via `TASKSGODZILLA_DB_URL`; Alembic scaffolding plus initial migration under `alembic/`.
- API and console: FastAPI app exposes projects/protocols/steps/events, queue stats (`/queues*`), Prometheus metrics (`/metrics`), and webhook endpoints for GitHub/GitLab; a lightweight console at `/console` surfaces projects/runs/steps/events/queues.
- Queue and workers: Redis/RQ (fakeredis in dev) with job types wired for planning, execution, QA, project setup, and PR open; background worker auto-starts when fakeredis is used. Request/step IDs, retries, and backoff are captured as events.
- Spec-driven execution: `ProtocolSpec`/`StepSpec` schema is validated and stored on runs; steps sync from the spec; execution/QA use spec-defined engines/models/prompt_refs/output maps and `qa_policy` via the shared resolver/engine registry; spec audit/backfill exists for older runs.
- CodeMachine integration: `.codemachine` workspaces can be imported via API to persist templates into ProtocolSpec/StepSpecs; execution uses the shared resolver/engine registry with placeholders/specifications, writes outputs to `.protocols` and `.codemachine/outputs`, applies loop/trigger policies (depth-limited), and honors StepSpec QA policy (skip/light/full) with events.
- Automation flags and budgets: `TASKSGODZILLA_AUTO_QA_AFTER_EXEC` and `TASKSGODZILLA_AUTO_QA_ON_CI` drive QA scheduling; token budgets (`TASKSGODZILLA_MAX_TOKENS_*` with `strict|warn|off`) gate Codex calls.
- CI callbacks: `scripts/ci/report.sh` posts GitHub/GitLab-shaped payloads to `/webhooks/*`, mapping by branch or explicit `TASKSGODZILLA_PROTOCOL_RUN_ID`. Webhook tokens and API tokens guard external access.
