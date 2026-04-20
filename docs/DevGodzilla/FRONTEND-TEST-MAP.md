# DevGodzilla Frontend Test Map

> Status: Active
> Scope: Map frontend and cross-stack tests to supported UI behavior and contributor-facing contracts
> Source of truth: `frontend/`, `tests/`, `tests/e2e/`
> Last updated: 2026-04-20

## Summary

A meaningful part of the real frontend specification currently lives in tests.

Use this page to understand which behavior is already contract-tested before changing routes, hooks, workspaces, or Windmill-connected views.

The active frontend-specific suite lives primarily under `frontend/__tests__/`, with additional backend API and e2e coverage under `tests/` and `tests/e2e/`.

## Frontend-Facing Behavior Covered By Tests

### Project and protocol workflows

Representative coverage areas:

- project workspace behavior
- protocol detail actions and drill-down surfaces
- project-to-spec-to-protocol transitions
- specification review paths
- task-cycle and sprint-linked behavior

Relevant test families include:

- `frontend/__tests__/workflow/project-route-helpers.test.ts`
- `frontend/__tests__/workflow/generate-specs-workflow.test.tsx`
- `frontend/__tests__/workflow/manual-wizard-recovery-links.test.tsx`
- `frontend/__tests__/workflow/protocol-sync-sprint.test.tsx`
- protocol/state transition tests
- step and protocol UI API tests

### Onboarding and discovery

Representative coverage areas:

- onboarding status shape
- background onboarding behavior
- discovery-agent and fallback flows
- blocking clarification effects

Relevant test families include:

- onboarding status tests
- onboarding queue service tests
- discovery-agent service tests
- project onboarding API tests

### SpecKit flows

Representative coverage areas:

- spec-run status values
- background fallback semantics
- artifact linkage and cleanup
- project-scoped SpecKit behavior

Relevant test families include:

- `test_devgodzilla_speckit.py`
- `test_devgodzilla_spec_run_statuses.py`
- project SpecKit API and integration tests
- `frontend/__tests__/workflow/generate-specs-wizard-validation.test.tsx`
- `frontend/__tests__/workflow/spec-workflow-entrypoints.test.tsx`

### Runs, logs, quality, and feedback

Representative coverage areas:

- run visibility
- QA verdict handling
- feedback loops
- CLI execution lifecycle
- streamed or recent log surfaces

Relevant test families include:

- QA pipeline tests
- quality service tests
- feedback router and feedback API tests
- CLI execution lifecycle tests
- `frontend/__tests__/websocket/websocket-properties.test.tsx`
- `frontend/__tests__/ui/data-table-properties.test.tsx`

### Dedicated frontend component and visualization coverage

Representative coverage areas:

- feature-level cards, feeds, and quality widgets
- agile task forms and sprint-linked UI
- charts and pipeline visualizations
- route helper formatting and review-link generation

Relevant test families include:

- `frontend/__tests__/features/*`
- `frontend/__tests__/agile/*`
- `frontend/__tests__/visualizations/*`
- `frontend/__tests__/workflow/*`

### Windmill and reconciliation

Representative coverage areas:

- flow/script contract shape
- Windmill asset imports
- backend flow and job passthrough routes
- reconciliation behavior

Relevant test families include:

- Windmill workflow tests
- Windmill client tests
- Windmill live integration tests
- reconciliation tests

## Frontend-Specific Code Areas To Check

When changing these code areas, check both local frontend tests and backend integration coverage:

- `frontend/app/projects/[id]/`
- `frontend/app/protocols/[id]/`
- `frontend/lib/api/`
- `frontend/lib/websocket/`
- `frontend/components/wizards/`
- `frontend/components/agile/`
- `frontend/app/windmill/`

## Audit Snapshot Note

`docs/FRONTEND_AUDIT.md` remains useful as a point-in-time audit artifact, but it is not the canonical architecture doc. Treat it as a snapshot that may lag the current route and feature surface.

## Related Docs

- `FRONTEND-ARCHITECTURE.md`
- `FRONTEND-WORKSPACES.md`
- `FRONTEND-API-CONTRACTS.md`
