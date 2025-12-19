# Integrated Solution Design (Onboarding + SpecKit + SWE Agents)

This document describes a single, coherent solution design that aligns the current
implementation of DevGodzilla (backend, frontend, Windmill) with SWE agents,
prompt-driven SpecKit workflows, and policy/clarification governance. It focuses
on closing the integration gaps without throwing away the working pieces that
exist today.

Primary reference points in code:
- SpecKit service: `devgodzilla/services/specification.py`
- Protocol planning: `devgodzilla/services/planning.py`
- Protocol generation: `devgodzilla/services/protocol_generation.py`
- Execution + QA: `devgodzilla/services/execution.py`, `devgodzilla/services/quality.py`
- Agents config: `devgodzilla/services/agent_config.py`, `config/agents.yaml`
- Frontend SpecKit wizards: `frontend/components/wizards/*spec*`
- Windmill API flows: `windmill/flows/devgodzilla/*`

---

## 1) Current Implementation Snapshot (Facts)

### Onboarding
- API endpoint: `POST /projects/{id}/actions/onboard` in `devgodzilla/api/routes/projects.py`
- Behavior: clone repo, checkout branch, init `.specify/`, optional discovery agent.
- Policy constitution is rendered, but clarifications are not persisted.

### SpecKit (agent-assisted)
- Artifacts: `.specify/` (constitution/templates), `specs/<feature>/` (spec/plan/tasks).
- Generation is prompt-driven via SWE agents (SpecKit prompts in `prompts/`).
- SpecKit runs are not recorded in DB and not linked to protocol runs.

### Protocol planning and execution
- Planning reads `.protocols/<protocol>/step-*.md` (or can be auto-generated).
- StepRuns are derived from protocol files, not from SpecKit tasks.
- Execution and QA run independently of SpecKit.

### Frontend
- SpecKit wizards call `/speckit/*` endpoints, but there is no bridge to protocols.
- Project wizard is UI-only and does not call onboarding/policy/clarification APIs.

### Windmill
- Flows mostly call DevGodzilla API wrappers for onboarding and SpecKit steps.
- No built-in flow that converts SpecKit tasks to protocol steps and executes them.

---

## 2) Gaps and Workflow Issues

1) SpecKit outputs are not linked to protocol runs.
- `specs/<feature>/tasks.md` never becomes a `ProtocolRun` or `StepRun`.

2) Agent config and engine registry are disconnected.
- `config/agents.yaml` and `AgentConfigService` are not used to bootstrap engines.

3) Prompt versions are not tracked for SpecKit or discovery runs.
- No prompt hash, version, or model usage stored in DB for spec/plan/tasks.

4) Clarifications are not first-class for onboarding or SpecKit.
- Policy clarifications are appended to spec markdown, but not stored as
  `clarifications` rows, and cannot block workflows.

5) QA does not consume SpecKit checklists.
- Checklists exist as documents, but QA gates do not read them.

6) `/speckit/workflow` ignores `skip_existing`.
- The API accepts the field but does not implement the logic.

---

## 3) Target Unified Design (Single Workflow)

### 3.1 Unified lifecycle (high level)

1. **Project create + policy selection**
2. **Onboarding**: clone repo, init `.specify/`, discovery, clarifications
3. **SpecKit workflow**: spec -> plan -> tasks -> checklist -> analyze
4. **Spec -> Protocol**: translate tasks to `ProtocolSpec` and step files
5. **Execution**: StepRuns execute via engine registry
6. **QA**: standard gates + optional SpecKit checklist gate
7. **Feedback loop**: clarifications -> re-spec or re-plan as needed

### 3.2 Data model and artifacts (minimal additions)

Use existing tables where possible:
- `protocol_runs.speckit_metadata` to link SpecKit outputs.
- `job_runs` to record SpecKit agent runs with prompt metadata.

Suggested metadata payload for `speckit_metadata`:
```
{
  "spec_path": "specs/001-feature/spec.md",
  "plan_path": "specs/001-feature/plan.md",
  "tasks_path": "specs/001-feature/tasks.md",
  "checklist_path": "specs/001-feature/checklist.md",
  "protocol_root": "specs/001-feature/_runtime",
  "spec_hash": "<hash>",
  "prompt_versions": {
    "specify": "<sha>",
    "plan": "<sha>",
    "tasks": "<sha>"
  }
}
```

### 3.3 SpecKit -> Protocol translation (core missing bridge)

Create a dedicated adapter that:
- Parses `specs/<feature>/tasks.md` (reuse `TaskSyncService.parse_task_markdown`).
- Groups tasks by phase or category and generates step files under:
  - `specs/<feature>/_runtime/step-01-*.md`
  - Each step file references the spec and plan paths.
- Sets `protocol_root` to `specs/<feature>/_runtime` for the run.
- Builds and stores `ProtocolSpec` in `protocol_runs.template_config`.
- Records the link in `protocol_runs.speckit_metadata`.

This allows the existing PlanningService to reuse the current execution path.

### 3.4 Agent and prompt registry alignment

Align YAML agent config with runtime engines:
- Bootstrap `devgodzilla.engines` from `AgentConfigService` on API start.
- Use `AgentConfig.default_model` and `sandbox` in `EngineRequest`.
- Record prompt paths + hashes in `job_runs.prompt_version` or `events`.

### 3.5 Clarifications as first-class gates

On onboarding and spec generation:
- Materialize policy clarifications to `clarifications` table.
- Block onboarding and planning when `blocking=true` and unanswered.
- On answer, update spec markdown and unblock workflows.

### 3.6 QA + SpecKit checklist integration

If `checklist.md` exists:
- Populate a `ChecklistGate` with required items or patterns.
- Store checklist results as QA findings and events.

---

## 4) API Contract (proposed additions)

1) `POST /protocols/from-spec`
   - Input: `project_id`, `spec_path` or `tasks_path`, optional `protocol_name`.
   - Output: `protocol_run_id`, `protocol_root`, `step_count`.

2) `POST /speckit/workflow` (fix)
   - Implement `skip_existing` and return what was skipped.
   - Record prompt versions and outputs in `job_runs`.

3) `GET /projects/{id}/onboarding`
   - Include clarification status and discovery summary.

---

## 5) Frontend and Windmill alignment

### Frontend
- Wire `ProjectWizard` to:
  - `POST /projects`
  - `PUT /projects/{id}/policy`
  - `POST /projects/{id}/onboarding/actions/start`
  - `GET /projects/{id}/clarifications`
- Add "Create protocol from SpecKit tasks" action in SpecKit wizard.

### Missing UI/UX interfaces and pages (add to plan)
- Project onboarding status page (stages, discovery outputs, blocking clarifications).
- SpecKit workspace page (spec/plan/tasks/checklist/analyze list + run history).
- Spec -> Protocol action surface (button + status + new protocol link).
- Protocol run detail page (links to spec/plan/tasks, step list, QA verdicts).
- Clarifications inbox (project/protocol/step scope, open vs answered).
- Agent registry page (health, default models, enable/disable).
- Prompt catalog view (prompt list + version hash + last-used metadata).
- QA checklist viewer (parsed checklist + last run verdicts).

### Windmill
- Add flow: `spec_to_protocol` (API wrapper) that:
  - runs `/speckit/workflow` then `/protocols/from-spec`.
- Keep existing API-wrapper scripts as the supported path.

---

## 6) Implementation Phases (small, safe steps)

Phase 1: SpecKit -> Protocol adapter
- New service (adapter) that generates step files from tasks.
- Store `speckit_metadata` on protocol runs.
- Add `/protocols/from-spec` endpoint.
- Wire SpecKit wizard to trigger protocol creation.

Phase 2: Agent + prompt registry alignment
- Bootstrap engines from agent config.
- Record prompt hashes in `job_runs`.
- Add agent registry UI with health/status.

Phase 3: Clarifications and onboarding coupling
- Persist policy clarifications and block on missing answers.
- Update frontend and windmill flows to surface clarifications.
- Add clarifications inbox UI and onboarding status page.

Phase 4: QA checklist integration
- Map SpecKit checklist into QA gate inputs.
- Add checklist viewer in protocol/spec pages.

---

## 7) Summary

This design keeps the current, working pieces (SpecKit prompts, protocol runs,
execution/QA, Windmill API wrappers) and introduces a single missing bridge:
SpecKit tasks are translated into protocol steps and linked as first-class runs.
With a unified agent registry and prompt tracking, onboarding + SpecKit + SWE
agents become one coherent pipeline.
