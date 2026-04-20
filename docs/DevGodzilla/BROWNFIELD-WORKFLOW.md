# Brownfield Workflow

> Status: Active design direction, exported as `f/devgodzilla/brownfield_feature`
> Scope: Small brownfield project and feature-delivery journey
> Last updated: 2026-04-20

## Why this flow exists

The current DevGodzilla journey is split across multiple concepts:

- project onboarding
- SpecKit specification and clarification
- plan and task generation
- protocol creation and planning
- sprint synchronization

That separation matches internal architecture, but it is too heavy for a user who usually wants one simple outcome:

- understand the repo
- define one feature
- get either tasks, a runnable protocol, or a sprint-ready backlog

## Recommended customer journey

For a small brownfield feature, the UI and flow runner should ask only four things:

1. Which repo or existing project are we working on?
2. What customer outcome are we trying to deliver?
3. Do we only need tasks, or should DevGodzilla create an executable protocol?
4. Should the result land in an existing sprint or create a new sprint?

Everything else should stay optional and advanced:

- discovery
- clarifications
- checklist generation
- analysis report
- protocol overwrite behavior

## Windmill flow

The exported flow is:

- `f/devgodzilla/brownfield_feature`

Source file:

- `windmill/flows/devgodzilla/brownfield_feature.flow.json`

It reuses existing API-wrapper scripts instead of adding new backend orchestration:

- `windmill/scripts/devgodzilla/project_onboard_api.py`
- `windmill/scripts/devgodzilla/speckit_specify_api.py`
- `windmill/scripts/devgodzilla/speckit_clarify_api.py`
- `windmill/scripts/devgodzilla/speckit_plan_api.py`
- `windmill/scripts/devgodzilla/speckit_checklist_api.py`
- `windmill/scripts/devgodzilla/speckit_tasks_api.py`
- `windmill/scripts/devgodzilla/speckit_analyze_api.py`
- `windmill/scripts/devgodzilla/protocol_from_spec_api.py`
- `windmill/scripts/devgodzilla/protocol_plan_and_wait.py`
- `windmill/scripts/devgodzilla/sync_tasks_api.py`
- `windmill/scripts/devgodzilla/sprint_from_protocol_api.py`

## Flow shape

Base path:

1. onboard existing or new project
2. generate spec
3. optionally apply clarifications
4. generate plan
5. optionally generate checklist
6. generate tasks
7. optionally generate analysis

Delivery branch:

- `task_cycle`
- `tasks_only`
- `tasks_to_sprint`
- `protocol`
- `protocol_to_sprint`

This keeps one entry point while still supporting the most common brownfield outcomes.

## What to simplify in UI next

The frontend should stop exposing separate wizards for each internal artifact stage when the user intent is feature delivery.

Recommended replacement:

- one "Brownfield Feature" entry point
- step 1: repo/project
- step 2: feature request
- step 3: desired output mode
- step 4: optional advanced settings

The existing wizard components show the current fragmentation:

- `frontend/components/wizards/project-wizard.tsx`
- `frontend/components/wizards/generate-specs-wizard.tsx`
- `frontend/components/wizards/implement-feature-wizard.tsx`

## Backend/API contract

The compound backend endpoint now exists:

- `POST /projects/{id}/brownfield/run`

Implemented request shape:

- required: `feature_request`
- optional naming and routing: `feature_name`, `protocol_name`, `branch`
- mode selection: `output_mode`
- sprint inputs: `sprint_id`, `sprint_name`, `auto_sync_sprint`, `overwrite_existing_tasks`
- protocol overwrite control: `overwrite_protocol`

Implemented `output_mode` values:

- `task_cycle`: create a protocol, seed task-cycle metadata, and auto-advance the first runnable step
- `tasks_only`: stop after SpecKit tasks are generated
- `tasks_to_sprint`: import generated tasks into an existing sprint
- `protocol`: create and plan a protocol without task-cycle auto-advance
- `protocol_to_sprint`: create a protocol, create a sprint from it, and optionally sync tasks into that sprint

Implemented response shape:

- artifact paths: `spec_path`, `plan_path`, `tasks_path`
- protocol output when relevant: `protocol`
- sprint output when relevant: `sprint`, `tasks_synced`, `task_ids`
- task-cycle output when relevant: `work_items`, `next_work_item_id`
- async hinting: `warnings`, `poll_hint`

Long-running runs can still return `202 Accepted`. The caller should follow the returned `poll_hint`, because the correct polling endpoint depends on `output_mode` rather than always being the task-cycle board.
