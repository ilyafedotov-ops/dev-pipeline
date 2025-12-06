# Detailed Implementation Plan

This plan turns the target architecture into executable work. Phases can run sequentially or with limited parallelism when dependencies allow. Existing components in `deksdenflow/` (storage, API, queue/workers) should be reused rather than rebuilt.

## Current decisions and priorities
- Stack choice: Postgres for production (SQLite for dev/tests), Redis + RQ for the first queue/worker implementation.
- Phase 0 priorities: 0.1 (stabilize library surface) → 0.2 (thin CLIs) → 0.3 (central config) → 0.4 (logging/errors). Containerization (0.5) can trail but should land before API/worker rollout.

## Status model and QA defaults
- ProtocolRun: `pending` → `planning` → `planned` → `running` → (`paused` | `blocked` | `failed` | `cancelled` | `completed`). CI failure or job failure moves to `blocked`; PR/MR merge completes the run.
- StepRun: `pending` → `running` → `needs_qa` → (`completed` | `failed` | `cancelled` | `blocked`). Execution ends in `needs_qa`; QA or manual approval flips to `completed`; CI/webhook failures can block a step.
- Automation flags: `DEKSDENFLOW_AUTO_QA_AFTER_EXEC=true` enqueues QA immediately after execution; `DEKSDENFLOW_AUTO_QA_ON_CI=true` enqueues QA when CI success webhooks arrive.
- CI callbacks: `scripts/ci/report.sh success|failure` posts GitHub/GitLab-style payloads to the orchestrator using `DEKSDENFLOW_API_BASE` (optional `DEKSDENFLOW_API_TOKEN`/`DEKSDENFLOW_WEBHOOK_TOKEN`).
- Auth tokens: API bearer token (`DEKSDENFLOW_API_TOKEN`) gates all non-health endpoints; per-project token (`X-Project-Token`) is optional; webhook token (`DEKSDENFLOW_WEBHOOK_TOKEN`) signs/verifies CI callbacks.

## Phase 0 – Foundations and refactoring
**Goal:** Make the orchestration logic library-first, configurable, and container-ready.

- 0.1 Stabilize the core package: move shared logic from `scripts/protocol_pipeline.py`, `scripts/quality_orchestrator.py`, `scripts/project_setup.py`, and `scripts/codex_ci_bootstrap.py` into `deksdenflow.*` modules with clean APIs. Keep behaviors parity with current CLIs.
- 0.2 Thin CLIs: refactor each script to pure arg parsing plus a call into the library. Preserve flags and defaults; add unit tests around CLI entrypoints.
- 0.3 Centralize configuration: introduce a Pydantic config object for paths, model defaults, retries, budgets, and CI settings. Replace ad hoc `os.environ[...]` reads with explicit config injection.
- 0.4 Standard logging and errors: add structured logging helpers, request/correlation IDs, and typed exceptions for Codex/Git/CI failures. Normalize exit codes for CLIs.
- 0.5 Containerization: build `deksdenflow-core` image (library + CLIs) and optionally `codex-worker` image with tighter runtime limits. Document local vs. prod compose/Kubernetes layouts.

## Phase 1 – Data model and persistence
**Goal:** Introduce durable state for Projects, ProtocolRuns, StepRuns, and Events.

- 1.1 Choose DB: Postgres for prod, SQLite for dev; wire connection management and pooling.
- 1.2 Define schema: tables for projects, protocol_runs, step_runs, events with statuses, timestamps, git metadata, model selections, retries, summaries, prompt versions.
- 1.3 Migrations: set up Alembic (or similar) with versioned migrations and CLI hooks.
- 1.4 Data access layer: repositories/DAO or SQLAlchemy models for create/list/update per entity, plus event append helpers.
- 1.5 Library integration: update protocol open/run/QA flows to create/update DB rows and emit events. Ensure idempotency on retries.

## Phase 2 – Orchestrator API service
**Goal:** Single API surface for projects, protocols, and steps.

- 2.1 API skeleton: FastAPI app with health, auth middleware, and dependency injection for config/DB.
- 2.2 Endpoints: `/projects`, `/projects/{id}`, `/projects/{id}/protocols`, `/protocols/{id}`, `/protocols/{id}/steps`, `/steps/{id}` plus action endpoints (`start`, `run`, `run_qa`, `approve`, `pause/resume`, `cancel`).
- 2.3 Workflows: handlers validate input, update DB state, and enqueue jobs (Phase 3). Include optimistic concurrency to avoid double-runs.
- 2.4 Auth and tenancy: API tokens or basic auth; project/org scoping for multi-tenant readiness.
- 2.5 Docs: OpenAPI/Swagger exposed; examples for common flows; smoke tests for happy paths.

## Phase 3 – Job queue and workers
**Goal:** Offload long-running and LLM-heavy work with retries/backoff.

- 3.1 Queue selection: Redis-backed (RQ/Celery) or DB-backed queue; configure serialization, visibility timeouts, and backoff policies.
- 3.2 Job contracts: define payloads keyed by IDs (`project_id`, `protocol_run_id`, `step_run_id`). Job types: `project_setup_job`, `plan_protocol_job`, `execute_step_job`, `run_quality_job`, `open_pr_job`.
- 3.3 Codex Worker: consume planning/execution/QA jobs; assemble context; call Codex via the library; write artifacts under `.protocols/NNNN-[task]/`; update DB status/events.
- 3.4 Git/CI Worker: handle clones, worktrees, branch pushes, PR/MR creation, and CI webhook side effects. Reuse `scripts/ci_trigger.py` patterns where possible.
- 3.5 Retry/error policies: per-job max attempts, exponential backoff caps, and terminal vs. recoverable failures mapped to StepRun/ProtocolRun statuses.
- 3.6 Scheduler: periodic scan for pending/needs_qa steps to enqueue work; consider cron inside orchestrator or external scheduler.

## Phase 4 – Console and onboarding
**Goal:** First-class UI to onboard projects and manage runs.

- 4.1 UX flows: define onboarding (register project, run setup, pick models/QA strictness) and operations (project list, protocol table, step timeline).
- 4.2 TUI console (fast path): implement with Rich/Textual consuming only the API; screens for projects, protocol runs, step details, recent events; controls to start/run/rerun/QA/approve.
- 4.3 Web console (next): simple web frontend (React/Next.js or server-rendered) with auth; reuse the same API contracts and views.
- 4.4 Onboarding integration: frontend calls `/projects` to register and shows job/event progress; orchestrator enqueues `project_setup_job`.
- 4.5 Status/actions: surface buttons/shortcuts for “new protocol”, “run next step”, “retry step”, “run QA”, “open PR/MR now”, “manual approve”.

## Phase 5 – CI integration and automation loops
**Goal:** Make CI results first-class signals in orchestration.

- 5.1 Webhooks: endpoints for GitHub/GitLab with signature validation; parse CI and PR/MR events.
- 5.2 Mapping: resolve ProtocolRun/StepRun from branch names and repo; update statuses (`ci_passed`, `ci_failed`, `blocked`).
- 5.3 CI scripts: update `scripts/ci/*.sh` templates to optionally call back to the orchestrator; keep them customizable per stack.
- 5.4 Automation policies: on CI failure, mark StepRun failed and optionally spawn a “fix CI” protocol; on CI success, auto-queue QA jobs.
- 5.5 Merge flows: add protocol templates for review/merge; orchestrator can trigger these when PRs are ready.

## Phase 6 – Observability, cost, and governance
**Goal:** Operate the system with SRE-grade visibility and controls.

- 6.1 Logging and correlation: propagate correlation IDs per ProtocolRun/StepRun across API, workers, queue, and git/CI hooks.
- 6.2 Metrics: export job counts, durations, QA pass/fail, Codex token usage/cost per project, error rates by model; publish via Prometheus/OpenTelemetry.
- 6.3 Budgets and limits: enforce max tokens per step/protocol and per-project cost ceilings; alert when thresholds are breached.
- 6.4 Audit trail: persist all user actions and key AI decisions as Events for compliance.
- 6.5 Security hardening: authz per project/tenant, secrets management for git/CI/Codex credentials.

## Phase 7 – LLM-specific quality improvements
**Goal:** Improve robustness of AI behavior and reproducibility.

- 7.1 Prompt versioning: track prompt revisions and the version used for each planning/execution/QA run.
- 7.2 Offline evaluation: extend `tests/test_readme_workflow_integration.py` (or add new harness) to compare prompt/model variants when `RUN_REAL_CODEX` is enabled.
- 7.3 Fallback/ensembles: allow retries with alternate models or secondary QA prompts for critical steps.
- 7.4 Guardrails: validate Codex outputs beyond JSON schema (sanity checks on step descriptions/QA verdicts) before accepting them into the state machine.
