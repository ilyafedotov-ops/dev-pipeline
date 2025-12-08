# Services Refactor – Implementation Status

This document tracks progress on the new `tasksgodzilla.services.*` layer and the
service-oriented refactor. It complements `STATUS.md` (orchestrator track) and
`docs/services-architecture.md`.

## Scope

- Define a forward-looking services API under `tasksgodzilla/services/…`.
- Migrate API/CLI/TUI and workers to use services instead of legacy helpers.
- Allow non-backwards-compatible changes to old worker flows where needed.

## High-level milestones

- [x] **Architecture & plan**
  - `docs/services-architecture.md` describing target services and platform layers.
  - Decision: services layer is the new primary contract; legacy worker helpers
    may be simplified or removed as we migrate.

- [x] **Initial service stubs**
  - `tasksgodzilla/services/orchestrator.py` (`OrchestratorService`)
  - `tasksgodzilla/services/execution.py` (`ExecutionService`)
  - `tasksgodzilla/services/onboarding.py` (`OnboardingService`)
  - `tasksgodzilla/services/spec.py` (`SpecService`)
  - `tasksgodzilla/services/quality.py` (`QualityService`)
  - `tasksgodzilla/services/prompts.py` (`PromptService`)
  - `tasksgodzilla/services/decomposition.py` (`DecompositionService`)
  - `tasksgodzilla/services/platform/queue.py` (`QueueService`)
  - `tasksgodzilla/services/platform/telemetry.py` (`TelemetryService`)

- [x] **Wire services into API**
  - Replace direct calls to `codex_worker`, `project_setup`, and raw DB helpers
    in `tasksgodzilla/api/app.py` with service calls.
  - [x] Use `OrchestratorService.create_protocol_run` for `/projects/{project_id}/protocols`.
  - [x] Route protocol actions `start|run_next_step|retry_latest` through `OrchestratorService`.
  - [x] Expose onboarding start via `/projects/{id}/onboarding/actions/start` (service-backed job enqueue).
  - [x] Route open_pr enqueue through `OrchestratorService` (`/protocols/{id}/actions/open_pr`).
  - [x] Zero direct worker imports in `api/app.py` - all routes use services.
  - Request/response shapes remain compatible for existing clients.

- [ ] **Wire services into CLI/TUI**
  - Update `tasksgodzilla/cli/main.py` and `scripts/tasksgodzilla_cli.py` to use
    `OnboardingService`, `OrchestratorService`, and `ExecutionService`.
  - TUI flows use API or service client wrappers instead of reaching into workers.

- [x] **Refactor worker job handlers**
  - Change `tasksgodzilla/worker_runtime.process_job` to call services:
    - [x] `plan_protocol_job` → `OrchestratorService.plan_protocol`
    - [x] `execute_step_job` → `ExecutionService.execute_step`
    - [x] `run_quality_job` → `QualityService.run_for_step_run`
    - [x] `project_setup_job` → `OnboardingService.run_project_setup_job`
    - [x] `open_pr_job` → `OrchestratorService.open_protocol_pr`
    - [x] `codemachine_import_job` → `CodeMachineService.import_workspace`
  - Job payloads and event shapes remain stable.

- [ ] **Move orchestration logic out of `codex_worker`**
  - Gradually migrate planning/decomposition/QA/loop/trigger logic into
    `OrchestratorService`, `SpecService`, `DecompositionService`, and `QualityService`.
  - Leave `codex_worker` as a thin adapter (or retire it once all callers use services).

- [x] **Service-level tests**
  - Add focused tests for each service:
    - [x] Orchestrator: protocol lifecycle transitions and policy behaviour (`tests/test_orchestrator_service.py` - 10 tests)
    - [x] Execution: correct delegation to worker (`tests/test_execution_service.py` - 2 tests)
    - [x] Quality: QA delegation and direct evaluation (`tests/test_quality_service.py` - 4 tests)
    - [x] Onboarding: project creation and workspace/onboarding flows (`tests/test_onboarding_service.py` - 2 tests)
    - [x] Spec: spec build/validate + step creation (`tests/test_spec_service.py` - 6 tests)
    - [x] Platform services: Queue and Telemetry (`tests/test_platform_services.py` - 7 tests)
  - Tests use mocks and do not depend on legacy worker internals.

- [x] **Docs and migration notes**
  - [x] Updated `docs/orchestrator.md` to include Services Layer section with all 9 services documented
  - [x] Updated `docs/architecture.md` to reference services layer in control plane section
  - [x] Created `docs/services-migration-guide.md` with comprehensive migration patterns and examples for contributors
  - Services layer is now documented as the primary integration surface

## Current focus

- ✅ **Service-level tests complete** (44 tests across 9 test files, 100% pass rate)
- ✅ **Documentation updated** to reflect services as primary integration surface
- ✅ **API integration complete** - Zero direct worker imports, all routes use services
- ✅ **Worker integration complete** - All 6 job types delegate to services
- ✅ **Phase 1 Quick Wins Complete:**
  - Created `CodeMachineService` for workspace imports
  - Added `check_and_complete_protocol` to `OrchestratorService`
  - Removed all direct worker imports from `api/app.py`
  - All API routes now use services exclusively
- ✅ **Phase 2 Structural Improvements Complete:**
  - Extracted git logic to `GitService`
  - Refactored `codex_worker.py` to use `GitService`
  - Added comprehensive tests for `GitService` (9 tests)
  - Added unit tests for `CodeMachineService` (1 test)
  - Created `BudgetService` with tests (2 tests)
- ✅ **Verification Complete:** See `docs/services-verification-report.md` for full analysis
- Next: Phase 3 - Deep Refactoring (optional, ongoing - extract logic from codex_worker opportunistically)

