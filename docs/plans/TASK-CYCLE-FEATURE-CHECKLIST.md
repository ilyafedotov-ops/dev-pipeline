# Brownfield Task Cycle Feature Validation Checklist

Use this checklist to validate the task-cycle implementation before shipping.

## Product Flow

- [x] There is one visible primary entry point for brownfield delivery.
- [x] The entry point asks for project or repo, feature request, and output mode.
- [x] The UI does not force the user through separate SpecKit, plan, and protocol wizards for the common path.
- [x] `task_cycle` is an `output_mode` branch inside `brownfield_feature`, not a separate user-facing intake flow.
- [x] The work-item loop in the UI matches [task-cycle-flow.md](../DevGodzilla/task-cycle-flow.md).
- [x] [task-cycle-flow.md](../DevGodzilla/task-cycle-flow.md) is treated as the default v1 task-cycle reference until a future flow manager exists.

## Context Builder

- [x] A `ContextPack` artifact is created before implementation begins.
- [x] `ContextPack` is persisted as both `context_pack.json` and `context_pack.md`.
- [x] `context_pack.json` includes `work_item_id`, `project_id`, `protocol_run_id`, `step_run_id`, goal, acceptance criteria, entry points, required files, contracts, types, schemas, test commands, review focus, and risk notes.
- [x] `context_pack.json` also captures project manifests and style-guide references needed by review and QA.
- [x] File references in `ContextPack` are curated and reusable by downstream agents, not just raw logs.
- [x] The system can detect insufficient context and request clarification or deeper tracing.
- [x] For brownfield repos, the context path is code-first, not spec-first.
- [x] Work-item artifacts are stored under the project temp folder in per-task subfolders.

## Backend Contract

- [x] There is a stable intent-level API for starting brownfield task-cycle runs.
- [x] Work-item state is available through API without exposing raw protocol internals as the primary contract.
- [x] In v1, work items are projected from existing `step_runs` with a stable identity mapping.
- [x] Work-item state includes context, review, QA, owner, helper-agent summary, and PR-ready fields.
- [x] Work-item state includes a canonical task folder path and artifact references.
- [x] Blocking clarifications stop execution cleanly.
- [x] Policy findings can block or warn according to enforcement mode.

## Execution Model

- [x] Single-owner work-items can be assigned and executed.
- [x] A single `owner_agent` is accountable for each work item.
- [x] Helper agents may run bounded parallel subtasks under the owner without creating first-class workflow lanes.
- [x] Review failure returns the work-item to rework.
- [x] QA failure returns the work-item to rework.
- [x] Successful review and QA can mark the work-item `PR-ready`.

## Agent Handoffs

- [x] `context_builder` writes reusable artifacts, not only logs.
- [x] `dev` consumes `context_pack.json` as the primary machine-readable contract.
- [x] `review` is a dedicated stage in the flow with a separate review agent.
- [x] `review` consumes the `ContextPack`, current diff or artifacts, project manifests, and project style-guide references.
- [x] `test` consumes the `ContextPack`, diff, and exact test commands.
- [x] Rework feedback is stored as a structured artifact, not only as free text in logs.

## Windmill

- [x] `brownfield_feature` can branch into `task_cycle`.
- [x] The task-cycle branch is part of the same user-facing intake flow.
- [x] Windmill scripts remain thin API adapters.
- [x] Flow runs and job runs are visible through existing API passthrough endpoints.
- [x] Operator actions in Windmill are named according to business meaning, not raw internal step verbs.

## Next.js UI

- [x] The project page shows task-cycle progress as work-items, not only protocol steps.
- [x] The work-item UI is a higher-level projection over existing `step_runs`.
- [x] The user can see owner, helper-agent activity summary, status, review state, QA state, and PR-ready state.
- [x] The user can open the latest context, review, and test artifacts from the UI.
- [x] The user can see the task folder path and reusable artifact links for the current work item.
- [x] The user can trigger implement, review, QA, and mark PR-ready actions from the UI.
- [x] Empty states explain the next useful action.

## Windmill Apps

- [ ] Windmill project detail has a first-class `Task Cycle` or `Feature Delivery` tab.
- [x] Windmill protocol detail actions are semantically correct.
- [x] No button labeled `Start` actually runs a raw step action by mistake.

## Testing

- [x] Backend unit tests cover context creation, work-item transitions, and rework loops.
- [x] Windmill workflow tests cover the `task_cycle` branch.
- [x] Frontend tests cover task-cycle board rendering and actions.
- [ ] Property or transition tests cover invalid state transitions.
- [ ] Manual test verifies one complete brownfield feature from intake to PR-ready.

## Manual End-to-End Scenario

- [ ] Start from an existing project.
- [ ] Enter one brownfield feature request.
- [ ] Generate work-items.
- [ ] Build `context_pack.json` and `context_pack.md` for the first work-item.
- [ ] Run a `dev` implementation cycle.
- [ ] Run `review`.
- [ ] Verify the review agent uses manifests, style-guide references, and test commands from `context_pack.json`.
- [ ] Force one review failure and verify rework loop.
- [ ] Run `test`.
- [ ] Force one QA failure and verify rework loop.
- [ ] Reach `PR-ready`.

## Deferred Phase 2

- [ ] First-class parallel work-items honor `parallel_group`.
- [ ] Parallel execution respects configured `cap_n`.
- [ ] Dependency ordering respects `depends_on` across independently scheduled lanes.
- [ ] An `integrator` role exists only when multiple first-class lanes are actually implemented.

## Release Readiness

- [x] Docs are updated in `docs/DevGodzilla/`.
- [ ] No route, flow, or UI label still uses the old fragmented journey as the recommended path.
- [ ] New artifacts and APIs are included in `openapi.json` and tested.
- [x] Basic `PR-ready` criteria are implemented and visible in the work-item contract.
- [ ] Rollout can be gated by a feature flag if needed.
