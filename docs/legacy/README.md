# Legacy Documentation Archive

This directory contains architecture/layer documents that were useful during migration and transition phases but are no longer authoritative.

## Archive Policy

- Archived docs are preserved for historical context.
- Active source of truth moved to canonical docs under `docs/DevGodzilla/` plus top-level `README.md`.
- When archived docs conflict with current code/runtime, trust current code and canonical docs.

## Canonical Docs (Active)

- `README.md`
- `docs/DevGodzilla/CURRENT_STATE.md`
- `docs/DevGodzilla/ARCHITECTURE.md`
- `docs/DevGodzilla/API-ARCHITECTURE.md`
- `docs/DevGodzilla/API-REFERENCE.md`
- `docs/DevGodzilla/BACKEND-FLOWS.md`
- `docs/DevGodzilla/STATE-MODELS.md`
- `docs/DevGodzilla/SUBSYSTEMS.md`
- `docs/DevGodzilla/OPERATIONS-OBSERVABILITY.md`
- `docs/DevGodzilla/FRONTEND-ARCHITECTURE.md`
- `docs/DevGodzilla/FRONTEND-WORKSPACES.md`
- `docs/DevGodzilla/FRONTEND-API-CONTRACTS.md`
- `docs/DevGodzilla/FRONTEND-COMPONENT-SYSTEM.md`
- `docs/DevGodzilla/WINDMILL-WORKFLOWS.md`
- `docs/DevGodzilla/WINDMILL-CONTRACTS.md`
- `docs/DevGodzilla/WINDMILL-OPERATIONS.md`
- `docs/DevGodzilla/FRONTEND-TEST-MAP.md`
- `docs/DevGodzilla/DOCS-MAINTENANCE.md`

## Migration Map

| Previous Path | Archived Path | Canonical Replacement |
|---|---|---|
| `docs/COMPREHENSIVE_ARCHITECTURE.md` | `docs/legacy/2026-02-21-COMPREHENSIVE_ARCHITECTURE.md` | `docs/DevGodzilla/ARCHITECTURE.md` |
| `docs/APP_ARCHITECTURE.md` | `docs/legacy/2026-02-21-APP_ARCHITECTURE.md` | `docs/DevGodzilla/CURRENT_STATE.md` |
| `docs/services-architecture.md` | `docs/legacy/2026-02-21-services-architecture.md` | `docs/DevGodzilla/ARCHITECTURE.md` |
| `docs/services-status.md` | `docs/legacy/2026-02-21-services-status.md` | `docs/DevGodzilla/CURRENT_STATE.md` |
| `docs/services-dependencies.md` | `docs/legacy/2026-02-21-services-dependencies.md` | `docs/DevGodzilla/ARCHITECTURE.md` |
| `docs/services-migration-guide.md` | `docs/legacy/2026-02-21-services-migration-guide.md` | `docs/DevGodzilla/ARCHITECTURE.md` |
| `docs/services-verification-report.md` | `docs/legacy/2026-02-21-services-verification-report.md` | `docs/DevGodzilla/CURRENT_STATE.md` |
| `docs/implementation-plan.md` | `docs/legacy/2026-02-21-implementation-plan.md` | `docs/DevGodzilla/ARCHITECTURE.md` |
| `docs/DevGodzilla/IMPLEMENTATION-PLAN.md` | `docs/legacy/2026-02-21-DevGodzilla-IMPLEMENTATION-PLAN.md` | `docs/DevGodzilla/ARCHITECTURE.md` |
| `docs/api-reference.md` | `docs/legacy/2026-02-21-api-reference.md` | `docs/DevGodzilla/API-ARCHITECTURE.md` + `/openapi.json` |
| `docs/frontend-solution-architecture.md` | `docs/legacy/2026-02-21-frontend-solution-architecture.md` | `docs/DevGodzilla/FRONTEND-ARCHITECTURE.md` |
| `docs/DevGodzilla/subsystems/*` | `docs/legacy/2026-02-21-DevGodzilla-subsystems/*` | `docs/DevGodzilla/SUBSYSTEMS.md` |
| `docs/DevGodzilla/INTEGRATED_SOLUTION_DESIGN.md` | `docs/legacy/2026-02-21-DevGodzilla-INTEGRATED_SOLUTION_DESIGN.md` | `docs/DevGodzilla/ARCHITECTURE.md` |
| `docs/DevGodzilla/AGENTS.md` | `docs/legacy/2026-02-21-DevGodzilla-AGENTS.md` | `docs/DevGodzilla/ARCHITECTURE.md` |
| `docs/cli-workflow-harness-usage.md` | `docs/legacy/2026-02-21-cli-workflow-harness-usage.md` | `docs/cli.md` |
| `docs/manual-workflow-testing.md` | `docs/legacy/2026-02-21-manual-workflow-testing.md` | `docs/ci.md` + `scripts/test_*.sh` |
| `docs/e2e-testing-guide.md` | `docs/legacy/2026-02-21-e2e-testing-guide.md` | `docs/ci.md` + `tests/e2e/` |
| `docs/SPEC_KIT_EXECUTION_PLAN.md` | `docs/legacy/2026-02-21-SPEC_KIT_EXECUTION_PLAN.md` | `docs/DevGodzilla/ARCHITECTURE.md` |
| `docs/SPEC_KIT_INTEGRATION_PLAN.md` | `docs/legacy/2026-02-21-SPEC_KIT_INTEGRATION_PLAN.md` | `docs/DevGodzilla/ARCHITECTURE.md` |
| `docs/devgodzilla_frontend_windmill_integration_plan.md` | `docs/legacy/2026-02-21-devgodzilla_frontend_windmill_integration_plan.md` | `docs/DevGodzilla/WINDMILL-WORKFLOWS.md` + `docs/DevGodzilla/CURRENT_STATE.md` |
| `docs/snug-seeking-crane.md` | `docs/legacy/2026-02-21-snug-seeking-crane.md` | `docs/DevGodzilla/CURRENT_STATE.md` |
| `docs/tui-improvement-plan.md` | `docs/legacy/2026-02-21-tui-improvement-plan.md` | `docs/cli.md` |

## Notes

Some archived content contains historical `tasksgodzilla` naming and aspirational designs that are intentionally preserved.

Use `python3 scripts/docs_inventory.py` when reviewing or refreshing the canonical docs to compare the live code surface against the active doc set.
