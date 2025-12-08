# Services Architecture and Refactor Plan

This document captures the proposed service-oriented architecture for Tasksgodzilla and how it maps to the current codebase. It builds on the high-level view in `docs/architecture.md` and `docs/orchestrator.md` and is intended as a guide for incremental refactors.

## 1. Current services mapped to code

### User Console (WEB / TUI / CLI)
- Web/API: `tasksgodzilla/api/app.py`, `tasksgodzilla/api/frontend`
- CLI: `tasksgodzilla/cli/main.py`, `scripts/tasksgodzilla_cli.py`
- TUI: `tasksgodzilla/cli/tui.py`, `tui`, `tui-rs`, `scripts/tasksgodzilla_tui.py`

### Orchestrator (head observer / control plane)
- Orchestration and pipelines: `tasksgodzilla/pipeline.py`, `tasksgodzilla/workers/codex_worker.py`
- Lifecycle helpers: `tasksgodzilla/domain.py`, `tasksgodzilla/run_registry.py`
- Engine routing: `tasksgodzilla/engine_resolver.py`, `tasksgodzilla/engines*`

### Quality Monitor
- QA logic and Codex/engine integration: `tasksgodzilla/qa.py`
- CLI wrapper: `scripts/quality_orchestrator.py`
- QA policy comes from specs: `tasksgodzilla/spec.py`, used in `codex_worker.handle_execute_step`

### Onboarding services
- Project/repo setup helpers: `tasksgodzilla/project_setup.py`
- CLI entrypoints: `scripts/onboard_repo.py`, `scripts/project_setup.py`
- Worker: `tasksgodzilla/workers/onboarding_worker.py`
- DB project metadata: `tasksgodzilla/storage.py` (`create_project`, `update_project_local_path`)

### Spec Generator service
- Spec building and validation: `tasksgodzilla/spec.py`
  - Build spec from protocol files or CodeMachine config
  - Validate JSON schema and path layout
  - Materialize `StepRun` rows from spec
- Used heavily from `tasksgodzilla/workers/codex_worker.py`

### Prompts Manager service
- Prompt fingerprinting/versioning: `tasksgodzilla/prompt_utils.py`
- Prompt templates: `prompts/*`
- Prompt use sites:
  - Planning/decomposition: `tasksgodzilla/pipeline.py`, `codex_worker`
  - QA: `tasksgodzilla/qa.py`, `scripts/quality_orchestrator.py`
  - Discovery/CI bootstrap: `tasksgodzilla/project_setup.py`, `scripts/codex_ci_bootstrap.py`

### Task Execution / Worker service
- Core worker: `tasksgodzilla/workers/codex_worker.py`
  - Resolves repo/worktree, spec, prompts, and outputs
  - Enforces token budgets and records metrics
  - Executes via engine registry; pushes branches; triggers CI
  - Runs QA, applies loop/trigger policies, updates DB and events
- Other workers: `codemachine_worker.py`, `spec_worker.py`, `onboarding_worker.py`
- Shared runner abstraction: `tasksgodzilla/workers/unified_runner.py` (not yet wired everywhere)
- Queue consumption glue: `tasksgodzilla/worker_runtime.py`, `scripts/rq_worker.py`

### Queue Service
- Redis-backed queue: `tasksgodzilla/jobs.py` (`RedisQueue`, `BaseQueue`)
- Job dispatch: `tasksgodzilla/worker_runtime.py`, `scripts/rq_worker.py`
- Inline fallback and trigger enqueue logic: `codex_worker._enqueue_trigger_target`

### Logging and Metrics Service
- Logging helpers: `tasksgodzilla/logging.py`
- Metrics (tokens, etc.): `tasksgodzilla/metrics.py`, used via `_budget_and_tokens` in `codex_worker`
- Events persisted via DB: `tasksgodzilla/storage.py` (`append_event`, `list_events`, etc.)

### Decomposer Services
- Decomposition heuristics and prompts: `tasksgodzilla/pipeline.py` (`is_simple_step`, `decompose_step_prompt`)
- Reused in worker planning: decomposition loop in `codex_worker`

### DB Service
- Storage layer: `tasksgodzilla/storage.py` (SQLite/Postgres, `BaseDatabase`)
- Domain models: `tasksgodzilla/domain.py`
- Run registry for Codex jobs: `tasksgodzilla/run_registry.py`

---

## 2. Target service boundaries

The refactor goal is to move from “big workers + scripts” toward clear services with well-defined responsibilities and stable APIs. The main boundaries are:

- **Interfaces**
  - API & web console
  - CLI
  - TUI

- **Application services**
  - Orchestrator (protocol/run/step lifecycle)
  - Quality
  - Onboarding
  - Specification
  - Prompts
  - Execution
  - Decomposition

- **Platform / shared infrastructure**
  - Queue
  - Storage (DB)
  - Engines (Codex, CodeMachine, future)
  - Telemetry (logging + metrics)

---

## 3. Concrete `services` module layout

The following layout keeps existing modules intact while introducing a clear services layer under `tasksgodzilla/services/`. Each service starts small by wrapping existing functions and can gradually absorb logic from workers and scripts.

### 3.1 Interfaces

These are mostly already in place; the change is to have them call services instead of reaching into workers or storage directly.

- `tasksgodzilla/api/app.py`
  - Depends on: `OrchestratorService`, `OnboardingService`, `SpecService`, `ExecutionService`, `QualityService`, `QueueService`, `TelemetryService`.
- `tasksgodzilla/cli/main.py`
  - Wraps common operations: onboarding, starting protocols, running steps, viewing status.
- `tasksgodzilla/cli/tui.py` and `tui` / `tui-rs`
  - Consume events and metrics exposed via API or a small client wrapper.

No physical move required immediately; just change dependencies to use services.

### 3.2 Application services (`tasksgodzilla/services/…`)

**`tasksgodzilla/services/orchestrator.py`**
- Responsibilities:
  - Own the lifecycle for `Project` → `ProtocolRun` → `StepRun`.
  - Decide when to:
    - Plan a protocol.
    - Decompose steps.
    - Execute steps.
    - Run QA.
    - Apply loop/trigger policies and enqueue follow-up work.
  - Translate between external actions (API/CLI calls, queue jobs) and internal services.
- Depends on:
  - `SpecService`, `ExecutionService`, `QualityService`, `DecompositionService`
  - `OnboardingService`, `QueueService`, `TelemetryService`
  - Repositories built on top of `BaseDatabase`
- Initial API sketch:
  - `create_protocol_run(project_id, protocol_name, description, base_branch, template_source) -> ProtocolRun`
  - `start_protocol_run(protocol_run_id) -> None` (enqueue planning job)
  - `step_completed(step_run_id, qa_verdict) -> None` (decide next steps)
  - `retry_step(step_run_id, reason) -> None`

**`tasksgodzilla/services/quality.py`**
- Responsibilities:
  - Provide a high-level `evaluate_step(step_run_id)` API.
  - Read QA policy (`skip`, `full`, `light`, etc.) from spec.
  - Build and run QA requests via `run_qa_unified` / engines registry.
  - Store verdict/report paths and emit consistent events.
- Depends on:
  - `tasksgodzilla/qa.py` (implementation details)
  - `SpecService`, `PromptService`, `QueueService`, `TelemetryService`
- Initial API sketch:
  - `evaluate_step(step_run_id) -> QualityResult`
  - `should_evaluate(step_run_id) -> bool`

**`tasksgodzilla/services/onboarding.py`**
- Responsibilities:
  - Manage project registration and repo setup.
  - Wrap `project_setup.py` helpers into a coherent workflow.
- Depends on:
  - `tasksgodzilla/project_setup.py`
  - `Storage` / repositories
  - `TelemetryService`
- Initial API sketch:
  - `register_project(name, git_url, base_branch, ci_provider, default_models, secrets) -> Project`
  - `ensure_project_workspace(project_id) -> Path`
  - `run_discovery(project_id, strict=False) -> None`

**`tasksgodzilla/services/spec.py`**
- Responsibilities:
  - Manage ProtocolSpec / StepSpec lifecycle for a protocol run.
  - Wrap `tasksgodzilla/spec.py` helpers.
- Depends on:
  - `tasksgodzilla/spec.py`
  - Storage / repositories
  - `TelemetryService`
- Initial API sketch:
  - `build_spec_from_protocol(protocol_run_id) -> dict`
  - `build_spec_from_codemachine(protocol_run_id) -> dict`
  - `validate_and_persist_spec(protocol_run_id) -> list[str]` (returns errors)
  - `ensure_step_runs(protocol_run_id) -> int`
  - `get_step_spec(protocol_run_id, step_name) -> dict | None`

**`tasksgodzilla/services/prompts.py`**
- Responsibilities:
  - Provide a logical mapping from prompt roles to files.
  - Centralize prompt versioning using `prompt_utils`.
- Depends on:
  - `tasksgodzilla/prompt_utils.py`
  - Project config / defaults
  - `TelemetryService`
- Initial API sketch:
  - `resolve_prompt(project_id, name) -> (Path, str, version_hash)`
  - `list_prompts(project_id) -> list[dict]`

**`tasksgodzilla/services/execution.py`**
- Responsibilities:
  - Execute a single step given its `step_run_id`.
  - Encapsulate prompt resolution, engine selection, token budgeting, and output writing.
- Depends on:
  - `tasksgodzilla/engine_resolver.py`, `tasksgodzilla/engines.registry`
  - `tasksgodzilla/workers/unified_runner.py`
  - `SpecService`, `PromptService`
  - Storage / repositories
  - `TelemetryService`
- Initial API sketch:
  - `execute_step(step_run_id) -> ExecutionResult`
  - `build_execution_plan(step_run_id) -> dict` (for dry-run/inspection)

**`tasksgodzilla/services/decomposition.py`**
- Responsibilities:
  - Drive step decomposition, using current heuristics and engine.
  - Remove duplicated decomposition logic from `pipeline.py` and `codex_worker`.
- Depends on:
  - `tasksgodzilla/pipeline.py` decomposition helpers
  - `SpecService`, `PromptService`
  - Engines registry
  - `TelemetryService`
- Initial API sketch:
  - `decompose_protocol(protocol_run_id) -> dict` (metadata about decomposed/skipped steps)
  - `decompose_step(protocol_run_id, step_name) -> None`

### 3.3 Platform services (`tasksgodzilla/services/platform/…`)

**`tasksgodzilla/services/platform/queue.py`**
- Wraps `BaseQueue`/`RedisQueue` into a task-level API.
- Responsibilities:
  - Hide RQ details and inline vs Redis behavior.
  - Provide semantic queue operations instead of raw job types.
- Initial API sketch:
  - `enqueue_plan_protocol(protocol_run_id) -> Job`
  - `enqueue_execute_step(step_run_id) -> Job`
  - `enqueue_evaluate_step(step_run_id) -> Job`
  - `enqueue_onboard_project(project_id) -> Job`

**`tasksgodzilla/services/platform/storage.py`**
- Thin repository layer over `BaseDatabase`.
- Responsibilities:
  - Group project/protocol/step/event operations with invariants.
  - Offer higher-level helpers like “append event and update status atomically”.
- Initial API sketch:
  - `ProjectRepository`, `ProtocolRepository`, `StepRepository`, `EventRepository`

**`tasksgodzilla/services/platform/telemetry.py`**
- Wraps logging and metrics into a coherent API.
- Responsibilities:
  - Standard event names and payload shapes.
  - Token/cost observability.
  - Glue between DB events and log lines.
- Initial API sketch:
  - `log_protocol_event(protocol_run_id, type, message, metadata=None, step_run_id=None)`
  - `observe_tokens(phase, model, count)`
  - `record_cost(run_id, tokens, cents)`

**`tasksgodzilla/services/platform/engines.py`**
- Optionally wrap `tasksgodzilla/engines.registry` for service consumers.
- Responsibilities:
  - Centralize model/engine selection policies.
  - Provide inspection utilities for available engines and defaults.

### 3.4 Additional services (implemented during Phase 1 & 2)

**`tasksgodzilla/services/budget.py`**
- Responsibilities:
  - Token budget tracking and enforcement
  - Budget mode handling (strict/warn/off)
  - Token counting and cost calculation
- Depends on:
  - `TelemetryService`
  - Configuration for budget limits
- Initial API sketch:
  - `check_and_track(phase, model, prompt_tokens, completion_tokens, protocol_run_id, step_run_id) -> None`

**`tasksgodzilla/services/git.py`**
- Responsibilities:
  - Git and worktree operations
  - Branch management and remote operations
  - PR/MR creation via CLI or API
  - CI triggering
- Depends on:
  - `tasksgodzilla/git_utils.py`
  - `tasksgodzilla/ci.py`
  - Storage / repositories
  - `TelemetryService`
- Initial API sketch:
  - `get_branch_name(protocol_name) -> str`
  - `get_worktree_path(repo_root, protocol_name) -> tuple[Path, str]`
  - `ensure_repo_or_block(project, run, clone_if_missing, block_on_missing) -> Optional[Path]`
  - `ensure_worktree(repo_root, protocol_name, base_branch) -> Path`
  - `push_and_open_pr(worktree, protocol_name, base_branch) -> bool`
  - `trigger_ci(repo_root, branch, ci_provider) -> bool`

**`tasksgodzilla/services/codemachine.py`**
- Responsibilities:
  - CodeMachine workspace import and management
  - Wrap existing codemachine_worker implementation
  - Provide stable service API for CodeMachine operations
- Depends on:
  - `tasksgodzilla/workers/codemachine_worker`
  - Storage / repositories
  - `TelemetryService`
- Initial API sketch:
  - `import_workspace(project_id, protocol_run_id, workspace_path, job_id) -> None`

---

## 4. Refactor strategy (high level)

## 4. Refactor strategy (high level)

**Status Update (December 2025):** Phase 1 and Phase 2 are complete. The services layer is now the primary integration surface for all API and worker operations.

The existing service flows (especially in `tasksgodzilla/workers/*` and older scripts)
are known to have behavioural issues and do not need to be preserved as-is. The
new `tasksgodzilla.services.*` layer is the primary target API going forward and
may intentionally *break backwards compatibility* with the old worker helpers as
we converge on a cleaner design.

1. **Introduce services package and prefer it for new code**
   - Add and evolve `tasksgodzilla/services/__init__.py` and modules (`orchestrator.py`, `quality.py`, `onboarding.py`, `spec.py`, `prompts.py`, `execution.py`, `decomposition.py`, `platform/{queue,storage,telemetry,engines}.py`).
   - New features should call these services directly instead of reaching into workers or scripts, even if the behaviour differs from legacy flows.

2. **Update interfaces to use services**
   - API endpoints and CLI/TUI commands call service methods, not workers or low-level helpers.
   - Workers become job adapters: “deserialize payload → call service”.

3. **Aggressively pull logic from workers into services**
   - Start with clearly scoped flows:
     - Planning + spec building (`SpecService`, `DecompositionService`).
     - Single-step execution + QA (`ExecutionService`, `QualityService`).
   - Then move trigger/loop/policy decisions into `OrchestratorService`.
   - Old helper functions in `codex_worker` and related modules can be simplified or removed once API/CLI callers use the new services.

4. **Consolidate QA and decomposition**
   - Replace direct Codex CLI calls with unified engine flows where possible.
   - Ensure QA and decomposition share prompt resolution / token budgeting in services.

5. **Tighten telemetry and events**
   - Use `TelemetryService` for all tokens, costs, and high-level events.
   - Expose these through API and console for better observability.

This layout provides a clear target while allowing for deliberate, even
non-backwards-compatible refactors: the services layer becomes the stable
contract, and legacy worker implementations can be iteratively retired.
