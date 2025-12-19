# Policy Framework + SpecKit Implementation Plan

This plan breaks the policy framework integration into scoped tasks, grouped by
prioritized PRs (backend -> frontend -> windmill). Each task includes scope and
acceptance criteria so work can be tracked and reviewed incrementally.

## PR 1 - Backend contracts + missing endpoint (highest priority)

### Tasks
- Add `GET /steps/{id}/policy/findings` endpoint in `devgodzilla/api/routes/steps.py`.
- Normalize enforcement mode to `off|warn|block` and accept legacy values
  (`advisory|mandatory|enforce`) in `devgodzilla/api/schemas.py` or request
  handlers.
- Align policy findings shape: either add `location` to the API response or map
  `metadata` to a consistent display field.
- Support repo-local policy overrides from both `.devgodzilla/policy.*` and
  `.tasksgodzilla/policy.*` in `devgodzilla/services/policy.py`.
- Allow `PolicyPackContent.clarifications` to accept list shapes (normalize if a
  dict is supplied).

### Acceptance criteria
- `GET /steps/{id}/policy/findings` returns findings successfully.
- Project policy updates accept `off|warn|block` and legacy values.
- Repo-local policy loads from either supported path.

## PR 2 - Policy <-> SpecKit constitution sync (backend)

### Tasks
- Add policy-to-constitution renderer (policy -> markdown) in
  `devgodzilla/services/policy.py` or a dedicated helper.
- On SpecKit init, seed `constitution.md` from policy (if configured) in
  `devgodzilla/services/specification.py`.
- On policy update, optionally sync the constitution if `.specify` exists.
- Add `POST /projects/{id}/speckit/constitution/sync` API endpoint for explicit
  sync (thin wrapper over `SpecificationService.update_constitution`).

### Acceptance criteria
- Policy pack changes update constitution content or explicit sync endpoint does.
- Constitution hash updates on project record.

## PR 3 - SpecKit artifacts get policy guidelines + clarifications (backend)

### Tasks
- Inject policy guidelines into SpecKit templates by adding
  `{{ policy_guidelines }}` placeholders to default templates.
- Update `SpecificationService.run_specify` / `run_plan` to provide policy
  guidelines values and populate templates accordingly.
- Auto-append policy clarifications to spec files after generation using
  `run_clarify` (filter by `applies_to=planning|spec`).

### Acceptance criteria
- Generated `spec.md` and `plan.md` include policy guidelines.
- Policy clarifications appear in spec artifacts after generation.

## PR 4 - Execution/QA gating by policy (backend)

### Tasks
- Pre-execution check in `devgodzilla/services/execution.py` for blocking
  clarifications and blocking findings; mark steps as `blocked` when applicable.
- Apply policy defaults in `devgodzilla/services/quality.py` for gate selection
  and QA policy (`skip|light|full`).
- Emit `policy_finding` events for project/protocol/step scopes.

### Acceptance criteria
- In `block` mode, missing requirements/clarifications halt execution with
  `status=blocked`.
- In `warn` mode, execution proceeds and findings are visible.

## PR 5 - SpecKit canonical specs layout + SWE agent docs (backend + tooling)

### Tasks
- Enforce canonical specs layout (`specs/`) and spec filename (`spec.md`) across
  services/routes/CLI.
- Remove legacy fallbacks for `.specify/specs` and `feature-spec.md`.
- Add prompt-driven SWE agent generation for spec/plan/tasks/checklist/analyze.
- Update Windmill scripts and helpers to target `specs/`.
- Update tests and docs to reflect the canonical layout and prompts.

### Acceptance criteria
- SpecKit artifacts are written under `specs/<spec_id>/` with `spec.md`.
- SpecKit generation invokes a SWE agent using prompt files; failures surface.
- API/CLI/Windmill flows reference `specs/` consistently.

## PR 6 - Frontend policy + SpecKit UX wiring (frontend)

### Tasks
- Update enforcement mode types and labels in `frontend/lib/api/types.ts` and
  UI widgets.
- Wire `ProjectWizard` to `POST /projects`, then set policy via
  `PUT /projects/{id}/policy`, then trigger SpecKit init.
- Add clarifications view + answer flow for projects/protocols in the console.
- Show constitution sync status in the policy tab (or SpecKit status panel).

### Acceptance criteria
- Wizard creates a project, sets policy, and initializes SpecKit.
- Clarifications are visible and answerable in UI.

## PR 7 - Windmill scripts + app wiring (windmill)

### Tasks
- Replace local service calls in `windmill/scripts/devgodzilla/handle_feedback.py`
  with API calls.
- Add scripts for listing policy findings (project/protocol/step) and pending
  clarifications.
- Wire policy findings + clarifications into Windmill apps/flows.

### Acceptance criteria
- Windmill apps display policy findings and clarifications without errors.
- SpecKit flows accept clarifications as inputs.

## Decisions
- Source of truth: policy is preferred; keep bidirectional sync by embedding
  policy JSON in constitution and syncing on constitution edits.
- Clarification auto-append phases: pending (default to `planning|spec`).
