# Brownfield Task Cycle Implementation Plan

> Scope: implement the task cycle from [task-cycle-flow.md](../DevGodzilla/task-cycle-flow.md) for small brownfield work using Windmill as runner and Next.js as the primary UI.
> Source inputs: [task-cycle-flow.md](../DevGodzilla/task-cycle-flow.md), [BROWNFIELD-WORKFLOW.md](../DevGodzilla/BROWNFIELD-WORKFLOW.md), [WINDMILL-WORKFLOWS.md](../DevGodzilla/WINDMILL-WORKFLOWS.md), screenshot `Screenshot 2026-03-08 at 00.00.07.png`.

## Goal

Turn the current artifact-first brownfield journey into a work-item loop:

1. pick work-item
2. build brownfield context
3. assign single owner
4. implement
5. review
6. test and coverage
7. mark PR-ready

The core product rule is:

- Next.js should expose the customer journey.
- Windmill should run the workflow.
- DevGodzilla backend should own state, contracts, and artifacts.

## Current Status

As of 2026-04-23, the following v1 items are implemented in repo code:

- Task Cycle is the default brownfield project entry in the Next.js project view when the feature is enabled.
- `ContextPack` is generated before implementation and is consumed by execution and QA/test handoffs.
- Work-item state exposes owner, helper-agent summary, review/QA state, `PR-ready`, `task_dir`, and artifact refs.
- The Task Cycle UI follows the v1 loop more closely by surfacing the next useful action and disabling invalid transitions.
- Task-cycle artifacts and routes are present in runtime OpenAPI and covered by tests.
- Rollout can be gated with `DEVGODZILLA_TASK_CYCLE_ENABLED`.

Still intentionally open in this plan:

- dedicated review-agent execution instead of local review logic
- real bounded helper-agent subtask execution
- full manual brownfield intake-to-PR-ready validation
- Windmill app parity beyond the protocol detail semantic action fix

## Proposed Agent Set

Use a small fixed set of agents first:

- `context_builder`
- `dev_owner`
- `review`
- `test`
- `helper_agents` only as internal delegation under `dev_owner`
- `clarifier` only when context is insufficient

V1 ownership rule:

- one work item has one accountable owner
- helper agents may run bounded parallel subtasks
- helper agents do not create first-class workflow lanes
- review, QA, and `PR-ready` run once on the consolidated result

## Shared Context Contract

Current runtime shares context mostly through repo state, protocol files, DB state, and artifacts. That means this feature should make handoff artifacts explicit.

Add a `ContextPack` artifact per work-item with:

- goal
- acceptance criteria
- target files
- traced contracts, APIs, schemas, and types
- repo entry points
- exact test commands
- review focus
- risks and hotspots
- assumptions and open questions

Persist it as two artifacts:

- `context_pack.json` as the canonical machine-readable contract
- `context_pack.md` as the human-readable operator and debug view

Canonical storage location for v1 should be inside the project temp folder, grouped by task/work item:

- `<project_temp>/task-cycle/work-items/<step_run_id>/context_pack.json`
- `<project_temp>/task-cycle/work-items/<step_run_id>/context_pack.md`
- `<project_temp>/task-cycle/work-items/<step_run_id>/review_report.json`
- `<project_temp>/task-cycle/work-items/<step_run_id>/review_report.md`
- `<project_temp>/task-cycle/work-items/<step_run_id>/test_report.json`
- `<project_temp>/task-cycle/work-items/<step_run_id>/test_report.md`
- `<project_temp>/task-cycle/work-items/<step_run_id>/rework_pack.json`

That folder path should be exposed in the API as `task_dir` and mirrored in `artifact_refs`.

In v1, work items should be a higher-level projection over existing `step_runs`:

- one work item maps to one `StepRun`
- `step_run_id` is the stable persisted runtime identity
- the API and UI expose a `work_item` view over that identity
- do not add a separate `work_items` table in v1 unless projection proves insufficient

Default v1 flow reference:

- use [task-cycle-flow.md](../DevGodzilla/task-cycle-flow.md) as the default task-cycle definition
- later, add a flow manager that can select or generate custom flow variants
- do not block v1 on building the flow manager abstraction

## Phase 1: Define the New Contract

### Files to update

- [docs/DevGodzilla/task-cycle-flow.md](../DevGodzilla/task-cycle-flow.md)
- [docs/DevGodzilla/BROWNFIELD-WORKFLOW.md](../DevGodzilla/BROWNFIELD-WORKFLOW.md)
- [docs/DevGodzilla/WINDMILL-WORKFLOWS.md](../DevGodzilla/WINDMILL-WORKFLOWS.md)
- [docs/DevGodzilla/CURRENT_STATE.md](../DevGodzilla/CURRENT_STATE.md)
- [docs/DevGodzilla/ARCHITECTURE.md](../DevGodzilla/ARCHITECTURE.md)

### Files to add

- `docs/DevGodzilla/TASK-CYCLE-CONTEXT-PACK.md`
- `schemas/context-pack.schema.json`

### Work

- Document the work-item lifecycle state machine.
- Define the `ContextPack` JSON shape.
- Define the `ReworkPack`, `ReviewReport`, and `TestReport` artifact shapes.
- Define the v1 projection from `StepRun` to `WorkItemOut`.
- Defer first-class lane semantics for `parallel_group` and `cap_n` to phase 2.
- Define the canonical project temp folder layout for task-cycle artifacts.

### Example schema sketch

```json
{
  "task_id": "wf-123-item-2",
  "project_id": 42,
  "protocol_run_id": 77,
  "step_run_id": 123,
  "goal": "Add bulk archive action to users table",
  "acceptance_criteria": [
    "Operator can archive multiple users from the table",
    "API rejects archive for already-deleted users"
  ],
  "entry_points": [
    "frontend/app/users/page.tsx",
    "devgodzilla/api/routes/users.py"
  ],
  "contracts": [
    {
      "kind": "api",
      "path": "devgodzilla/api/routes/users.py",
      "symbol": "POST /users/archive"
    }
  ],
  "manifest_files": [
    {
      "path": "package.json",
      "reason": "frontend scripts and dependency conventions"
    },
    {
      "path": "pyproject.toml",
      "reason": "python tooling and style configuration"
    }
  ],
  "style_guides": [
    {
      "path": "AGENTS.md",
      "reason": "repo-specific coding instructions"
    }
  ],
  "test_commands": [
    "pytest -q tests/test_users_api.py",
    "pnpm test -- users"
  ],
  "review_focus": [
    "selection state across pagination",
    "API validation for deleted users"
  ],
  "risks": [
    "Row selection state already has a known bug with pagination"
  ],
  "assumptions": [],
  "open_questions": [],
  "required_files": [
    {
      "path": "frontend/app/users/page.tsx",
      "reason": "UI entry point for bulk archive"
    },
    {
      "path": "devgodzilla/api/routes/users.py",
      "reason": "Archive API endpoint"
    }
  ],
  "artifact_refs": {
    "task_dir": "/tmp/project-42/task-cycle/work-items/123",
    "context_pack_json": "/tmp/project-42/task-cycle/work-items/123/context_pack.json",
    "context_pack_md": "/tmp/project-42/task-cycle/work-items/123/context_pack.md"
  }
}
```

## Phase 2: Add Backend State for Task-Cycle Work Items

### Files to update

- [devgodzilla/api/app.py](../../devgodzilla/api/app.py)
- [devgodzilla/api/schemas.py](../../devgodzilla/api/schemas.py)
- [devgodzilla/models/domain.py](../../devgodzilla/models/domain.py)
- [devgodzilla/db/schema.py](../../devgodzilla/db/schema.py)
- [devgodzilla/db/database.py](../../devgodzilla/db/database.py)
- [devgodzilla/api/routes/protocols.py](../../devgodzilla/api/routes/protocols.py)
- [devgodzilla/api/routes/steps.py](../../devgodzilla/api/routes/steps.py)

### Files to add

- `devgodzilla/api/routes/brownfield.py`
- `devgodzilla/services/context_builder.py`
- `devgodzilla/services/task_cycle.py`

### Work

- Add a high-level brownfield/task-cycle route group instead of forcing the UI to orchestrate raw SpecKit and protocol endpoints.
- Keep protocol steps as the execution substrate and project a higher-level `work_item` view over existing `step_runs`.
- In v1, use `step_run_id` as the persisted identity for a work item.
- Extend step runtime state and artifact references for:
  - `context_status`
  - `review_status`
  - `qa_status`
  - `pr_ready`
  - `owner_agent`
  - `helper_agents`
  - `task_dir`
  - `artifact_refs`
- Add APIs such as:
  - `POST /projects/{id}/brownfield/run`
  - `GET /projects/{id}/task-cycle`
  - `POST /work-items/{id}/build-context`
  - `POST /work-items/{id}/review`
  - `POST /work-items/{id}/qa`
  - `POST /work-items/{id}/mark-pr-ready`

### Example endpoint sketch

```python
class BrownfieldRunRequest(BaseModel):
    feature_request: str
    output_mode: Literal["task_cycle", "tasks_only", "protocol"]
    branch: str = "main"
    run_discovery_agent: bool = False
    owner_agent: str = "dev"
    allow_helper_agents: bool = True


class WorkItemOut(BaseModel):
    id: int  # projected from step_run_id
    project_id: int
    protocol_run_id: int
    title: str
    status: str
    context_status: str
    review_status: str
    qa_status: str
    owner_agent: str | None = None
    helper_agents: list[str] = []
    task_dir: str | None = None
    artifact_refs: dict[str, str] = {}
    depends_on: list[str] = []
    pr_ready: bool = False
    blocking_clarifications: int = 0
    blocking_policy_findings: int = 0
```

## Phase 3: Build the Context Builder Agent Path

The screenshot points to a brownfield code-first context builder. That should be implemented before parallel execution.

### Files to update

- [devgodzilla/services/planning.py](../../devgodzilla/services/planning.py)
- [devgodzilla/services/execution.py](../../devgodzilla/services/execution.py)
- [devgodzilla/services/quality.py](../../devgodzilla/services/quality.py)
- [devgodzilla/services/orchestrator.py](../../devgodzilla/services/orchestrator.py)

### Files to add

- `prompts/context-builder.prompt.md`
- `prompts/review-agent.prompt.md`
- `prompts/test-agent.prompt.md`
- `windmill/scripts/devgodzilla/context_builder_api.py`
- `windmill/scripts/devgodzilla/review_work_item_api.py`
- `windmill/scripts/devgodzilla/test_work_item_api.py`

### Work

- Add a `ContextBuilderService` that:
  - locates entry points
  - traces dependencies and contracts
  - traces test surface and CI commands
  - detects risk hotspots
  - records project manifests and style-guide references
  - emits `context_pack.json` and `context_pack.md`
- Make execution consume `context_pack.json` before the task body, not only `plan.md` and the step file.
- Make review and test agents also consume the same `ContextPack`.
- Include `step_run_id`, curated file references, and exact test commands so the artifact is reusable for debugging and rework.

### Current limitation to fix

Today execution prompt construction mostly includes:

- exec prompt template
- `plan.md`
- current step file

See:

- [devgodzilla/services/execution.py](../../devgodzilla/services/execution.py)

That is too thin for brownfield work-item loops.

## Phase 4: Implement Windmill Task-Cycle Flows

### Files to update

- [windmill/flows/devgodzilla/brownfield_feature.flow.json](../../windmill/flows/devgodzilla/brownfield_feature.flow.json)
- [windmill/flows/devgodzilla/run_next_step.flow.json](../../windmill/flows/devgodzilla/run_next_step.flow.json)
- [windmill/flows/devgodzilla/step_execute_with_qa.flow.json](../../windmill/flows/devgodzilla/step_execute_with_qa.flow.json)
- [windmill/scripts/devgodzilla/protocol_select_next_step.py](../../windmill/scripts/devgodzilla/protocol_select_next_step.py)
- [windmill/scripts/devgodzilla/step_execute_api.py](../../windmill/scripts/devgodzilla/step_execute_api.py)
- [windmill/scripts/devgodzilla/step_run_qa_api.py](../../windmill/scripts/devgodzilla/step_run_qa_api.py)

### Files to add

- `windmill/flows/devgodzilla/work_item_review.flow.json`
- `windmill/flows/devgodzilla/work_item_test.flow.json`
- `windmill/scripts/devgodzilla/get_task_cycle_api.py`
- `windmill/scripts/devgodzilla/mark_pr_ready_api.py`

### Work

- Keep `brownfield_feature` as intake.
- Add `task_cycle` as an `output_mode` branch inside `brownfield_feature`.
- Avoid creating a second user-facing intake flow for task-cycle.
- Flow modules should run:
  1. build context
  2. assign owner
  3. execute owner-driven implementation
  4. allow internal helper-agent delegation when useful
  5. review
  6. rework loop if needed
  7. QA
  8. rework loop if needed
  9. mark PR-ready
- Do not add first-class multi-lane scheduling in v1.

## Phase 4.5: Add Dedicated Review Stage

Review should be part of the flow, with a dedicated review agent rather than being treated as an implicit side effect.

### Review agent inputs

- work-item details
- `context_pack.json`
- diff summary and changed files
- project manifests
- project style guides and best-practice references
- exact test commands
- existing policy findings if present

### Review agent outputs

- `review_report.json`
- `review_report.md`
- blocking findings
- warnings
- recommended rework actions
- recommended QA emphasis areas

### Review agent responsibility

- verify implementation matches the task goal and acceptance criteria
- verify touched files are consistent with repo conventions
- check code style guidance and manifest-driven expectations
- inspect likely test coverage gaps before QA runs
- send the work item back to rework when findings are blocking

### Example Windmill payload

```json
{
  "project_id": 42,
  "feature_request": "Add bulk archive to users table",
  "output_mode": "task_cycle",
  "owner_agent": "dev",
  "allow_helper_agents": true,
  "review_required": true,
  "qa_required": true
}
```

## Phase 5: Replace the Current UI Journey in Next.js

### Files to update

- [frontend/app/projects/[id]/page.tsx](../../frontend/app/projects/[id]/page.tsx)
- [frontend/app/projects/[id]/components/workflow-tab.tsx](../../frontend/app/projects/[id]/components/workflow-tab.tsx)
- [frontend/components/workflow/pipeline-visualizer.tsx](../../frontend/components/workflow/pipeline-visualizer.tsx)
- [frontend/components/visualizations/pipeline-dag.tsx](../../frontend/components/visualizations/pipeline-dag.tsx)
- [frontend/components/speckit/spec-workflow.tsx](../../frontend/components/speckit/spec-workflow.tsx)
- [frontend/components/wizards/implement-feature-wizard.tsx](../../frontend/components/wizards/implement-feature-wizard.tsx)
- [frontend/lib/api/types.ts](../../frontend/lib/api/types.ts)
- [frontend/lib/api/hooks/use-protocols.ts](../../frontend/lib/api/hooks/use-protocols.ts)
- [frontend/lib/api/hooks/use-steps.ts](../../frontend/lib/api/hooks/use-steps.ts)

### Files to add

- `frontend/components/workflow/task-cycle-board.tsx`
- `frontend/components/workflow/work-item-card.tsx`
- `frontend/components/wizards/brownfield-feature-wizard.tsx`
- `frontend/lib/api/hooks/use-brownfield.ts`

### Work

- Add one main entry point: `Brownfield Feature`.
- Replace the current SpecKit stepper with a task-cycle board.
- Show columns or states:
  - `Queued`
  - `Context Ready`
  - `In Progress`
  - `In Review`
  - `QA`
  - `PR Ready`
- Surface explicit actions:
  - build context
  - assign owner
  - run implement
  - run review
  - run QA
  - mark PR-ready
- Show artifacts inline:
  - `ContextPack`
  - latest review report
  - latest test report
  - latest diff summary
- Show helper-agent activity only as subordinate execution detail under the owner, not as first-class lanes in v1.
- Show the task folder path and direct links to `context_pack`, `review_report`, and `test_report`.

### UI rule

Do not make the customer think in:

- SpecKit
- protocol files
- step markdown files

Those remain internal implementation details.

## Phase 6: Update Windmill Operator Apps

### Files to update

- [windmill/apps/devgodzilla/devgodzilla_project_detail.app.json](../../windmill/apps/devgodzilla/devgodzilla_project_detail.app.json)
- [windmill/apps/devgodzilla/devgodzilla_protocol_detail.app.json](../../windmill/apps/devgodzilla/devgodzilla_protocol_detail.app.json)

### Work

- Add `Task Cycle` or `Feature Delivery` as the first-class tab.
- Show current work-items, owner, helper-agent activity summary, review state, QA state, and PR-ready state.
- Remove the misleading protocol action wiring where `Start` reads like protocol start but points to raw step execution.

## Phase 7: Add Tests Before Rollout

### Backend/API tests to update or add

- [tests/test_devgodzilla_windmill_workflows.py](../../tests/test_devgodzilla_windmill_workflows.py)
- [tests/test_devgodzilla_orchestrator_lifecycle.py](../../tests/test_devgodzilla_orchestrator_lifecycle.py)
- [tests/test_devgodzilla_quality_service.py](../../tests/test_devgodzilla_quality_service.py)
- [tests/test_devgodzilla_feedback_router.py](../../tests/test_devgodzilla_feedback_router.py)
- [tests/test_devgodzilla_api_e2e_headless_workflow.py](../../tests/test_devgodzilla_api_e2e_headless_workflow.py)
- [tests/test_devgodzilla_api_windmill_and_runs.py](../../tests/test_devgodzilla_api_windmill_and_runs.py)
- [tests/test_state_transitions.py](../../tests/test_state_transitions.py)

### Frontend tests to update or add

- [tests/test_devgodzilla_frontend_integration.py](../../tests/test_devgodzilla_frontend_integration.py)
- [tests/test_devgodzilla_frontend_task_properties.py](../../tests/test_devgodzilla_frontend_task_properties.py)
- [frontend/__tests__/workflow/pipeline-visualizer-properties.test.tsx](../../frontend/__tests__/workflow/pipeline-visualizer-properties.test.tsx)

### New tests likely needed

- `tests/test_devgodzilla_task_cycle_api.py`
- `tests/test_devgodzilla_context_builder_service.py`
- `tests/test_devgodzilla_task_cycle_properties.py`
- `frontend/__tests__/workflow/task-cycle-board.test.tsx`

### Test coverage needed

- context pack creation
- single-owner loop
- review agent input coverage from manifests and style-guide references
- review fail -> rework
- QA fail -> rework
- PR-ready transition
- clarification/blocking behavior

## Phase 8: Rollout Order

1. Add schemas and backend routes behind a feature flag.
2. Add context builder service and artifacts.
3. Add `task_cycle` branch inside `brownfield_feature`.
4. Add Next.js task-cycle board and new brownfield wizard.
5. Switch project page primary entry from SpecKit flow to brownfield task-cycle flow.
6. Update Windmill apps after the API and flow contract settles.

## Suggested Definition of Done

- A user can start one brownfield feature from one UI entry point.
- The system builds explicit context before coding starts.
- Each work-item has visible owner, helper-agent activity summary, review state, and QA state.
- Review and QA can send the task back to rework.
- PR-ready is explicit and auditable.
- All state transitions are covered by automated tests.

## Basic v1 PR-Ready Rule

Start with a simple rule set based on current best practices and tighten later:

- `context_pack.json` exists
- implementation completed successfully
- latest `review_report` has no blocking findings
- latest `test_report` passed required QA commands
- no blocking clarifications remain open
- no blocking policy findings remain
- required artifact references are populated on the work item

## Minimal First Release

If scope must stay tight, implement only:

1. `Context Builder`
2. `Dev Owner`
3. `Review`
4. `Test`
5. `single_owner` mode

Defer:

- first-class parallel lanes
- `parallel_group`
- `cap_n`
- `integrator` agent
- automatic PR creation
- multi-lane merge conflict handling
