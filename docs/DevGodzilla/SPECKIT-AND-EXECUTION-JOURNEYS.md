# DevGodzilla SpecKit And Execution Journeys

> Status: Active
> Scope: Canonical frontend and backend journeys from onboarding through spec generation, protocol execution, and sprint sync
> Source of truth: `frontend/lib/project-routes.ts`, `frontend/components/wizards/`, `frontend/components/speckit/`, `devgodzilla/api/routes/speckit.py`, `project_speckit.py`, `protocols.py`, `steps.py`
> Last updated: 2026-04-20

## Canonical Journey

The supported contributor journey in this repo is:

1. onboard or open a project
2. generate or review spec artifacts
3. produce tasks and optional implementation artifacts
4. create or inspect a protocol
5. execute steps with QA
6. sync results into sprint/task views
7. inspect logs, findings, and artifacts

## Entry Points

Primary entry points from the project workspace:

- spec workflow wizard via `wizard=generate-specs`
- manual design workflow via `wizard=design-solution`
- manual implementation workflow via `wizard=implement-feature`
- direct jump to execution tab via `tab=execution`

Primary recovery or review entry points:

- specification review path from `getSpecificationReviewPath()`
- protocol detail page for execution control
- run and step detail pages for deeper operational inspection

## Supported Paths

### Project onboarding to spec work

1. open `/projects/[id]`
2. inspect onboarding state
3. if needed, start or retry onboarding
4. move to the spec workspace or launch the generate-specs wizard

### SpecKit-driven path

1. run specify
2. answer clarifications if generated
3. run plan
4. optionally run checklist
5. run tasks
6. optionally run analyze
7. optionally run implement

This path maps to the backend `/speckit/*` or `/projects/{id}/speckit/*` routes and may return `202 Accepted` for longer-running stages.

### Protocol-driven execution path

1. create or resolve a protocol from spec outputs
2. open `/protocols/[id]`
3. start the protocol
4. run next step or use Windmill flow creation when needed
5. inspect steps, runs, logs, quality, policy, feedback, and artifacts
6. open a PR or sync to sprint

### Brownfield/task-cycle path

For smaller brownfield work, the supported path is a compressed version of the above:

1. onboard project
2. define the feature
3. generate tasks or a protocol
4. optionally sync to sprint

The Windmill `brownfield_feature` flow is the clearest current expression of that path.

## Happy Path Versus Manual Path

### Happy path

- use project workspace wizards
- let SpecKit produce artifacts in sequence
- create or start protocol
- allow step execution and QA to progress without manual intervention

### Manual path

- open spec workspace directly
- inspect or rerun individual SpecKit stages
- jump from project to specification detail pages
- control protocol state manually from the protocol workspace
- inspect Windmill/job/reconciliation pages when orchestration needs operator help

## Blocking Conditions

Typical blockers:

- onboarding clarifications
- SpecKit clarify stage
- protocol blocked or needs-QA state
- failed step execution
- reconciliation drift between DB and Windmill state

The UI handles these by exposing:

- clarification tabs and forms
- feedback tabs
- run and log drill-down
- websocket-driven refresh on protocol/step state changes

## Contributor Guidance

When adding a new wizard or journey:

- anchor it from the project workspace first
- preserve the project-routes helper conventions
- prefer extending the existing happy path rather than inventing a new isolated route family
- make manual recovery discoverable from the relevant workspace rather than from a hidden operator page

## Related Docs

- `FRONTEND-WORKSPACES.md`
- `BACKEND-FLOWS.md`
- `STATE-MODELS.md`
