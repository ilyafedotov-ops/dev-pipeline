# Architecture and Workflow Overview

This repository is a starter kit for DeksdenFlow_Ilyas_Edition_1.0: a protocol-driven way to ship work in parallel streams. The codebase is mostly orchestration around the Codex CLI, Git worktrees, and shared CI stubs for GitHub and GitLab.

For deeper design and delivery detail, see:
- `docs/solution-design.md` — current-state review and target orchestrator architecture.
- `docs/implementation-plan.md` — phased plan from refactors to console/CI integration.
- `Makefile` — convenience targets: `orchestrator-setup` (venv + deps + migrations) using Alembic and the Postgres/SQLite adapters.

## Repository layout (current state)
- `README.md`: quickstart and high-level Mermaid diagrams.
- `docs/`: deep dive on DeksdenFlow (`deksdenflow.md`), CI notes (`ci.md`), TerraformManager demo workflow plan, and this architecture doc.
- `prompts/`: operational prompt library (new/resume/review protocols, project/init/bootstrap, CI discovery, QA, Java testing).
- `scripts/`: orchestration utilities (protocol pipeline, project setup, CI discovery, QA orchestrator, dataset report generator) plus `scripts/ci/*` stubs.
- `.github/workflows/ci.yml` and `.gitlab-ci.yml`: dual CI entrypoints that call the same `scripts/ci/*.sh` hooks.
- `schemas/`: JSON schema for planning agent output.
- `tests/`: harnesses covering orchestration code paths; optional Codex integration test gated by `RUN_REAL_CODEX`.
- `deksdenflow/`: reusable library for protocol pipeline, QA, project setup, and the new orchestrator (API + storage + domain).

## Core building blocks
- **Protocol assets and schema**  
  - Protocols live under `.protocols/NNNN-[task]/` inside each worktree; numbered via `next_protocol_number()` scanning existing `.protocols/` and `../worktrees/`.  
  - `schemas/protocol-planning.schema.json` enforces the planning agent’s JSON (plan/context/log + step files).
- **Protocol pipeline (`scripts/protocol_pipeline.py`)**  
  - Interactive CLI that: detects repo root, prompts for base branch/short name/description; creates a Git worktree/branch `NNNN-[task]` from `origin/<base>`; and builds protocol artifacts.  
  - Uses Codex CLI twice: (1) planning (`run_codex_exec` with `planning_prompt`, validated against the JSON schema) to produce `plan.md`, `context.md`, `log.md`, `00-setup.md`, and step files; (2) step decomposition (`decompose_step_prompt`) for each non-setup step.  
  - Optional flags: `--pr-platform github|gitlab` to auto-commit/push and open Draft PR/MR (requires `gh`/`glab`); `--run-step` to auto-execute a step via Codex using `execute_step_prompt`.  
  - Model defaults come from env (`PROTOCOL_PLANNING_MODEL`, `PROTOCOL_DECOMPOSE_MODEL`, `PROTOCOL_EXEC_MODEL`) with fallbacks (`gpt-5.1-high`, etc.). Temporary artifacts live in `.protocols/<name>/.tmp/`.
- **QA orchestrator (`scripts/quality_orchestrator.py`)**  
  - Builds a QA prompt from `plan.md`, `context.md`, `log.md`, the current step file, git status, and last commit, then calls Codex with `prompts/quality-validator.prompt.md`.  
  - Writes `quality-report.md`; exits non-zero on Codex failure or `VERDICT: FAIL` to gate CI/pipelines.
- **Project setup (`scripts/project_setup.py`)**  
  - Ensures a repo exists (optionally `git init -b <base>`), warns if `origin` or base branch is missing, and materializes starter assets from `BASE_FILES`. Copies from this starter repo when available; otherwise writes placeholders.  
  - Marks CI scripts executable and can optionally run Codex discovery via `--run-discovery`/`PROTOCOL_DISCOVERY_MODEL`.
- **Codex CI bootstrap (`scripts/codex_ci_bootstrap.py`)**  
  - Thin wrapper around Codex CLI using `prompts/repo-discovery.prompt.md` to auto-fill `scripts/ci/*` for the detected stack (default model `gpt-5.1-codex-max`).
- **CI surfaces**  
  - GitHub Actions job `checks` and GitLab stages `bootstrap → lint → typecheck → test → build` each call the matching `scripts/ci/*.sh` if executable; otherwise emit “skip” messages. The scripts are placeholders today and must be filled per stack.
- **Prompts library**  
  - `protocol-new` defines the contract for opening a protocol (worktree creation, planning, first commit/PR, step structure, commit messaging).  
  - `protocol-resume` and `protocol-review-merge*` handle continuation and QA/merge flows with context reconciliation.  
  - `project-init` guides scaffolding a repo; `protocol-pipeline` guides running `protocol_pipeline.py`; `java-testing` and `quality-validator` provide specialized guidance.
- **Dataset helper (`scripts/generate_dataset_report.py`)**  
  - Small utility that reads `dataset.csv` (category/value), aggregates metrics, and renders a PDF via reportlab. Current inputs are toy data; output path defaults to `docs/dataset_report.pdf`.
- **TerraformManager workflow plan (`docs/terraformmanager-workflow-plan.md`)**  
  - Checklists for cloning/running the TerraformManager demo under `Projects/`, covering API/CLI/UI validation and optional infra tooling; serves as an example end-to-end ops workflow.
- **Orchestrator (alpha)**  
  - `deksdenflow/storage.py` provides SQLite persistence for Projects/ProtocolRuns/StepRuns/Events; `deksdenflow/api/app.py` exposes FastAPI endpoints for CRUD + actions; `scripts/api_server.py` runs uvicorn. Queueing is a stub (`deksdenflow/jobs.py`) to be replaced with a real backend.

## Operational workflows
1. **Bootstrap a repo**  
   - Run `python3 scripts/project_setup.py --base-branch <branch> [--init-if-needed] [--run-discovery]` or follow `prompts/project-init.prompt.md`. Creates docs/prompts/CI/scripts/schema, ensures git state, and optionally runs Codex discovery to prefill CI hooks.
2. **Open a new protocol stream**  
   - From repo root, run `python3 scripts/protocol_pipeline.py ...`. It creates `../worktrees/NNNN-[task]/`, generates `.protocols/NNNN-[task]/` with plan + step files, optionally commits/pushes + Draft PR/MR, and can auto-run a step. Work happens in the new worktree; plan/step files are the execution contract.
3. **Execute steps manually (outside auto-run)**  
   - Work from the protocol’s worktree. For each step: follow the step file, run stack checks (`lint/typecheck/test/build`), update `log.md` and `context.md`, commit with `type(scope): subject [protocol-NNNN/XX]`, push, and report per the contract in `prompts/protocol-new.prompt.md`.
4. **QA gate a step**  
   - Run `python3 scripts/quality_orchestrator.py --protocol-root <.protocols/...> --step-file XX-*.md [--model ...] [--sandbox ...]`. On FAIL, fix issues before continuing; reports land in `quality-report.md`.
5. **CI pipelines**  
   - Both GitHub Actions and GitLab CI invoke the same `scripts/ci/*.sh` hooks. Real work requires filling those scripts; missing scripts simply print skip messages to keep empty repos green.
6. **Optional: CI discovery**  
   - Use `python3 scripts/codex_ci_bootstrap.py` to run the discovery prompt that suggests/fills CI commands based on the detected stack.
7. **Sample data/report workflow**  
   - `scripts/generate_dataset_report.py --csv dataset.csv --out docs/dataset_report.pdf` converts the sample CSV into a PDF report; demonstrates the pattern for simple analytic tooling.
8. **TerraformManager demo**  
   - `docs/terraformmanager-workflow-plan.md` documents a full validation flow for the TerraformManager app (clone, configure env vars, run services, exercise CLI/API/UI, optional container smoke tests).

## State, conventions, and dependencies
- **Worktrees/branches:** Each protocol lives in its own Git worktree under `../worktrees/NNNN-[task]/` with a same-named branch from `origin/<base>`. `.protocols/` sits inside the worktree; numbering scans both `.protocols/` and `../worktrees/`.
- **Commit format:** `feat(protocol): add plan for ... [protocol-NNNN/00]` for initial plan; subsequent commits use `type(scope): subject [protocol-NNNN/XX]` as defined in `protocol-new.prompt.md`.
- **Models/env vars:** Planning/decompose/exec/QA models configurable via `PROTOCOL_PLANNING_MODEL`, `PROTOCOL_DECOMPOSE_MODEL`, `PROTOCOL_EXEC_MODEL`, `PROTOCOL_QA_MODEL`, `PROTOCOL_DISCOVERY_MODEL`; defaults favor `gpt-5.1-high`/`codex-5.1-max` families.
- **External tooling:** Codex CLI (mandatory for orchestrators), optional `gh`/`glab` for PR/MR automation. The dataset helper requires `reportlab`.
- **Git hygiene:** Scripts avoid destructive commands; `project_setup` warns if `origin` missing or base branch absent. `.gitignore` excludes local assets (`Projects/`, dataset files, generated reports).

## Quality and tests
- Unit tests cover orchestration helpers (`run_codex_exec`, QA prompt assembly, project setup discovery wiring).  
- Integration test `tests/test_readme_workflow_integration.py` can exercise the full protocol pipeline against real Codex when `RUN_REAL_CODEX=1`.  
- No stack-specific lint/type/test wired yet—`scripts/ci/*` are placeholders to be customized per project.
