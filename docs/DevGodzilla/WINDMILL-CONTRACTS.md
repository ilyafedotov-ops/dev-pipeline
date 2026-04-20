# DevGodzilla Windmill Contracts

> Status: Active
> Scope: Current flow-level contracts for Windmill scripts and flows shipped in this repo
> Source of truth: `windmill/flows/devgodzilla/`, `windmill/scripts/devgodzilla/`, `windmill/scripts/devgodzilla/_api.py`, `devgodzilla/api/routes/windmill.py`, related tests in `tests/`
> Last updated: 2026-04-20

## Summary

Windmill flows in this repo are thin orchestration layers over the DevGodzilla API.

Contract rule:

- Windmill script -> `windmill/scripts/devgodzilla/_api.py` -> DevGodzilla API

This doc records what each active flow is for and how it connects to backend and frontend surfaces.

## Flow Contracts

### `project_onboarding`

Purpose:

- bootstrap repo understanding and initial SpecKit readiness

Script chain:

- `clone_repo`
- `analyze_project`
- `initialize_speckit`

Backend effect:

- prepares repo-local analysis state and `.specify/` initialization

Frontend touchpoints:

- project onboarding views
- project overview and onboarding tabs

### `onboard_to_tasks`

Purpose:

- take a project from onboarding through full SpecKit artifact generation

Script chain:

- `project_onboard_api`
- `speckit_specify_api`
- `speckit_clarify_api`
- `speckit_plan_api`
- `speckit_checklist_api`
- `speckit_tasks_api`
- `speckit_analyze_api`
- `speckit_implement_api`

Backend effect:

- creates or updates onboarding state plus spec, plan, checklist, tasks, analysis, and implement artifacts

Frontend touchpoints:

- project workspace
- specification review pages

### `spec_to_tasks`

Purpose:

- run the SpecKit path and synchronize resulting tasks

Script chain:

- `speckit_specify_api`
- `speckit_clarify_api`
- `speckit_plan_api`
- `speckit_checklist_api`
- `speckit_tasks_api`
- `speckit_analyze_api`
- `speckit_implement_api`
- `sync_tasks_api`

Backend effect:

- produces spec artifacts and maps resulting tasks into the task/sprint system

Frontend touchpoints:

- spec review pages
- task-cycle and sprint surfaces

### `spec_to_protocol`

Purpose:

- turn spec work into an executable protocol

Script chain:

- `speckit_specify_api`
- `speckit_clarify_api`
- `speckit_plan_api`
- `speckit_checklist_api`
- `speckit_tasks_api`
- `speckit_analyze_api`
- `speckit_implement_api`
- `protocol_plan_and_wait`

Backend effect:

- produces SpecKit artifacts and a planned protocol

Frontend touchpoints:

- project workspace
- protocol workspace

### `protocol_start`

Purpose:

- plan and start a protocol through the backend orchestration layer

Script chain:

- `protocol_plan_and_wait`

Backend effect:

- advances a protocol toward planned/running state

Frontend touchpoints:

- protocol detail start controls

### `run_next_step`

Purpose:

- select and execute the next runnable protocol step

Script chain:

- `protocol_select_next_step`
- `step_execute_api`

Backend effect:

- advances step and protocol execution state

Frontend touchpoints:

- protocol detail page
- step and run drill-down pages

### `execute_protocol`

Purpose:

- trigger step execution as a focused flow wrapper

Script chain:

- `step_execute_api`

Backend effect:

- executes step work and emits logs/events

Frontend touchpoints:

- protocol/runs/log surfaces

### `step_execute_with_qa`

Purpose:

- execute a step in the standard backend path that includes QA behavior

Script chain:

- `step_execute_api`

Backend effect:

- step execution plus downstream QA lifecycle handled by backend orchestration

Frontend touchpoints:

- protocol quality, feedback, and logs tabs

### `sync_tasks_to_sprint`

Purpose:

- push task outputs into sprint/task state

Script chain:

- `sync_tasks_api`

Backend effect:

- updates sprint-linked tasks and related metrics

Frontend touchpoints:

- project sprint workspace
- task-cycle views

### `sprint_from_protocol`

Purpose:

- create or link sprint state from protocol output

Script chain:

- `sprint_from_protocol_api`

Backend effect:

- materializes sprint context for a protocol

Frontend touchpoints:

- project and protocol sprint views

### `complete_sprint`

Purpose:

- close or complete a sprint lifecycle through the backend

Script chain:

- `complete_sprint_api`

Backend effect:

- final sprint status and metrics updates

Frontend touchpoints:

- sprint dashboards and project execution views

### `brownfield_feature`

Purpose:

- one-entry brownfield flow covering onboarding, SpecKit, task-cycle, protocol, and sprint delivery options

Script chain:

- `project_onboard_api`
- `speckit_specify_api`
- `speckit_clarify_api`
- `speckit_plan_api`
- `speckit_checklist_api`
- `speckit_tasks_api`
- `speckit_analyze_api`
- `protocol_from_spec_api`
- `protocol_plan_and_wait`
- `get_task_cycle_api`
- `sync_tasks_api`
- `sprint_from_protocol_api`

Backend effect:

- end-to-end brownfield feature delivery from repo understanding to `task_cycle`, `tasks_only`, `tasks_to_sprint`, `protocol`, or `protocol_to_sprint` outputs

Frontend touchpoints:

- project task-cycle views
- execution and spec-related workspaces

## Common Script Contract

Most `*_api.py` scripts:

- call backend endpoints rather than importing backend internals
- rely on `DEVGODZILLA_API_URL` or a Windmill variable for backend base URL
- return JSON-shaped results suitable for flow chaining

## Related Tests

Key backend test areas that verify these contracts:

- Windmill workflow contract tests
- Windmill client and import-manifest tests
- protocol/run API integration tests
- reconciliation tests

## Related Docs

- `WINDMILL-WORKFLOWS.md`
- `WINDMILL-OPERATIONS.md`
- `BACKEND-FLOWS.md`
