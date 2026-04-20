# DevGodzilla Frontend Workspaces

> Status: Active
> Scope: Project and protocol workspaces as the primary contributor-facing UI models
> Source of truth: `frontend/app/projects/[id]/`, `frontend/app/protocols/[id]/`, `frontend/lib/project-routes.ts`
> Last updated: 2026-04-20

## Summary

The frontend has two main workspaces:

- project workspace
- protocol workspace

Everything else is either a list page, a drill-down page, or an operational support surface for these two workspaces.

## Project Workspace

Primary route:

- `/projects/[id]`

The project workspace is a multi-tab control surface for one codebase. It combines planning, governance, Git surfaces, onboarding, and execution entrypoints.

Current tab groups:

- Overview
- Specifications
- Branches & PRs
- Sprints
- Workflow Pipeline
- Task Cycle
- Policy
- Clarifications
- Settings
- Onboarding

Key responsibilities:

- show project identity, base branch, repo URL, and policy pack linkage
- expose onboarding status and manual onboarding start
- surface protocol stats and project-scoped quick actions
- launch SpecKit, design, and implementation wizard flows
- provide access to sprint, branch/PR, workflow, task-cycle, and clarification surfaces

Current project-scoped route entrypoints also include:

- `/projects/[id]/branches`
- `/projects/[id]/clarifications`
- `/projects/[id]/constitution`
- `/projects/[id]/design-solution`
- `/projects/[id]/execution`
- `/projects/[id]/generate-specs`
- `/projects/[id]/implement-feature`
- `/projects/[id]/onboarding`
- `/projects/[id]/policy`
- `/projects/[id]/protocols`
- `/projects/[id]/sprint-board`

## Protocol Workspace

Primary route:

- `/protocols/[id]`

The protocol workspace is the execution control surface for one `ProtocolRun`.

Primary actions include:

- start
- pause
- resume
- run next step
- retry latest
- open PR
- cancel
- create Windmill flow
- sync to sprint

Current detail tabs and drill-down areas:

- Steps
- Runs
- Quality
- Events
- Logs
- Spec
- Policy
- Clarifications
- Feedback
- Artifacts

Current protocol-scoped route entrypoints also include:

- `/protocols/[id]/steps`
- `/protocols/[id]/runs`
- `/protocols/[id]/events`
- `/protocols/[id]/spec`
- `/protocols/[id]/policy`
- `/protocols/[id]/clarifications`

Key responsibilities:

- show protocol state and execution controls
- connect protocol state to project, spec, policy, and sprint context
- provide realtime step/protocol refresh through websocket-driven invalidation
- surface feedback and clarification handling during execution

## Route Helpers And Supported Navigation

`frontend/lib/project-routes.ts` defines the canonical navigation helpers for the main workflows:

- execution workspace path
- project spec workspace path
- project spec workflow wizard path
- manual plan wizard path
- manual tasks wizard path
- specification review path

These helpers are the supported way to move users between:

- project detail
- spec generation or review
- protocol execution
- sprint execution surfaces

## Workspace Boundaries

Use the project workspace when the user is deciding:

- what to build
- how the repo is configured
- how the project is onboarded
- which sprint or branch context applies

Use the protocol workspace when the user is deciding:

- how a concrete execution run progresses
- what step failed or passed QA
- whether to run, retry, pause, or open a PR
- which artifacts, logs, or findings belong to a single delivery attempt

## Supporting Surfaces

These pages support the main workspaces:

- `/specifications/[id]`: artifact review
- `/steps/[id]`: step-level detail
- `/runs/[runId]`: run-level drill-down
- `/execution` and `/executions`: cross-project execution and CLI execution surfaces
- `/clarifications`: global clarification inbox
- `/quality`: aggregate QA dashboard
- `/windmill/*`: flow and job visibility
- `/ops/*`: global operations visibility

They should not replace the project/protocol pages as the main contributor workflow.

## Related Docs

- `FRONTEND-ARCHITECTURE.md`
- `SPECKIT-AND-EXECUTION-JOURNEYS.md`
- `WINDMILL-CONTRACTS.md`
