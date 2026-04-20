# Frontend Audit Report — dev-pipeline

> Status: Audit snapshot
> Scope: Point-in-time parity and dead-hook audit from 2026-04-19
> Canonical replacements: `docs/DevGodzilla/FRONTEND-ARCHITECTURE.md`, `docs/DevGodzilla/FRONTEND-WORKSPACES.md`, `docs/DevGodzilla/FRONTEND-API-CONTRACTS.md`, `docs/DevGodzilla/FRONTEND-COMPONENT-SYSTEM.md`, `docs/DevGodzilla/FRONTEND-TEST-MAP.md`

**Date:** 2026-04-19  
**Pages audited:** 48 page.tsx files  
**Hooks audited:** 22 hook files, 169 exported hooks  
**Backend routes:** 29 route files, 215 endpoints  

---

## Summary

| Metric | Count |
|---|---|
| Total pages | 48 |
| Pages with issues | 1 |
| Pages that are redirects/stubs | 12 |
| Total hooks exported | 169 |
| Hooks used by pages/components | 124 |
| **Dead hooks (unused)** | **45** |
| Frontend API endpoints | 142 |
| Backend API endpoints | 215 |
| Matched (fe ↔ be) | 121 |
| Frontend-only (no backend) | 1 genuine |
| Backend-only (no frontend) | 94 |
| Hardcoded ports | 1 |
| Navigation issues | 0 |

---

## Pages with Issues

| Page | Issue |
|---|---|
| `/settings` | Hardcoded port `localhost:8011` in placeholder; calls `useChangePassword` → `POST /users/me/password` — **no backend endpoint** |

---

## Missing Backend Endpoint

| Frontend Call | Hook | Status |
|---|---|---|
| `POST /users/me/password` | `useChangePassword` (use-profile.ts) | **NO BACKEND ROUTE** |

---

## Dead Hooks (45 exported, never imported)

### By file:
- **use-cli-executions.ts** (5): useActiveCLIExecutions, useCLIExecution, useCLIExecutionLogStream, useCLIExecutionLogs, useCLIExecutions
- **use-constitution.ts** (6): useConstitution, useConstitutionMetadata, useHasConstitution, useResetConstitution, useSaveConstitution, useValidateConstitution
- **use-templates.ts** (10): useCreateTemplate, useDeleteTemplate, useDuplicateTemplate, useExportTemplate, useImportTemplate, useRenderTemplate, useTemplate, useTemplateCategories, useTemplates, useUpdateTemplate
- **use-toast-mutation.ts** (5): useCreateMutation, useDeleteMutation, useOptimisticMutation, useToastMutation, useUpdateMutation
- **use-speckit.ts** (3): useGeneratePlan, useGenerateTasks, useRunWorkflow
- **use-sprints.ts** (3): useImportTasksToSprint, useSprintTasks, useSprintVelocity
- **use-logs.ts** (2): useLogStream, useRecentLogs
- **use-events.ts** (3): useEvents, useEventsStreamFallbackError, useWebSocketEventStream
- **use-agents.ts** (2): useProjectAgentOverrides, useUpdateProjectAgentOverrides
- **use-steps.ts** (2): useStepArtifactContent, useStepArtifactDownloadUrl
- **use-quality.ts** (1): useProtocolQualityGates
- **use-specifications.ts** (1): useLinkSpecificationToSprint
- **use-projects.ts** (1): useWorkItemArtifactContent

---

## Backend-Only Endpoints (94 routes, no frontend consumer)

### Intentionally unused:
- Webhooks: `/webhooks/github`, `/webhooks/gitlab`, `/webhooks/windmill/*`
- Auth: `/auth/login`, `/auth/logout`, `/auth/refresh`, `/auth/me`
- Health probes: `/health/live`, `/health/ready`

### Unused feature areas:
- **Windmill/Flows** (6): `/flows`, `/flows/{id}`, `/flows/{id}/runs`, `/jobs`, `/jobs/{id}`, `/jobs/{id}/logs`
- **Reconciliation** (4): `/reconciliation/status`, `/reconciliation/protocols/{id}`, `/reconciliation/steps/{id}`, `/reconciliation/run`
- **Templates** (4): `/templates`, `/templates/{id}`, `/templates/import`, `/templates/{id}/duplicate`
- **Policy Packs detail** (2): `/policy_packs/{key}`, `/policy_packs/{key}/{version}`
- **Protocol actions** (7): cancel, start, pause, resume, open_pr, retry_latest, run_next_step
- **SpecKit non-project** (8): `/speckit/analyze`, `/checklist`, `/clarify`, `/implement`, `/init`, `/plan`, `/specify`, `/tasks`

---

## Recommendations

1. **Critical:** Implement `POST /users/me/password` backend endpoint or remove settings UI
2. **Cleanup:** 45 dead hooks — remove or mark for future use
3. **Features:** 94 backend endpoints without UI — Windmill, Reconciliation, Templates pages needed
4. **Low:** Replace hardcoded `localhost:8011` in settings placeholder
