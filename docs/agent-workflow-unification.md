# Agentic Workflow Unification

This document captures the current redundancy between Codex- and CodeMachine-driven paths, the target single workflow design, and a task-split implementation plan.

## What We Found
- Two parallel execution paths: Codex (planning/exec/QA via `scripts/protocol_pipeline.py` and `codex_worker`) and CodeMachine (import/runtime adapter via `codemachine_worker`), with different prompt resolution, QA behavior (CodeMachine skips QA), and outputs.
- Planning/import split: Codex planning creates `.protocols/<run>/` from `prompts/protocol-new.prompt.md`, while CodeMachine imports `.codemachine` templates and writes outputs under `.protocols/<run>/` (including `aux/codemachine/**`), but without a shared step spec.
- Engine dispatch is implicit: `handle_execute_step` branches on `is_codemachine_run` instead of using a uniform engine registry contract; policies (loop/trigger) and events differ subtly between the paths.
- Observability gaps: token estimates, prompt versions, and QA verdicts are recorded unevenly; CodeMachine executions bypass QA and thus skip metrics and gating.
- Best-practice delta (Context7 Better Agents): projects should have a single standardized structure, versioned prompts, scenario tests for every capability, uniform QA/evaluation, and full observability regardless of engine.

## Target Design (Single Protocol Runner)
- One `ProtocolSpec`/`StepSpec` drives all runs: each step records `engine_id`, `model`, `prompt_ref`, `inputs`, `outputs`, and `policies` (loop/trigger).
- Engines plug in via `tasksgodzilla.engines.registry`; Codex and CodeMachine become interchangeable backends. Prompt resolution/output paths live in a shared adapter that uses the spec rather than branching.
- QA is explicit on every step: spec carries QA config (engine/model/prompt/policy). “Skip QA” is a declared policy, not implicit for CodeMachine.
- Planning/import unify: Codex planning and CodeMachine import both emit the same `ProtocolSpec` and the same `.protocols/<run>/` artifacts; step rows are created from the spec, not inferred separately.
- Observability unified: events include prompt versions, models, token estimates, outputs map, and policy decisions for every engine.
- Artifacts contract: a single outputs map `{protocol: <path>, aux: {...}}`; CodeMachine writes to `aux.codemachine` without changing downstream consumers.

## Implementation Plan (Tasks)
1) Spec Schema and Persistence
   - Define `ProtocolSpec`/`StepSpec` JSON schema (engine, model, prompt_ref, inputs, outputs, policies, qa config).
   - Store the spec on `ProtocolRun.template_config` and emit it from both Codex planning and CodeMachine import.
   - Update `sync_step_runs_from_protocol` to source step rows from the spec instead of only filename inference.
2) Unified Prompt/Output Resolver
   - Introduce `resolve_prompt_and_outputs(step_spec, run)` that handles prompt resolution (Codex or CodeMachine) and returns output destinations (protocol + aux).
   - Refactor `handle_execute_step` to call the resolver, pick the engine from the registry, and execute through a single code path.
3) QA Normalization
   - Add QA config to CodeMachine imports; extend spec to carry `qa_policy: skip|light|full`, engine/model/prompt.
   - Refactor `handle_quality` to use the spec QA settings and remove the implicit CodeMachine QA skip.
4) Policy Unification
   - Keep loop/trigger policies in one module; ensure both exec and QA phases apply them uniformly.
   - Preserve inline trigger depth guard (`MAX_INLINE_TRIGGER_DEPTH`) and use the same enqueue/inline flow for all engines.
5) Observability and Events
   - Record prompt versions, models, token estimates, outputs map, and policy decisions on all events across engines.
   - Ensure QA verdicts for CodeMachine steps are captured (or marked skipped explicitly per policy).
6) Tests and Scenarios
   - Add unit tests for spec loader/emitter (Codex planning, CodeMachine import) and prompt/output resolver.
   - Add scenario tests covering mixed-engine runs and QA behavior with spec-driven config.
   - Maintain token-budget and policy edge-case coverage (loop, trigger depth, missing engine).
7) Migration and Compatibility
   - Provide a migration path to backfill `ProtocolSpec` for existing runs (best-effort).
   - Keep CLI surfaces stable; engines and QA selection remain configurable via project defaults and env.

## Current Behavior Notes
- Spec validation is enforced: missing `prompt_ref` emits `spec_validation_error`, blocks the protocol, and fails the step.
- Codex execution honors spec outputs: when `outputs` are present in the `StepSpec`, Codex stdout is written to the specified protocol path and any auxiliary paths (mirrors CodeMachine dual writes).

## Next Implementation Steps
- Execution path unification: fold Codex and CodeMachine into a single resolver/dispatch path for steps (currently still branched).
- Policy coverage: expand scenario tests for mixed-engine runs with loop/trigger policies and inline trigger depth limits.
- Migration automation: add a job/CLI to backfill specs across projects and report validation summaries to operators (spec_audit job added).

## Progress Checklist
- [x] Unified spec helpers created for Codex/CodeMachine with step creation from spec.
- [x] Spec validation enforced at execution/import; failures block with `spec_validation_error`.
- [x] Codex execution now uses spec for engine/model/prompt_ref and writes stdout to spec-declared outputs (protocol + aux).
- [x] QA path reads spec QA policy/model/prompt and skips only when policy says so; CodeMachine QA can be enabled via spec.
- [x] Prompt versions recorded for exec/QA events; outputs metadata attached.
- [x] Codex prompt resolver to support arbitrary prompt_ref outside `.protocols/` (with evented versioning).
- [x] Formal JSON Schema for `ProtocolSpec` + CLI to validate/backfill existing runs.
- [x] Expanded scenario tests for custom QA prompts/engines and spec hash/version observability.
