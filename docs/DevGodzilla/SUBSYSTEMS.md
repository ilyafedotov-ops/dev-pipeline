# DevGodzilla Backend Subsystems

> Status: Active
> Scope: Current backend subsystem boundaries, responsibilities, and ownership points for contributors
> Source of truth: `devgodzilla/api/`, `devgodzilla/services/`, `devgodzilla/db/`, `tests/`, active docs under `docs/DevGodzilla/`
> Last updated: 2026-04-20

## Architectural Rule of Thumb

The backend is intentionally layered:

- `devgodzilla/api/` composes HTTP, SSE, and WebSocket routes plus dependency injection.
- `devgodzilla/services/` owns orchestration and business logic.
- `devgodzilla/db/` persists system state and is the coordination boundary across processes.
- filesystem artifacts and Windmill are supporting runtimes, not the primary source of truth.

When code drifts, prefer the service and DB contracts over old narrative docs.

## API Composition

Primary files:

- `devgodzilla/api/app.py`
- `devgodzilla/api/dependencies.py`
- `devgodzilla/api/routes/*.py`

Responsibilities:

- build the FastAPI app and lifespan hooks
- dual-mount routers at `/api/v1` and root
- apply API-token and webhook-token dependencies
- expose health, metrics, and compatibility surfaces

Startup hooks currently handle:

- engine bootstrap
- DB schema initialization
- event-bus DB sink installation
- agent-default migration into DB
- stuck protocol recovery
- sprint event-handler registration
- path-contract validation
- optional OpenTelemetry initialization

## Project and Specification Subsystem

Primary files:

- `services/specification.py`
- `services/clarifier.py`
- `services/policy.py`
- `services/template_manager.py`
- `api/routes/projects.py`
- `api/routes/project_speckit.py`
- `api/routes/specifications.py`
- `api/routes/templates.py`

Responsibilities:

- onboarding repositories and `.specify/`
- managing constitutions and effective policy
- generating spec/plan/tasks/checklist/analyze artifacts
- persisting spec-run state and cross-project specification inventory
- handling clarifications and repo-level policy findings

Key invariant:

- project-scoped SpecKit routes are the primary implementation surface; `/speckit/*` wrappers should stay thin.

## Orchestration and Planning Subsystem

Primary files:

- `services/orchestrator.py`
- `services/planning.py`
- `services/protocol_generation.py`
- `services/spec_to_protocol.py`
- `services/worktree.py`
- `services/workspace_paths.py`
- `api/routes/protocols.py`

Responsibilities:

- create protocol runs
- materialize steps from protocol specs or SpecKit tasks
- resolve worktrees and protocol roots
- select runnable steps using dependency and priority order
- integrate with Windmill flow generation when configured
- complete, fail, pause, resume, cancel, or recover protocol runs

Key invariant:

- protocol completion is determined from persisted step state, not from UI assumptions or only from Windmill status.

## Execution and QA Subsystem

Primary files:

- `services/execution.py`
- `services/quality.py`
- `services/agent_config.py`
- `services/constitution.py`
- `api/routes/steps.py`
- `api/routes/quality.py`
- `api/routes/agents.py`

Responsibilities:

- resolve engines, models, prompt templates, and sandbox settings
- execute a step inside the correct workspace
- detect blocking conditions before or after execution
- run QA gates and aggregate verdicts
- persist QA results and human-readable reports
- expose agent defaults, assignments, prompts, and per-project overrides

Key invariant:

- QA is part of the execution lifecycle, not a detached report-only subsystem. Its verdicts feed back into step and protocol status.

## Brownfield and Agile Delivery Subsystem

Primary files:

- `services/task_cycle.py`
- `services/sprint_integration.py`
- `services/task_sync.py`
- `services/onboarding_queue.py`
- `api/routes/brownfield.py`
- `api/routes/sprints.py`
- `api/routes/tasks.py`

Responsibilities:

- run end-to-end brownfield feature generation
- seed task-cycle metadata and curate work-item context packs
- synchronize protocol/spec artifacts into sprint and task rows
- expose backlog metrics, velocity, and sprint completion flows

Key invariant:

- task-cycle state rides on top of protocol and step records; it is not a separate orchestration system.

## Events, Operations, and Observability Subsystem

Primary files:

- `services/events.py`
- `services/event_persistence.py`
- `services/telemetry.py`
- `services/health.py`
- `services/reconciliation.py`
- `services/cli_execution_tracker.py`
- `api/routes/events.py`
- `api/routes/logs.py`
- `api/routes/runs.py`
- `api/routes/metrics.py`
- `api/routes/reconciliation.py`
- `api/routes/cli_executions.py`
- `api/routes/webhooks.py`

Responsibilities:

- in-process event publication plus DB persistence
- SSE and WebSocket event streaming
- run and CLI execution inspection
- Prometheus and JSON metrics
- health checks
- webhook ingestion
- reconciliation of DB state with Windmill state
- optional OpenTelemetry tracing

Key invariant:

- persisted DB events are the replayable event history; the in-process bus alone is not durable.

## Windmill Integration Subsystem

Primary files:

- `devgodzilla/windmill/client.py`
- `api/routes/windmill.py`
- Windmill asset exports under `windmill/`

Responsibilities:

- queue and inspect Windmill jobs and flows
- map Windmill job state into backend job-run state
- support webhook-driven advancement and reconciliation
- keep Windmill scripts as API adapters instead of importing backend internals directly

Key invariant:

- the backend remains the business-logic owner. Windmill is an execution runtime and operator surface.

## Contributor Notes

- Keep route modules thin; push branching business rules into services.
- If a change affects both DB state and runtime artifacts, update the DB contract first and let artifacts reflect it.
- Prefer extending existing services before creating new cross-cutting subsystems with overlapping responsibilities.
