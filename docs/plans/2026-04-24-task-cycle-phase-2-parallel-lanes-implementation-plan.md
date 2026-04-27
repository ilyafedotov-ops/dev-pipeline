# Task Cycle Phase 2 Parallel Lanes Implementation Plan

This document defines the Phase 2 implementation plan for first-class parallel task-cycle lanes in DevGodzilla.

It covers the deferred task-cycle features that are intentionally not part of v1:

- first-class parallel work-items honoring `parallel_group`
- parallel execution constrained by `cap_n`
- dependency ordering across independently scheduled lanes using `depends_on`
- an `integrator` role that exists only when multiple first-class lanes are actually implemented

This plan is written for implementation agents and backend/frontend maintainers.

## Background

Task-cycle v1 is intentionally a single-owner work-item loop.

What exists today:

- a stable task-cycle API for projected work-items
- single-owner execution
- helper-agent sidecars under the owner
- review and QA loops
- artifact persistence per work item

What does not exist today:

- first-class lane scheduling
- first-class multi-lane state
- lane-aware dependency execution
- a true `cap_n` scheduler for work-item lanes
- a multi-lane `integrator` role

This is explicitly deferred in [TASK-CYCLE-IMPLEMENTATION-PLAN.md](./TASK-CYCLE-IMPLEMENTATION-PLAN.md).

## Goals

Phase 2 must add true multi-lane execution without regressing the current v1 experience.

Primary goals:

1. Introduce first-class lanes derived from `parallel_group`
2. Schedule lanes concurrently up to a configured `cap_n`
3. Enforce `depends_on` across lanes and within lanes
4. Introduce an `integrator` only for real multi-lane merge scenarios
5. Preserve the current single-owner v1 path when the feature is disabled

## Non-Goals

Phase 2 should not:

- replace helper agents with first-class lanes
- move orchestration logic into Windmill scripts
- introduce fully autonomous merge-conflict resolution in the first patch
- break existing task-cycle endpoints or existing work-item consumers
- remove the current single-owner workflow path

## Current State Summary

Current implementation characteristics:

- work items are projected from `StepRun`
- `depends_on` exists on `StepRun`
- `parallel_group` exists on `StepRun`
- protocol orchestration already honors `depends_on` at the step level
- helper sidecars use bounded parallelism, but they are not workflow lanes

Current limitation:

- task-cycle has no first-class lane model
- `parallel_group` is not exposed as task-cycle scheduling semantics
- `cap_n` does not exist in task-cycle execution
- there is no lane-aware dependency scheduler
- there is no integrator runtime or artifact model

## Core Design Decision

Phase 2 should introduce a first-class lane model while keeping work items as the primary user-facing unit.

Recommended model:

- work item remains the main UI/API unit
- lane is a schedulable grouping construct above work items
- multiple work items may belong to one lane
- lanes are visible and queryable through API and UI

This is better than making lanes replace work items because:

- it preserves current task-cycle UI concepts
- it minimizes breaking API changes
- it allows gradual rollout

## Execution Semantics

### V1

- one work item is executed by one owner
- helper agents are subordinate sidecars
- no independently scheduled lanes

### Phase 2

- work items may be grouped into first-class lanes
- each lane is schedulable and stateful
- multiple lanes may run concurrently
- `depends_on` gates lane readiness
- `cap_n` limits concurrent active lanes
- `integrator` exists only when multiple lanes need synthesis or merge coordination

## Domain Model Additions

Add a first-class lane model.

Suggested backend model:

```python
@dataclass
class TaskCycleLane:
    lane_id: str
    project_id: int
    protocol_run_id: int
    parallel_group: str | None
    status: str
    owner_agent: str | None
    integrator_required: bool
    depends_on_lane_ids: list[str]
    work_item_ids: list[int]
    created_at: str
    updated_at: str
```

Suggested runtime payload:

```json
{
  "lane_id": "protocol-77-lane-auth-api",
  "parallel_group": "auth-api",
  "status": "runnable",
  "owner_agent": "codex",
  "depends_on_lane_ids": ["protocol-77-lane-shared-models"],
  "work_item_ids": [201, 202],
  "integrator_required": false
}
```

## Mapping Rules

### Lane Derivation from Steps

Recommended derivation rules:

- if `parallel_group` is `null`, the step becomes a single-step lane
- if multiple steps share the same `parallel_group`, they belong to the same lane
- intra-group `depends_on` remains within the lane
- cross-group `depends_on` becomes lane-to-lane dependency

### Lane Identity

Lane identity must be stable and reproducible.

Recommended format:

- if `parallel_group` exists:
  - `protocol-{protocol_run_id}-lane-{slug(parallel_group)}`
- if no `parallel_group`:
  - `protocol-{protocol_run_id}-lane-step-{step_run_id}`

This avoids random IDs that change across reloads.

## `cap_n` Semantics

This must be precise before implementation starts.

Recommended Phase 2 meaning:

- `cap_n` is the maximum number of first-class lanes that may be in `running` state at the same time for one task-cycle/protocol run

This does not mean:

- helper parallelism under one owner
- global worker pool size
- number of work items in one lane

### Configuration

Add:

- `DEVGODZILLA_TASK_CYCLE_LANE_CAP_N`

Default:

- `1`

Optional protocol metadata override:

- `task_cycle_lane_cap_n`

Priority order:

1. explicit protocol/task-cycle metadata override
2. project-level override if added later
3. global config default

## Dependency Semantics

### Within Lane

- preserve step-level `depends_on`
- lane is runnable only if its first executable internal step is ready
- lane completes only when all steps in the lane are terminal and successful enough for completion semantics

### Across Lanes

- if any step in lane B depends on a step in lane A, lane B depends on lane A
- a lane becomes runnable only when all predecessor lanes are completed

### Failure Semantics

- if a predecessor lane fails, dependent lanes move to `blocked`
- blocked dependent lanes may be retried only after predecessor recovery

### Validation

The lane builder must reject:

- cycles in lane dependencies
- references to missing dependency steps
- malformed `parallel_group` structures that cannot be mapped deterministically

## Integrator Role

The `integrator` must not be introduced as a cosmetic or placeholder role.

It should exist only when:

- there are multiple completed first-class lanes
- their outputs must be reconciled
- a merge or synthesis task is required

It should not exist when:

- the feature flag is off
- there is only one lane
- multiple lanes complete independently without needing synthesis

### Integrator Inputs

Create:

- `integration_input.json`
- `integration_input.md`

Content should include:

- lane summaries
- lane outputs and diffs
- shared `ContextPack`
- merge objective
- risk notes
- overlap/conflict hints

### Integrator Outputs

Create:

- `integration_report.json`
- `integration_report.md`

Output schema should include:

- verdict
- summary
- findings
- required follow-up work
- conflict areas
- confidence

## Backend Modules

Do not keep all of this in `task_cycle.py`.

Recommended new modules:

- `devgodzilla/services/task_cycle_lanes.py`
- `devgodzilla/services/task_cycle_lane_scheduler.py`
- `devgodzilla/services/task_cycle_integration.py`
- `devgodzilla/api/routes/task_cycle_lanes.py`

Recommended responsibilities:

### `task_cycle_lanes.py`

- derive lanes from protocol steps
- compute lane graph
- validate lane graph
- map step dependencies to lane dependencies

### `task_cycle_lane_scheduler.py`

- compute runnable lanes
- enforce `cap_n`
- transition lane states
- enqueue lane execution
- reconcile lane completion/failure/blocking

### `task_cycle_integration.py`

- decide whether integration is required
- build integration inputs
- run integrator agent
- persist integration artifacts
- map integrator output back to protocol/task-cycle state

## Backend API Changes

### Extend Existing Work-Item API

Extend `WorkItemOut` with:

- `lane_id`
- `lane_status`
- `parallel_group`
- `dependency_ids`
- `integration_required`
- `integrator_agent`

### New Lane Endpoints

Add endpoints:

- `GET /api/v1/protocols/{protocol_run_id}/lanes`
- `GET /api/v1/lanes/{lane_id}`
- `POST /api/v1/lanes/{lane_id}/actions/start`
- `POST /api/v1/lanes/{lane_id}/actions/retry`
- `GET /api/v1/lanes/{lane_id}/artifacts/{artifact_key}/content`

Optional:

- `GET /api/v1/protocols/{protocol_run_id}/integration`

### Existing Task-Cycle List

Extend:

- `GET /api/v1/projects/{project_id}/task-cycle`

with:

- lane counters
- lane summary payload
- next runnable lane

## Artifact Layout

Add a lane-level directory layout:

```text
.devgodzilla/task-cycle/protocols/{protocol_run_id}/lanes/{lane_id}/
```

Artifacts:

- `lane_state.json`
- `lane_summary.json`
- `lane_context.json`
- `lane_execution_log.md`
- `integration_input.json`
- `integration_report.json`

Existing work-item directories remain unchanged.

## Scheduling Algorithm

Recommended scheduler loop:

1. build lane graph
2. compute lane statuses from current work-item/step state
3. identify `runnable` lanes:
   - all predecessor lanes completed
   - no blocking clarifications/policy failures
   - lane not already running/completed/failed
4. count active running lanes
5. start up to `cap_n - running_count` runnable lanes
6. when a lane completes:
   - mark successors runnable if dependencies satisfied
7. if multiple lanes reach a merge point requiring integration:
   - create integration task and move state to `awaiting_integration`

## Agent Assignment Rules

Recommended precedence for lane owner:

1. explicit lane owner override
2. work-item owner agent if lane has one consistent owner
3. protocol default agent
4. global default agent

Integrator agent precedence:

1. explicit integrator override
2. configured integrator default
3. fail closed if integration is required and no integrator is available

## UI Plan: Next.js

Update the Task Cycle tab with lane visibility.

Add:

- lane counters
- lane groups
- dependency badges
- lane status badges
- `cap_n` summary
- integration state block when present

Requirements:

- helper agents must remain clearly subordinate to the owner
- first-class lanes must be visually distinct from helper sidecars
- work items should render inside or under lane groups

## UI Plan: Windmill

Update Windmill project detail `Task Cycle` tab with:

- lane summary strip
- lane table
- dependency display
- integrator section when present

Do not add orchestration logic to Windmill scripts.

Windmill scripts must remain thin API adapters.

## Feature Flag and Rollout

Add a rollout gate:

- `DEVGODZILLA_TASK_CYCLE_PARALLEL_LANES_ENABLED`

Behavior:

- disabled:
  - current v1 semantics remain unchanged
- enabled:
  - lane builder and scheduler are active
  - lane metadata is visible in API and UI
  - integrator may appear when required

This is required to avoid destabilizing current task-cycle behavior.

## Migration Strategy

Use additive rollout only.

Recommended approach:

1. do not rewrite existing v1 runtime state in place
2. synthesize lane metadata for old runs where possible
3. persist new lane state only for new phase-2-enabled runs at first

This reduces migration risk.

## Testing Strategy

### Backend Unit Tests

Add:

- lane derivation by `parallel_group`
- lane dependency graph derivation from `depends_on`
- cycle detection
- scheduler respects `cap_n`
- blocked dependency propagation
- integrator creation only in multi-lane merge cases

### Backend API Tests

Add:

- lane list/detail endpoints
- extended work-item payload shape
- integration endpoint behavior
- invalid lane transitions rejected

### Task-Cycle E2E Tests

Add:

- multi-lane protocol with two runnable groups
- `cap_n=2` allows two concurrent lanes and blocks the third
- dependency ordering delays downstream lane start
- integrator absent when only one lane exists
- integrator present only in merge scenario

### Frontend Tests

Add:

- lane summary rendering
- grouped work-item display
- dependency badge rendering
- `cap_n` status display
- integration panel conditional rendering

### Windmill Tests

Add:

- app JSON contract for lane data sources
- thin adapter scripts for lane actions
- task-cycle tab lane rendering contract

## Implementation Order

Recommended order:

### Phase 2A: Read-Only Lane Model

- create lane builder
- add lane data model
- expose read-only lane API
- extend work-item payloads with lane metadata
- add UI read-only lane rendering

### Phase 2B: Scheduler

- add lane scheduler
- enforce `cap_n`
- add lane state transitions
- add dependency-aware scheduling

### Phase 2C: Integrator

- add integration decision logic
- add integrator artifacts
- add integrator runtime
- expose integration state in API/UI

### Phase 2D: Windmill and Rollout

- wire Windmill task-cycle tab to lane APIs
- add feature flag gating
- run full live validation

## Acceptance Criteria

The work is complete when all of the following are true:

- first-class parallel work-items honor `parallel_group`
- scheduler never exceeds configured `cap_n`
- lane readiness respects `depends_on` across independently scheduled lanes
- `integrator` exists only when multiple first-class lanes are implemented and merge logic is actually required
- v1 task-cycle remains unchanged when the feature flag is off

## Risks

Main implementation risks:

- overloading `task_cycle.py` further instead of splitting modules
- confusing helper sidecars with first-class lanes in UI/state
- introducing nondeterministic scheduler behavior
- allowing integrator to appear in single-lane scenarios
- breaking current task-cycle payload consumers

## Recommendation

Do not implement all of Phase 2 in one patch.

Best path:

1. add read-only lane model
2. add lane scheduler and `cap_n`
3. add dependency-aware execution
4. add integrator last

This keeps the rollout understandable and testable.
