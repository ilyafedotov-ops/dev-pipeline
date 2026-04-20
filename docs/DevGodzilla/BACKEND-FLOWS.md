# DevGodzilla Backend Flows

> Status: Active
> Scope: Implemented backend lifecycle flows across API, services, DB, filesystem, and Windmill integration
> Source of truth: `devgodzilla/api/routes/*.py`, `devgodzilla/services/*.py`, `tests/test_*workflow*`, `tests/test_*api*.py`
> Last updated: 2026-04-20

## Flow Topology

The backend has five primary delivery flows:

1. project onboarding
2. SpecKit artifact generation
3. protocol planning and step execution
4. brownfield task-cycle delivery
5. sprint/task synchronization

Every flow is DB-first. Windmill, agent CLIs, and filesystem artifacts extend the flow, but the persisted project, protocol, step, spec-run, event, QA, and job-run records are the coordination surface.

## 1. Project Onboarding

Entry points:

- `POST /projects`
- `POST /projects/{id}/actions/onboard`
- `POST /projects/{id}/onboarding/actions/start`
- `GET /projects/{id}/onboarding`

Sequence:

1. Create or load the project record.
2. Resolve or clone the repository, using the project-scoped GitHub token if one is stored.
3. Check out the requested branch or `project.base_branch`.
4. Initialize `.specify/` and constitution content through `SpecificationService`.
5. Optionally run discovery and persist discovery artifacts/log paths.
6. Persist onboarding events so the status endpoint can report progress even when work moves to the background.

Important behavior:

- Onboarding attempts a synchronous fast path first.
- If that path fails or is too slow, the route returns `202 Accepted` and continues in a background task.
- Auto-onboarding from `POST /projects` may queue work through Windmill when configured, otherwise it falls back to in-process onboarding.

## 2. SpecKit Artifact Flow

Entry points:

- Project-scoped: `/projects/{id}/speckit/*`
- Compatibility: `/speckit/*`

Sequence:

1. `init` seeds `.specify/` structure and constitution content.
2. `specify` creates a `SpecRun`, worktree metadata, and `spec.md`.
3. `plan` derives `plan.md`, data-model, and contract artifacts.
4. `tasks` derives `tasks.md` and task counts.
5. Optional `clarify`, `checklist`, and `analyze` extend the same `SpecRun`.
6. `implement` converts spec artifacts into a protocol run and runtime protocol tree.
7. `cleanup` removes worktree state after terminal handling; `stop` forcibly terminates transitional runs.

Important behavior:

- The implementation is agent-assisted inside `SpecificationService`; there is no required external `specify` binary on the main code path.
- Compatibility routes try synchronous execution and fall back to background execution with `202 Accepted`.
- Failure hardening matters: the backend updates affected `SpecRun` rows to `failed` instead of leaving them in transitional statuses.

## 3. Protocol Planning and Execution

Entry points:

- `POST /protocols`
- `POST /projects/{project_id}/protocols`
- `POST /protocols/from-spec`
- `POST /protocols/{id}/actions/start`
- `POST /protocols/{id}/actions/run_next_step`
- `POST /steps/{id}/actions/execute`
- `POST /steps/{id}/actions/qa`

Planning sequence:

1. Create a `ProtocolRun` in `pending`.
2. `PlanningService.plan_protocol()` loads the project, policy, and clarifications.
3. It resolves workspace and protocol roots and creates a worktree when needed.
4. If runtime step files are missing and auto-generation is enabled, protocol files may be generated first.
5. It validates the protocol spec, materializes `StepRun` rows, and sets the protocol to `planned`.
6. In Windmill mode, the orchestrator can generate or start a Windmill flow; in local mode, services execute in-process.

Execution sequence:

1. `OrchestratorService.enqueue_next_step()` or `/steps/{id}/actions/execute` selects a runnable step based on dependencies and priority.
2. `ExecutionService.execute_step()` resolves engine/model/prompt/workspace context.
3. Policy blocking and open clarifications can stop execution before the engine runs.
4. Successful execution writes runtime artifacts and usually advances the step to `needs_qa`.
5. `QualityService.run_qa()` aggregates gate results, persists verdicts, and maps the outcome back into step and protocol state.
6. `OrchestratorService.check_and_complete_protocol()` closes the protocol when all steps are terminal.

Important behavior:

- `GET /protocols/{id}/next-step` previews the next runnable step without execution.
- QA failure or QA error blocks the protocol and marks the step as failed.
- Completion is driven by terminal step state, not by Windmill alone.

## 4. Brownfield Task-Cycle Flow

Entry points:

- `POST /projects/{project_id}/brownfield/run`
- `GET /projects/{project_id}/task-cycle`
- `/work-items/{id}/*`

Sequence:

1. `TaskCycleService.start_brownfield_run()` uses the same SpecKit pipeline: specify -> plan -> tasks.
2. `output_mode=tasks_only` returns after artifacts are generated and does not create a protocol or sprint.
3. `output_mode=tasks_to_sprint` imports generated tasks into the requested sprint through `TaskSyncService`.
4. `output_mode in {protocol, task_cycle, protocol_to_sprint}` creates a protocol through `SpecToProtocolService`.
5. Only `output_mode=task_cycle` seeds task-cycle metadata into step runtime state and auto-advances the first runnable step so the board is actionable immediately.
6. `output_mode=protocol_to_sprint` creates a sprint from the protocol and can auto-sync protocol tasks into that sprint through `SprintIntegrationService`.
7. Each task-cycle step is exposed as a work item with task-cycle status, context state, review state, QA state, and artifact references.
8. Work-item actions build curated context packs, execute implementation, run review, run QA, and mark PR readiness.

Important behavior:

- `POST /projects/{project_id}/brownfield/run` is a compound intent endpoint, not just a task-cycle launcher.
- The route may return `202 Accepted` for slow runs and includes a mode-specific `poll_hint` so callers can poll the right resource.
- Task-cycle state is persisted in step runtime state rather than in a separate table.
- `protocol` mode creates a protocol without task-cycle auto-advance.
- Artifact references under each work item are part of the contract; UI and Windmill scripts should treat them as generated runtime paths, not hand-authored docs.

## 5. Sprint and Task Sync Flow

Entry points:

- `/sprints/*`
- `/tasks/*`
- `POST /protocols/{id}/actions/create-sprint`
- `POST /protocols/{id}/actions/sync-to-sprint`
- `POST /sprints/{id}/actions/link-protocol`
- `POST /sprints/{id}/actions/sync-from-protocol`
- `POST /sprints/{id}/actions/import-tasks`
- `POST /specifications/{id}/link-sprint`

Sequence:

1. A protocol can create or attach to a sprint via `SprintIntegrationService`.
2. Task markdown is parsed and synchronized into agile task rows.
3. Sprint metrics and velocity are computed from the persisted task set.
4. Specifications may link to sprints directly or indirectly through task labels and task membership.

Important behavior:

- Sprint/task sync is derived from protocol/spec artifacts plus DB rows. There is no separate planner-only truth source.
- Tests cover the UI-facing contracts for linked sprint naming, task import, and update reflection.

## 6. Webhooks, Recovery, and Reconciliation

Entry points:

- `/webhooks/windmill/*`
- `/webhooks/github`
- `/webhooks/gitlab`
- `/reconciliation/*`

Sequence:

1. Windmill job and flow webhooks update `JobRun` state and may complete a protocol.
2. CI failure webhooks can block a protocol.
3. CI success webhooks can ask the orchestrator to enqueue the next step when no step is in flight.
4. `ReconciliationService` compares active DB step state with Windmill job state and auto-fixes safe drift.
5. On API startup, `recover_stuck_protocols()` runs best-effort recovery for stale protocol state.

Important behavior:

- Reconciliation only inspects active steps by default.
- Auto-fix is conservative; mismatches outside safe mappings are reported as manual follow-up.
- Webhooks are operational inputs to the orchestrator, not just audit signals.
