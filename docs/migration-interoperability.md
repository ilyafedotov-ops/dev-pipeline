# Migration & Interoperability Plan: dev-pipeline ↔ CodeMachine-CLI

This document defines how to integrate CodeMachine-CLI’s workflow/agent model with the dev-pipeline orchestrator (TasksGodzilla_Ilyas_Edition_1.0), and how to evolve our architecture to support multi-engine, CodeMachine-style workflows.

---

## 1) Goals & Scope

- **Interop, not rewrite**: Run CodeMachine-style workflows under our orchestrator (FastAPI + Redis/RQ + Postgres/SQLite) without forking or deeply modifying CodeMachine’s core.
- **Richer workflows**: Add engine-pluggable, loop/trigger-capable agent configurations to our stack, inspired by CodeMachine’s `main/sub/modules` model.
- **Distribution-ready tooling**: Introduce release/distribution workflows (binaries + npm) modeled after CodeMachine’s CI so the orchestrator tooling can be installed and updated like a product.

**Out of scope (initially):**
- Replacing CodeMachine’s internal runtime with our own.
- Backporting our orchestrator concepts into the upstream CodeMachine repository.

---

## 2) Success Criteria

- **Template execution:** A CodeMachine template (main agents + modules) runs via our API/worker, with `ProtocolRun`/`StepRun` persisted in DB, and artifacts written to a git worktree.
- **Engine choice per step:** Multi-engine support (Codex + ≥1 other CLI engine) is configurable per step/agent and enforced by policies.
- **Traceable behavior:** Loop/trigger decisions are visible in our console (events + timelines) and match CodeMachine’s semantics.
- **Productized tooling:** Tagged releases build/publish binaries and an npm package via CI; docs are published automatically on main/tag pushes.

---

## 3) Current-State Snapshot

### 3.1 Our Orchestrator (dev-pipeline)

- **Control plane:** FastAPI service with domain model for `Project`, `ProtocolRun`, `StepRun`, and `Event`, backed by Postgres/SQLite with Alembic migrations.
- **Execution:** Redis/RQ workers for Codex-heavy jobs (planning, execution, QA) and Git/CI jobs (clone, worktrees, PR/MR, CI webhook processing).
- **Artifacts & git:** Protocols live in `.protocols/NNNN-[task]/` under per-task worktrees; Codex CLI is the primary engine.
- **QA & governance:** `scripts/quality_orchestrator.py` implements QA gates; `docs/solution-design.md` defines state machines, budgets, and automation flags.
- **CI:** Dual GitHub/GitLab CI that call `scripts/ci/*.sh` (currently mostly stubs) and can report status back to the orchestrator via `/webhooks/*`.

### 3.2 CodeMachine-CLI

- **Runtime:** Bun/TypeScript CLI that runs in interactive mode or via commands (`codemachine start`, etc.).
- **Workspace:** Uses a `.codemachine/` folder with inputs (`inputs/specifications.md`), selected template, engine configs, and outputs.
- **Agent model:** Config-driven agents and modules declared under `config/`:
  - `main.agents.js` – primary workflow agents (architecture, plan, task breakdown, context manager, code generation, task sanity check, runtime prep, git commit, fallbacks).
  - `sub.agents.js` – specialized sub-agents (frontend-dev, backend-dev, QA, architects) for delegation and parallelization.
  - `modules.js` – workflow modules with `loop` and `trigger` behaviors (e.g., `check-task`, `iteration-checker`).
  - `placeholders.js` – path placeholders used in prompt resolution.
- **Workflows:** Templates and utilities under `src/workflows/**` implement step resolution (`resolveStep`, `resolveFolder`, `resolveModule`, `resolveUI`) and validate templates.
- **Multi-engine:** Supports multiple CLI engines (Codex CLI, Claude Code, CCR, Cursor, OpenCode, Auggie; Gemini/Qwen planned) mapped into agents via configuration.
- **CI & releases:** GitHub Actions build platform-specific binaries (`build-binaries.yml`), publish npm packages (`publish.yml`), and deploy docs with mike/MkDocs (`publish_docs.yml`).

### 3.3 Key Differences Driving Design

- **Control surface:** Our system is API/console-first and server-based; CodeMachine is CLI/TUI-first and runs locally per workspace.
- **State:** We persist orchestrator state in a DB and use git worktrees; CodeMachine persists in `.codemachine/` files without a central DB.
- **Workflow model:** We use fixed protocol prompts and schemas; CodeMachine uses configurable agent graphs plus loop/trigger modules.
- **Distribution:** Our tooling is repo-local; CodeMachine ships binaries/npm packages and treats itself as a product.

---

## 4) Interop Principles & Use Cases

### 4.1 Design Principles

- **Single control plane:** Our orchestrator remains the source of truth for long-running workflows, status, and metrics.
- **Config as contract:** Interop is driven by configuration (`config/*.js`, template JSON) rather than manual wiring.
- **Non-invasive:** Avoid forking CodeMachine; treat it as a configurable “workflow spec” that our runtime adapter can interpret.
- **Observability-first:** Every loop/trigger decision and engine call should be observable (events/metrics) and attributable to a project/protocol/step.

### 4.2 Primary Interop Use Cases

1. **Run CodeMachine templates via our orchestrator**
   - Import a CodeMachine template and execute its main agents/modules as `StepRun`s inside our ProtocolRun, using our workers and git worktrees.

2. **Add CodeMachine-style behavior to existing protocols**
   - Reuse loop and trigger patterns (e.g., task verification, iteration checker) for our native protocols without requiring `.codemachine` workspaces.

3. **Multi-engine orchestration**
   - Allow different steps (planning, coding, QA) to use different engines (Codex, Claude Code, Cursor, etc.) while still following our state machines and cost policies.

4. **Shared observability and governance**
   - Capture all engine calls (including CodeMachine-derived ones) in unified metrics, budgets, and dashboards.

---

## 5) Target Interop Architecture

### 5.1 Component View

- **Orchestrator API (existing)**
  - Owns `Project`, `ProtocolRun`, `StepRun`, `Event` and provides actions: `start`, `run-step`, `run-qa`, `approve`, etc.

- **CodeMachine Runtime Adapter (new worker layer)**
  - Reads `.codemachine/template.json` and `config/*.js`.
  - Translates agent graphs and modules into our internal workflow representation (`StepRun` sequence, dependencies, loop/trigger rules).
  - Orchestrates per-step execution via the engine layer and writes artifacts to both `.protocols/NNNN-*` and `.codemachine/outputs` (when present).

- **Engine Abstraction Layer (new)**
  - Defines a uniform interface for CLI-based engines (Codex, Claude Code, Cursor, CCR, OpenCode, Auggie).
  - Handles environment configuration, invocation, timeouts, retries, and error mapping.

- **Workspace & Artifact Manager (new utility)**
  - Manages coexistence of `.protocols/**` and `.codemachine/**`.
  - Applies `placeholders.js` rules to resolve prompt paths.
  - Enforces naming/layout conventions to avoid collisions.

- **Console & Metrics (existing, extended)**
  - Surfaces CodeMachine-derived runs (template name, agent graph).
  - Visualizes loops/triggers and engine usage per step.

### 5.2 Execution Flow (CodeMachine Template under Orchestrator)

1. **Template selection**
   - User registers a project and chooses a CodeMachine template (or default) via console/API.
2. **Config ingestion**
   - Adapter loads `config/main.agents.js`, `sub.agents.js`, `modules.js`, `placeholders.js` and `template.json`.
3. **ProtocolRun creation**
   - Orchestrator creates `ProtocolRun` with metadata: template id, CodeMachine version, engine defaults, workspace paths.
4. **Step graph materialization**
   - Adapter maps main agents to ordered `StepRun`s; associates modules (loop/trigger) to relevant points in the sequence.
5. **Execution**
   - For each `StepRun`, the engine layer calls the configured engine, passing prompts and context (spec, prior outputs, git state).
   - Outputs are written to `.protocols/NNNN-*` and `.codemachine/outputs` as appropriate.
6. **Loop/trigger behavior**
   - Module outputs (e.g., `check-task`, `iteration-checker`) determine whether to:
     - Mark step completed and proceed.
     - Step back N steps and re-run (loop).
     - Invoke another agent (trigger).
   - These decisions are persisted as `Event`s and reflected in `StepRun` transitions.
7. **Completion & QA**
   - Final CodeMachine steps (e.g., runtime prep, git commit) run under our workers.
   - Optional QA (`quality_orchestrator`) can run after key steps or at the end.

### 5.3 Data Model Alignment

- CodeMachine **Template** ↔ our **ProtocolRun template metadata**.
- CodeMachine **Main Agent** ↔ our **StepRun** (primary unit of work).
- CodeMachine **Sub-Agent** ↔ our **subtasks** or nested steps (not necessarily first-class DB entities initially).
- CodeMachine **Module (loop/trigger)** ↔ our **StepRun policy** + **transition rules**.
- CodeMachine **Specification document** ↔ our **protocol context** (stored in `.protocols` and associated to `ProtocolRun`).

---

## 6) Configuration Mapping Plan

- **Inputs to ingest**
  - `config/main.agents.js`, `config/sub.agents.js`, `config/modules.js`, `config/placeholders.js`.
  - `.codemachine/template.json` (selected template, engine defaults).

- **Mapping rules**
  - **Agent**
    - Fields: `id`, `name`, `description`, `promptPath`, optional `mirrorPath`.
    - Convert to `StepRun` blueprint with prompt path resolved via placeholders and root paths.
  - **Sub-agent**
    - Treat as a catalog of capabilities; allow main steps to reference them via prompt instructions or future nested-step support.
  - **Module**
    - `behavior.type = 'loop'` + `action = 'stepBack'` → StepRun backtracking with bounded retries (`maxIterations`) and optional `skip` list.
    - `behavior.type = 'trigger'` + `action = 'mainAgentCall'` → enqueue the target agent’s `StepRun` (using `triggerAgentId`).
  - **Placeholders**
    - Maintain a resolver that mirrors CodeMachine’s path placeholder behavior so our adapter finds the same prompt files.

- **Persistence**
  - Persist the parsed graph and module policies as template metadata linked to `Project` or `ProtocolRun`.
  - Record resolved prompt versions (paths + git commit) for each `ProtocolRun` for auditability and reproducibility.

---

## 7) Engine Abstraction & Policies

- **Engine interface**
  - Standard operations: `plan`, `execute`, `qa`, `meta` (capabilities).
  - Parameters: model id, reasoning effort, temperature, context files, working directory.
  - Behavior: CLI invocation with structured capture of stdout/stderr and exit codes.

- **Supported engines (initial target set)**
  - Codex CLI (existing).
  - +1 additional engine (e.g., Claude Code CLI or Cursor CLI) as the first “foreign” engine.

- **Policies**
  - Allowed models per project and per step type (planning vs execution vs QA).
  - Token/cost budgets enforced at `ProtocolRun` and `StepRun` levels.
  - Graceful fallback to Codex when an engine is unavailable or unhealthy, under configurable rules.

---

## 8) Phased Delivery Plan

- **Phase 0 – Readiness (1–2d)**
  - Verify DB migrations and Redis configuration.
  - Document expectations for `.codemachine` presence and version compatibility.
  - Select a PoC CodeMachine template and spec (e.g., small CRUD app).

- **Phase 1 – Config Ingestion (2–3d)**
  - Implement parser/validator for `config/*.js` → internal schema.
  - Produce a compatibility matrix (supported fields, fallbacks, unsupported patterns).
  - Add structured error reporting when configs are incomplete or unsupported.

- **Phase 2 – Runtime Adapter PoC (4–6d)**
  - Implement adapter that:
    - Builds `ProtocolRun` + ordered `StepRun`s from a template.
    - Executes via Codex only.
    - Writes artifacts to `.protocols/NNNN-*` + `.codemachine/outputs`.
    - Honors simple loop/trigger rules for a single module.
  - Demo end-to-end execution for the PoC template; capture events/metrics.

- **Phase 3 – Multi-Engine Support (3–5d)**
  - Introduce engine registry/interface.
  - Integrate one alternate engine (e.g., Claude Code CLI) end-to-end.
  - Add health checks, timeouts, and policy enforcement (allowlist/budgets).

- **Phase 4 – UX/API Enhancements (3–4d)**
  - Console: template import/selection UI, visualization of agent graph and loop/trigger decisions.
  - API: endpoints to list templates, start/resume CodeMachine-style runs, and inspect per-step engine usage.

- **Phase 5 – Release & CI (2–4d)**
  - Add GitHub Actions mirroring CodeMachine’s:
    - Build platform binaries (Linux/macOS/Windows) for our CLI tooling.
    - Publish npm package (if we expose a JS/TS wrapper or CLI).
    - Publish docs on main/tags (mike/MkDocs or Sphinx + Pages).
  - Introduce checksums/signing for binaries if required.

- **Phase 6 – Hardening & SRE (ongoing)**
  - Golden tests for loop/trigger semantics using representative templates.
  - Regression suite for `.codemachine` config parsing and engine selection.
  - Security review for engine tokens and workspace isolation.
  - Observability dashboards (engine usage, loop counts, error rates, cost).

---

## 9) Risks & Mitigations

- **Behavior drift (loop/trigger semantics)**
  - Mitigation: Use upstream templates as golden tests; keep a small mirror of CodeMachine’s expected workflows and validate transitions step-by-step.

- **Engine CLI instability**
  - Mitigation: Pin versions; implement pre-flight health checks; provide a clear fallback strategy to Codex; record engine failures as explicit `Event`s.

- **Workspace conflicts (`.protocols` vs `.codemachine`)**
  - Mitigation: Document path conventions; centralize workspace management; add cleanup hooks per `ProtocolRun` to avoid leftover temporary files.

- **Cost overruns**
  - Mitigation: Enforce budgets/allowlists at project and run level; expose cost metrics per engine/step; support soft/hard budget enforcement modes (`warn` vs `strict`).

- **Template drift across versions**
  - Mitigation: Store template id + version + git commit in `ProtocolRun`; allow pinning to a specific CodeMachine tag; add compatibility checks during run creation.

---

## 10) PoC Runbook (Thin Slice)

- **Template & spec**
  - Use CodeMachine’s default spec-to-code template.
  - Define a simple CRUD app spec using the published specification schema.

- **Steps**
  1. Parse `config/*.js` and `template.json`; store agent/module graph as template metadata.
  2. Create a `ProtocolRun` with mapped steps (main agents only); associate a single loop module (e.g., task verification).
  3. Execute via adapter using Codex as the sole engine; permit loop decisions for the verification module.
  4. Write artifacts to `.protocols/NNNN-*` and `.codemachine/outputs`.
  5. Capture `Event`s and metrics; verify that observed transitions match the intended CodeMachine behavior.
  6. Produce a short PoC report: success/failure, loop decisions, artifact paths, metrics snapshot.

---

## 11) Open Decisions

- **Second engine priority**
  - Choose between Claude Code CLI, Cursor CLI, or another engine as the first non-Codex integration.

- **Artifact layout when both `.protocols` and `.codemachine` exist**
  - Option A: Keep both as separate views; Option B: Use symlinks or shared directories for key artifacts (e.g., design docs, plans).

- **Release format**
  - Decide between npm-only distribution vs. npm + standalone binaries; define signing and provenance requirements, if any.

- **Template versioning strategy**
  - Decide how strictly we pin CodeMachine configs/templates (per project, per run, or globally) and how we roll out updates.

---

## 12) Comparative Architecture, Pipelines, and Workflows

### 12.1 Architecture (Runtime vs Orchestrator)

- **dev-pipeline / TasksGodzilla**
  - Python/FastAPI control plane (`tasksgodzilla/api/app.py`) with a persistent domain model (`Project`, `ProtocolRun`, `StepRun`, `Event`) stored in Postgres/SQLite via Alembic.
  - Redis/RQ-backed workers (`tasksgodzilla/worker_runtime.py`, `tasksgodzilla/workers/*`) handle planning, execution, QA, onboarding, and git/CI jobs; the orchestrator is a long‑running multi-project service.
  - Protocol artifacts live in git worktrees under `.protocols/NNNN-[task]/` (see `docs/architecture.md` and `docs/tasksgodzilla.md`), and Codex CLI is the only production engine today.

- **CodeMachine-CLI**
  - Bun/TypeScript CLI (`src/runtime/cli-setup.ts`) that runs either a TUI-first workflow (Ink + SolidJS under `src/cli/tui`) or explicit subcommands (`codemachine start`, `codemachine run`, `codemachine templates`, etc.).
  - Per-repo workspace rooted at `.codemachine/` holding inputs (`inputs/specifications.md`), selected workflow template (`template.json`), engine config, logs (`logs/workflow-debug.log`), and outputs.
  - Workflow logic lives in `src/workflows/**` and is driven by templates plus config files under `config/` (`main.agents.js`, `sub.agents.js`, `modules.js`, `placeholders.js`); there is no central DB, only filesystem state.

- **Interop implication**
  - dev-pipeline remains the central, multi-tenant control plane and source of truth for state and metrics.
  - CodeMachine is treated as a declarative workflow specification + engine registry that our runtime adapter can interpret; we do **not** attempt to replace its internal runtime, only to mirror its behavior through our `ProtocolRun`/`StepRun` model.

### 12.2 Pipelines, CI, and Distribution

- **dev-pipeline**
  - CI is dual-surface GitHub Actions (`.github/workflows/ci.yml`) + GitLab (`.gitlab-ci.yml`), both delegating to shell hooks in `scripts/ci/{bootstrap,lint,typecheck,test,build}.sh` (currently generic stubs).
  - There is **no** dedicated release pipeline today: the orchestrator is run via `make orchestrator-setup` / `scripts/api_server.py` / `docker-compose.yml`, and docs under `docs/` are not auto-published.

- **CodeMachine-CLI**
  - Uses GitHub Actions workflows:
    - `.github/workflows/build-binaries.yml` builds platform-specific binaries (Linux/macOS/Windows) using Bun and uploads them as artifacts.
    - `.github/workflows/publish.yml` installs dependencies and publishes npm packages for the core CLI and per-platform binaries, driven by tags and `NPM_TOKEN`.
    - `.github/workflows/publish_docs.yml` uses `uv` + `mike` + MkDocs (`mkdocs.yml`) to version and deploy docs to `gh-pages`, including CNAME management for `docs.codemachine.co`.
  - Test and quality pipelines are wired through Bun scripts in `package.json` (`lint`, `test`, `typecheck`, `validate`).

- **Gap summary**
  - Our CI story is focused on **project-level checks** (lint/type/test/build for arbitrary stacks) rather than **productizing the orchestrator itself**.
  - To match CodeMachine’s distribution posture, we still need:
    - Release workflows for publishing binaries/containers and/or Python/JS packages for the orchestrator CLI and library.
    - A docs publishing pipeline that tracks orchestrator versions (e.g., MkDocs/mike or Sphinx + Pages), aligned with tags.
  - These items align with §8 “Phase 5 – Release & CI” and should be treated as required for “productized tooling” in §2.

### 12.3 Workflow Semantics, Agents, and State

- **dev-pipeline**
  - Primary workflow is the protocol pipeline (`scripts/protocol_pipeline.py`) + QA orchestrator (`scripts/quality_orchestrator.py`), using a fixed prompt library under `prompts/` and a JSON schema under `schemas/`.
  - Looping/branching today is mostly **procedural**: StepRun states (`pending → running → needs_qa → completed/failed/...`) plus external actions (reruns, QA failures) drive retries, but there is no first-class notion of “loop module” or “trigger module” in the data model.
  - State and “memory” live in `.protocols/NNNN-[task]/` (`plan.md`, `context.md`, `log.md`, step files, QA reports) and in DB Events/StepRuns; there is no separate per-agent memory abstraction.

- **CodeMachine-CLI**
  - Main agents, sub-agents, and modules are declared in `config/*.js` and wired into workflow templates under `templates/` and `src/workflows/templates/**`.
  - Modules express **loop** and **trigger** semantics (e.g., “stepBack N steps”, “call another main agent”) that the runtime enforces via `src/workflows/execution/workflow.ts` and behavior helpers.
  - Context/memory is explicitly modeled:
    - File-based memory (JSON and markdown pipelines) under `.codemachine/` for historical context, progressive documentation, and auditing (see `docs/architecture.md`).
    - Session-level “orchestrator memory” inside the main agent, used to coordinate sub-agents and merge their results.

- **Interop implication and gaps**
  - §5 and §6 define the mapping from templates/agents/modules into `ProtocolRun`/`StepRun` plus policies, but we still need:
    - A concrete representation for **loop/trigger policies** in the DB (e.g., per-StepRun policy blobs that mirror module behavior).
    - An explicit strategy for mapping CodeMachine’s file-based memory artifacts into our `.protocols` + Events model (what we persist, where we store it, and how we expose it in the console).
  - These gaps should be closed as part of §8 “Phase 2 – Runtime Adapter PoC” and surfaced as requirements in any implementation tickets.

### 12.4 Engine Integration

- **dev-pipeline**
  - Currently hard-wired to Codex CLI with model/budget configuration via env vars (`PROTOCOL_*_MODEL`, `TASKSGODZILLA_MAX_TOKENS_*`) and policies described in `docs/solution-design.md`.
  - §7 sketches an engine interface and registry, but there is no concrete `Engine` abstraction or provider catalogue implemented in `tasksgodzilla/` yet.

- **CodeMachine-CLI**
  - Implements a full engine registry under `src/infra/engines/**` with provider-specific modules for Codex, Claude, CCR, Cursor, OpenCode, and Auggie (auth, config sync, command construction, telemetry parsing).
  - Engine selection is template/config-driven: each agent can pick a model/engine; the runtime aggregates “workflow agents” and calls `engine.syncConfig` before execution.

- **Interop implication and gaps**
  - To achieve parity with CodeMachine’s engine behavior, dev-pipeline needs:
    - A concrete `Engine` abstraction and registry, with at least Codex + one additional CLI engine wired end-to-end.
    - Engine-aware StepRun policies (which engine/model is allowed per step) and observability (per-engine usage/cost metrics).
  - This work corresponds to §8 “Phase 3 – Multi-Engine Support” and should be considered non-optional for serious CodeMachine interoperability.

### 12.5 Developer Experience and Control Surfaces

- **dev-pipeline**
  - Orchestrator-first UX: REST API + thin web console (`/console`) backed by FastAPI, plus Python CLIs in `scripts/` for project bootstrap, protocol creation, QA, workers, and CI discovery.
  - Designed for multi-repo, multi-tenant orchestration, with a focus on visibility into many ProtocolRuns/StepRuns at once.

- **CodeMachine-CLI**
  - CLI/TUI-first UX: `codemachine` launches an interactive application that owns the terminal, with embedded dashboards for agents, steps, logs, and engine status.
  - Single-workspace orientation: workflows operate within the current repo’s `.codemachine` directory.

- **Interop implication**
  - Interop favors keeping **dev-pipeline as the global view** while treating CodeMachine’s TUI as an optional, local control surface.
  - For most users, the orchestrator console should expose CodeMachine-derived runs (template name, agent graph, loops/triggers, engine usage) without requiring them to run the CodeMachine TUI directly.

---

## 13) Gap Checklist (Doc + Implementation)

The sections above surface several concrete gaps between dev-pipeline and CodeMachine-CLI. For tracking purposes:

- **Interop-critical implementation gaps**
  - Implement `config/*.js` + `.codemachine/template.json` ingestion and validation inside `tasksgodzilla` (or a dedicated adapter module), producing a stored template graph compatible with `ProtocolRun`/`StepRun`.
  - Materialize loop/trigger behavior as first-class StepRun policies, including persistence and console visualization.
  - Define and implement how CodeMachine’s file-based memory and outputs map into `.protocols/` + Events (what we mirror, what we derive, and what remains `.codemachine`-only).

- **Pipelines and distribution gaps**
  - Add release workflows and packaging for the orchestrator tooling (binaries/containers and/or Python/JS packages), following the pattern of CodeMachine’s `build-binaries.yml` and `publish.yml`.
  - Introduce a docs publishing pipeline and versioned documentation for dev-pipeline, mirroring CodeMachine’s `publish_docs.yml` approach.

- **Documentation gaps**
  - Cross-link this document with `docs/architecture.md`, `docs/solution-design.md`, and CodeMachine’s `docs/architecture.md` to make the architecture and workflow differences discoverable.
  - When the adapter and engine registry land, expand this file with concrete API/CLI examples (e.g., “run CodeMachine template X via `/projects/{id}/protocols`”) and an updated compatibility matrix.

---

## 14) Implementation Blueprint: Loop/Trigger Policies & Engine Registry

This section captures concrete implementation steps for closing two of the key gaps identified above:
- Persisted loop/trigger policies per step, compatible with CodeMachine `modules.js`.
- A multi-engine registry (Codex + ≥1 other CLI engine) wired into `StepRun` and workers.

### 14.1 StepRun and Database Schema Changes

**Domain model (`tasksgodzilla/domain.py`)**

- Extend `StepRun` with engine and policy fields (keeping existing fields intact):
  - `engine_id: Optional[str]` — logical engine key (`"codex"`, `"claude_code"`, `"cursor"`, etc.).
  - `policy: Optional[dict]` — static, template-derived loop/trigger policy for this step.
  - `runtime_state: Optional[dict]` — mutable state for this step (loop counters, last decision, etc.).

**SQLite schema (`SCHEMA_SQLITE` in `tasksgodzilla/storage.py`)**

- Update the `step_runs` table definition to include:
  - `engine_id TEXT`
  - `policy TEXT` (JSON-encoded)
  - `runtime_state TEXT` (JSON-encoded)

Resulting shape (abridged):

```sql
CREATE TABLE IF NOT EXISTS step_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protocol_run_id INTEGER NOT NULL REFERENCES protocol_runs(id),
    step_index INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    step_type TEXT NOT NULL,
    status TEXT NOT NULL,
    retries INTEGER DEFAULT 0,
    model TEXT,
    engine_id TEXT,
    policy TEXT,
    runtime_state TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Postgres schema (`SCHEMA_POSTGRES` in `tasksgodzilla/storage.py`)**

- Update the `step_runs` table definition to include:
  - `engine_id TEXT`
  - `policy JSONB`
  - `runtime_state JSONB`

**Storage interface (`BaseDatabase` in `tasksgodzilla/storage.py`)**

- Widen method signatures to carry engine and policy:
  - `create_step_run(..., model: Optional[str] = None, engine_id: Optional[str] = None, retries: int = 0, summary: Optional[str] = None, policy: Optional[dict] = None) -> StepRun`
  - `update_step_status(..., summary: Optional[str] = None, model: Optional[str] = None, engine_id: Optional[str] = None, runtime_state: Optional[dict] = None, expected_status: Optional[str] = None) -> StepRun`

**SQLite and Postgres implementations**

- `Database.create_step_run`:
  - Accept `engine_id` and `policy`.
  - Serialize `policy` to JSON for SQLite (`policy_json = json.dumps(policy) if policy is not None else None`).
  - Insert into the new columns.
- `Database.update_step_status`:
  - Accept `engine_id` and `runtime_state`.
  - Serialize `runtime_state` for SQLite.
- `_row_to_step`:
  - Parse `policy` and `runtime_state` with the existing JSON helper (`_parse_json`) and pass them into `StepRun`.
- Mirror the same logic in `PostgresDatabase` (JSONB columns can store dicts directly or via `json.dumps`).

**Loop/trigger policy shape (for CodeMachine interop)**

- Standardize `StepRun.policy` to a CodeMachine-compatible, but engine-agnostic, structure, for example:

```json
{
  "module_id": "iteration-checker",
  "behavior": "loop",
  "max_iterations": 3,
  "step_back": 2,
  "skip_steps": [0],
  "trigger_agent_id": null
}
```

- Loop module: `behavior = "loop"`, with `max_iterations`, `step_back`, `skip_steps`.
- Trigger module: `behavior = "trigger"`, with `trigger_agent_id` and optional `conditions`.
- The CodeMachine adapter that ingests `config/modules.js` should normalize each module into this shape and attach it to the corresponding `StepRun.policy`.
- Execution workers update `StepRun.runtime_state` after each decision (e.g., `{"loop_count": 1, "last_action": "step_back", "last_target_step_index": 5}`) and emit `Event`s like `loop_decision` / `trigger_decision` including policy + runtime_state in `metadata`.

### 14.2 Engine Registry and Providers

**Engine interfaces (`tasksgodzilla/engines.py` or `tasksgodzilla/engines/__init__.py`)**

- Define a small engine abstraction:
  - `EngineMetadata` — id, display name, kind (`"cli"`/`"api"`), default model.
  - `EngineRequest` — project/protocol/step IDs, model, prompt files, working dir, and optional extras.
  - `EngineResult` — success flag, stdout/stderr, optional token/cost metadata.
  - `Engine` protocol — methods `plan`, `execute`, `qa`, and optional `sync_config(additional_agents=...)`.

**Registry**

- Implement an `EngineRegistry` with:
  - `register(engine: Engine, default: bool = False) -> None`
  - `get(engine_id: str) -> Engine`
  - `get_default() -> Engine`
  - `list_all() -> List[Engine]`
- Expose a process-global instance:
  - `registry = EngineRegistry()`

**Codex provider (`tasksgodzilla/engines/codex_engine.py`)**

- Implement `CodexEngine` wrapping existing Codex helpers (used by `protocol_pipeline`/`quality_orchestrator`):
  - `metadata.id = "codex"`
  - Implement `plan/execute/qa` by delegating to Codex CLI with the appropriate prompts and models.
  - Implement `sync_config` as a lightweight sanity check (or no-op).
- Register it at import time (e.g. in `tasksgodzilla/engines/__init__.py`):
  - `registry.register(CodexEngine(), default=True)`

**Second engine provider (e.g., Claude Code or Cursor)**

- Add a second engine class (e.g., `ClaudeCodeEngine`) that:
  - Wraps the corresponding CLI binary (`claude ...` / `cursor ...`).
  - Reads tokens/config from env.
  - Implements `plan/execute/qa` to produce an `EngineResult`.
- Register it in the same registry:
  - `registry.register(ClaudeCodeEngine())`

**StepRun wiring**

- When creating `StepRun` from a CodeMachine template:
  - Set `engine_id` from the template if specified; otherwise use `registry.get_default().metadata.id`.
  - Record the chosen `model` alongside `engine_id`.
- During execution (e.g. in `tasksgodzilla/workers/codex_worker.py` or a future generic engine worker):
  - Resolve an engine via:
    - `engine = registry.get(step.engine_id or registry.get_default().metadata.id)`
  - Build an `EngineRequest` (project/protocol/step IDs, model, prompt paths, working directory).
  - Call `engine.execute(req)` (or `plan`/`qa` depending on step type).
  - Update `StepRun` with:
    - `status`, `summary`, `model`/`engine_id` if they changed (e.g., due to fallback).
    - Updated `runtime_state` if a loop/trigger decision was taken.
  - Append `Event`s capturing engine choice, results, and any loop/trigger transitions.

These implementation notes are intended as the concrete blueprint for wiring CodeMachine-style loop/trigger semantics and multi-engine support into `tasksgodzilla`. Once implemented, this document should be updated with links to the final modules and any deviations from the plan.

---

## 15) Current implementation slice (dev-pipeline)

- **Workspace import**: `/projects/{id}/codemachine/import` (inline or queued) ingests `.codemachine` configs, persists the template graph on the `ProtocolRun` (`template_config` + `template_source`), and materializes `StepRun`s from main agents. Worker: `tasksgodzilla/workers/codemachine_worker.py`.
- **Engine + policy per step**: `StepRun` now stores `engine_id`, `policy` (list/dict), and `runtime_state`; schema added via Alembic `0002/0003`.
- **Strict module attachment**: Modules attach only when explicitly referenced (agent `moduleId/module/module_id`, module `targetAgentId`, or trigger `trigger_agent_id`). All matching modules attach; no default loop fallback.
- **Console hints**: Protocol detail shows template name/version; steps table shows engine and attached policies.
- **Runtime adapter**: Workers detect CodeMachine runs, resolve agent prompts with placeholders, execute via the engine registry, and write artifacts to both `.protocols/<run>/` and `.codemachine/outputs/`. Codex QA is skipped for CodeMachine runs (triggers still fire).
- **Condition-aware policies**: loop/trigger policies honor `condition/conditions` when the reason matches; skipped evaluations emit `loop_condition_skipped`/`trigger_condition_skipped` events for observability.
- **Inline triggers with fakeredis**: When Redis is configured with `fakeredis://`, trigger policies execute inline to mirror the dev/test expectation.

---

## 16) Compatibility matrix (snapshot)

- **Agents**: id/name/description/promptPath/mirrorPath/engineId/model supported.
- **Modules (loop/trigger)**: behavior.type/action/stepBack/maxIterations/skip + triggerAgentId/targetAgentId parsed; condition/conditions fields gate execution (reason-matched) with `loop_condition_skipped` / `trigger_condition_skipped` events.
- **Attachment rules**: modules attach only when referenced via agent moduleId list or module targetAgentId/triggerAgentId. No implicit defaults.
- **Runtime**: loop policies drive stepBack/backfill with runtime_state counters; trigger policies enqueue/inline target steps with depth guards. Conditions gate applicability based on reason; skipped policies emit observable events.
- **Docs/tests**: golden parsing tests live under `tests/test_codemachine_golden.py`; runtime semantics under `tests/test_codemachine_policy_runtime.py`.
