# PR Plan (P0): Convergence + Correctness

This plan turns the P0 items from `docs/DevGodzilla/ARCHITECTURE_REVIEW.md` into a concrete, shippable PR.

## Goals

1. **Single supported stack**: DevGodzilla only (no TasksGodzilla dependency).
2. **Reduce split-brain Windmill integration**:
   - Standardize on **API-wrapper Windmill scripts** (`*_api.py`) as the supported execution model.
3. **Documentation matches reality**:
   - Clear “what runs today” documentation.
   - Fix SpecKit integration wording (it is template-based today, not an external `specify` dependency).

## Non-goals (for this PR)

- Add production auth/RBAC (tracked as P1).
- Build out embedded React UI wiring (tracked as P1).
- Implement DB-backed event streaming (tracked as P1).

## Deliverables

### A) Documentation

- Add `docs/DevGodzilla/CURRENT_STATE.md` explaining:
  - runtime topology (compose services)
  - current planning model (`.protocols/<protocol>/step-*.md` → StepRuns)
  - current SpecKit artifact generation (`.specify/` templates)
  - supported Windmill flows and scripts
- Link the current-state doc from:
  - `docs/DevGodzilla/ARCHITECTURE.md`
  - `docs/DevGodzilla/WINDMILL-WORKFLOWS.md`

### B) SpecKit wording convergence

- Update `devgodzilla/services/specification.py` docstrings to match behavior:
  - Spec/plan/tasks generation is template-based today (no external CLI requirement).
- Add/extend `.gitignore` to ignore `.specify/specs/*/_runtime/runs/` (code creates it).

### C) Windmill convergence (supported execution model)

**Supported model (after this PR):**
- Windmill scripts call the DevGodzilla API (`windmill/scripts/devgodzilla/*_api.py`).
- DevGodzilla holds Windmill token server-side; browser never needs it.

Changes:
- Update DevGodzilla flow generator defaults to use API-wrapper scripts:
  - `u/devgodzilla/step_execute_api`
  - `u/devgodzilla/step_run_qa_api`
- Update `devgodzilla/services/orchestrator.py` Windmill dispatch to use API-wrapper scripts:
  - planning: `u/devgodzilla/protocol_plan_and_wait`
  - step exec: `u/devgodzilla/step_execute_api`
  - QA: `u/devgodzilla/step_run_qa_api`
- Fix or deprecate broken/demo exported flows:
  - Update `windmill/flows/devgodzilla/execute_protocol.flow.json` to use step-run IDs + API scripts.
  - Update `windmill/flows/devgodzilla/spec_to_tasks.flow.json` to use `speckit_*_api` scripts and `project_id` (not `project_path`).
  - Move `windmill/flows/devgodzilla/full_protocol.flow.json` out of the default import set (it is currently inconsistent/dummy).

### D) Tests / validation

- Update `tests/test_devgodzilla_windmill_workflows.py` to assert the new script paths.
- Run `pytest -q tests/test_devgodzilla_*.py`.

## Suggested follow-ups (P1)

- Add minimal API auth + restricted CORS for non-local environments.
- Provide a UI-safe “runs/logs/artifacts/events” contract for the embedded React app.
- Wire SSE events to persisted DB events and service lifecycle signals.

