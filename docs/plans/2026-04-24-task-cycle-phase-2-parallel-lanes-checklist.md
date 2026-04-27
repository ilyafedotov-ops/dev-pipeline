# Task Cycle Phase 2 Parallel Lanes Validation Checklist

Use this checklist to validate the Phase 2 parallel-lane implementation before shipping.

## Lane Model

- [ ] A first-class lane model exists in the backend.
- [ ] Lane identity is stable and reproducible from task-cycle/protocol data.
- [ ] `parallel_group` is reflected in lane derivation.
- [ ] Steps without `parallel_group` are mapped to single-step lanes.
- [ ] Lane metadata is exposed through API without replacing work items as the primary contract.

## `parallel_group`

- [ ] Work-items in the same `parallel_group` are grouped into the same first-class lane.
- [ ] Work-items in different `parallel_group` values are placed into separate lanes.
- [ ] `parallel_group` is visible in the work-item payload.
- [ ] `parallel_group` is visible in the Next.js Task Cycle UI.
- [ ] `parallel_group` is visible in the Windmill Task Cycle UI.

## `cap_n`

- [ ] A task-cycle/protocol-level `cap_n` configuration exists.
- [ ] `cap_n` defaults to a safe value when not configured.
- [ ] Lane scheduler never exceeds configured `cap_n`.
- [ ] Running-lane counts are visible in API and UI.
- [ ] `cap_n` is not confused with helper-agent parallelism.

## Dependencies

- [ ] Step-level `depends_on` relationships are converted into lane-aware dependencies.
- [ ] Within-lane dependencies preserve correct internal execution order.
- [ ] Cross-lane dependencies prevent dependent lanes from starting too early.
- [ ] Failed predecessor lanes block dependent lanes.
- [ ] Cycles in lane dependencies are rejected with a validation error.
- [ ] Missing dependency references are rejected with a validation error.

## Scheduler

- [ ] A dedicated lane scheduler exists separate from the v1 single-owner task-cycle loop.
- [ ] Lane states include at least `queued`, `runnable`, `running`, `blocked`, `completed`, and `failed`.
- [ ] Runnable lane selection is deterministic.
- [ ] Scheduler can reconcile lane state after completion or failure.
- [ ] Scheduler can resume correctly after restart or re-query from persisted state.

## Integrator

- [ ] An `integrator` role does not appear when the feature flag is off.
- [ ] An `integrator` role does not appear when only one first-class lane exists.
- [ ] An `integrator` role appears only when multiple first-class lanes require synthesis or merge coordination.
- [ ] Integrator input artifacts are persisted.
- [ ] Integrator output artifacts are persisted.
- [ ] Integrator state is visible through API and UI when present.

## Backend API

- [ ] There is a lane list endpoint.
- [ ] There is a lane detail endpoint.
- [ ] Work-item payloads include lane metadata.
- [ ] Lane artifacts can be read through existing artifact content patterns.
- [ ] Existing task-cycle endpoints remain backward compatible for v1 consumers.
- [ ] New lane/integration endpoints are included in generated OpenAPI output.

## Next.js UI

- [ ] The Task Cycle page shows lane summary counters.
- [ ] Work-items are visually grouped by lane when phase 2 is enabled.
- [ ] The user can see lane status, owner, dependencies, and `parallel_group`.
- [ ] The user can distinguish helper-agent sidecars from first-class lanes.
- [ ] Integration state is shown only when relevant.
- [ ] Empty and blocked states explain the next useful action for lane execution.

## Windmill

- [ ] Windmill project detail Task Cycle tab shows lane-level progress.
- [ ] Windmill exposes lane dependencies and lane status.
- [ ] Windmill scripts remain thin API adapters for lane actions.
- [ ] No Windmill script reimplements scheduling logic locally.

## Feature Flag and Rollout

- [ ] A feature flag gates phase-2 parallel-lane behavior.
- [ ] With the feature flag disabled, current v1 task-cycle behavior remains unchanged.
- [ ] With the feature flag enabled, lane metadata and scheduler behavior become active.
- [ ] Old runs continue to render safely even if they lack persisted lane state.

## Testing

- [ ] Backend unit tests cover lane derivation from `parallel_group`.
- [ ] Backend unit tests cover `cap_n` enforcement.
- [ ] Backend unit tests cover cross-lane `depends_on` ordering.
- [ ] Backend unit tests cover cycle and invalid-dependency rejection.
- [ ] Backend unit tests cover integrator creation conditions.
- [ ] API tests cover lane endpoints and backward compatibility.
- [ ] Frontend tests cover lane rendering and grouped work-item display.
- [ ] Windmill tests cover lane UI wiring and thin-adapter behavior.
- [ ] End-to-end tests verify real multi-lane scheduling behavior.

## Manual End-to-End Scenario

- [ ] Start from an existing project with phase-2 flag enabled.
- [ ] Create a task-cycle protocol containing at least two `parallel_group` values.
- [ ] Verify lane derivation matches expected group structure.
- [ ] Configure or confirm `cap_n`.
- [ ] Start execution and verify only `cap_n` lanes run concurrently.
- [ ] Verify downstream lanes wait for their dependencies.
- [ ] Complete one independent multi-lane run without integration and confirm no `integrator` appears.
- [ ] Complete one merge-requiring multi-lane run and confirm `integrator` appears.
- [ ] Verify integration artifacts are generated only in the merge-requiring case.

## Done Criteria

- [ ] First-class parallel work-items honor `parallel_group`.
- [ ] Parallel execution respects configured `cap_n`.
- [ ] Dependency ordering respects `depends_on` across independently scheduled lanes.
- [ ] An `integrator` role exists only when multiple first-class lanes are actually implemented.
