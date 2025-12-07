![TasksGodzilla banner](docs/Images/BigBanner.png)

# TasksGodzilla_Ilyas_Edition_1.0 Project Starter

This repo is a lightweight starter kit for agent-driven development using the TasksGodzilla_Ilyas_Edition_1.0 protocols. It includes:

- Generic folder layout and documentation to keep parallel workstreams organized.
- Ready-to-use prompts (new/resume/review) adapted from the published gists.
- Dual CI templates for GitHub Actions and GitLab CI that call the same `scripts/ci/*` hooks.
- An interactive protocol pipeline script that talks to Codex CLI to generate plans, decompose steps, and optionally open PRs/MRs or auto-run a specific step.
- A FastAPI-based orchestrator with Redis/RQ queue, SQLite/Postgres storage, and a minimal web console at `/console` for projects/protocols/steps/events.

## Quick start

1. Prep a repo (existing or new):

   ```bash
   python3 scripts/project_setup.py --base-branch main --init-if-needed
   # Optional: --clone-url <git-url> --run-discovery
   ```

   This adds docs/prompts/CI/schema/pipeline scripts and can auto-fill CI commands via Codex discovery.
2. Fill CI commands in `scripts/ci/*.sh` for your stack (Node, Python, Java, Go, etc.). Workflows already call these scripts.
3. Generate a protocol for your next task:

   ```bash
   python3 scripts/protocol_pipeline.py --base-branch main --short-name "<task>" --description "<desc>"
   # Optional: --pr-platform github|gitlab, --run-step 01-some-step.md
   ```

   This creates a worktree/branch `NNNN-<task>`, `.protocols/NNNN-<task>/plan.md` + step files, and can open a Draft PR/MR.
4. Execute steps with Codex:

   ```bash
   codex --model codex-5.1-max-xhigh --cd ../worktrees/NNNN-<task> \
     --sandbox workspace-write --ask-for-approval on-request \
     "Follow .protocols/NNNN-<task>/plan.md and the current step file to implement the next step."
   ```

5. Validate a step (optional QA gate):

   ```bash
   python3 scripts/quality_orchestrator.py \
     --protocol-root ../worktrees/NNNN-<task>/.protocols/NNNN-<task> \
     --step-file 01-some-step.md \
     --model codex-5.1-max
   ```

Logging tip: set `TASKSGODZILLA_LOG_JSON=true` to emit structured JSON logs from CLIs/workers/API.
Redis is required for orchestration; set `TASKSGODZILLA_REDIS_URL` (use `fakeredis://` for local testing).

### Protocol pipeline expectations (real work)
- The protocol pipeline scaffolds `.protocols/NNNN-task/`, but the steps are for **real code changes** (features, fixes, tests). Plan files are the contract; the work happens in the codebase.
- Prefer running `scripts/protocol_pipeline.py --pr-platform github` to auto-commit/push the plan and open a PR (uses gh/glab when present, falls back to GitHub REST with `GITHUB_TOKEN`/`GH_TOKEN`).
- From the web/API side, `POST /protocols/{id}/actions/open_pr` enqueues `open_pr_job` to push the branch and open a PR using the same fallbacks.
- Execute step files in order; update `log.md`/`context.md` as state, but commits should primarily contain code/test changes tied to the protocol.

## Orchestrator status & QA options

- Protocol statuses: `pending` → `planning` → `planned` → `running` → (`paused` | `blocked` | `failed` | `cancelled` | `completed`). CI failures or worker errors block the run; PR/MR merge completes it.
- Step statuses: `pending` → `running` → `needs_qa` → (`completed` | `failed` | `cancelled` | `blocked`). Execution stops at `needs_qa`; QA or manual approval marks `completed`. CI/webhook failures can mark a step `blocked`.
- Auto QA knobs: set `TASKSGODZILLA_AUTO_QA_AFTER_EXEC=true` to enqueue QA immediately after execution. Set `TASKSGODZILLA_AUTO_QA_ON_CI=true` to enqueue QA when CI reports success via webhook.
- CI callbacks: export `TASKSGODZILLA_API_BASE` in CI and call `scripts/ci/report.sh success|failure` to mirror pipeline status into the orchestrator (supports GitHub/GitLab payloads; optional `TASKSGODZILLA_API_TOKEN`/`TASKSGODZILLA_WEBHOOK_TOKEN`). Set `TASKSGODZILLA_PROTOCOL_RUN_ID` if branch detection is ambiguous so the webhook can map directly to a run.
- Observability: `/metrics` exposes Prometheus data; `/queues` and `/queues/jobs` list queue stats and payloads. Events can be tailed via the console’s activity feed.

## CodeMachine integration

- Import `.codemachine` workspaces with `POST /projects/{id}/codemachine/import` to persist the template graph and emit `ProtocolSpec`/`StepSpec` entries (engines, policies, QA) for the run.
- CodeMachine steps now use the unified engine runner and spec-driven prompt/output resolver; outputs are written to `.protocols/<protocol>/` and to `aux.codemachine` targets, and QA follows the spec `qa_policy` (skip/light/full) rather than being implicitly skipped.
- Module policies (loop/trigger) attach to matching agents and drive retries or inline triggers. Loop limits and trigger depth are recorded in `runtime_state` and surfaced as events.
- When `TASKSGODZILLA_REDIS_URL=fakeredis://`, the API spins up a background RQ worker thread to process jobs inline for local dev.

## Git onboarding & branch controls

- Projects accept an optional `local_path` and persist it. Onboarding uses that path when it already exists; otherwise it clones into `TASKSGODZILLA_PROJECTS_ROOT` (default `projects/<project_id>/<repo_name>`) and records the resolved path so every project has an isolated workspace. Opt out of cloning with `TASKSGODZILLA_AUTO_CLONE=false`.
- After resolving the workspace, onboarding auto-runs Codex repository discovery (`prompts/repo-discovery.prompt.md`, model from `PROTOCOL_DISCOVERY_MODEL` or default `gpt-5.1-codex-max`) and logs events for visibility across console/TUI/CLI.
- Onboarding auto-configures `origin` (rewrites to GitHub SSH when `TASKSGODZILLA_GH_SSH=true`) and can set git identity from `TASKSGODZILLA_GIT_USER` / `TASKSGODZILLA_GIT_EMAIL`.
- Clarifications are emitted as a `setup_clarifications` event with recommended CI/models/branch policies; set `TASKSGODZILLA_REQUIRE_ONBOARDING_CLARIFICATIONS=true` to block until acknowledged in the console/TUI.
- Remote branch management API: `GET /projects/{id}/branches` lists origin branches and `POST /projects/{id}/branches/{branch}/delete` with `{"confirm": true}` deletes a remote branch and records an event.

Workspace layout (default):
```text
projects/
  <project_id>/
    <repo_name>/            # primary working copy (honors local_path when provided)
      .protocols/<protocol>/...
    worktrees/
      <protocol_name>/      # branch+worktree created during plan/exec
        .protocols/<protocol_name>/...
```

## Containerized orchestrator (API + worker + Redis/Postgres)

For a quick local stack with API, RQ worker, Redis, and Postgres:

```bash
docker compose up --build
# API at http://localhost:8011 (token from TASKSGODZILLA_API_TOKEN env or compose default)
```

Environment defaults live in `docker-compose.yml`; override with env vars as needed.
Compose services and ports:
- API: `8011 -> 8010` (default token `changeme` if not overridden)
- Postgres: `5433 -> 5432` (db/user/pass `tasksgodzilla`)
- Redis: `6380 -> 6379`
Useful commands:
- Start/refresh: `docker compose up --build -d`
- Logs: `docker compose logs -f api worker codex-worker`
- Stop/clean: `docker compose down -v`

Local (SQLite + fakeredis) without Docker:

```bash
make orchestrator-setup
TASKSGODZILLA_REDIS_URL=fakeredis:// .venv/bin/python scripts/api_server.py
# open http://localhost:8010/console (use 8011 if running via docker compose) and set API token if configured
```

Local (containers for Redis + Postgres, app on host):
```bash
make compose-deps  # starts Redis on 6380 and Postgres on 5433
TASKSGODZILLA_DB_URL=postgresql://tasksgodzilla:tasksgodzilla@localhost:5433/tasksgodzilla \
TASKSGODZILLA_REDIS_URL=redis://localhost:6380/0 \
.venv/bin/python scripts/api_server.py --host 0.0.0.0 --port 8010
```

CLI (interactive):
```bash
python -m tasksgodzilla.cli.main          # interactive menu
./scripts/tasksgodzilla_cli.py projects list --json
```
See docs/cli.md for details.

Textual TUI (dashboard):
```bash
python -m tasksgodzilla.cli.tui           # panel-based dashboard with keybindings
./scripts/tasksgodzilla_tui.py
./scripts/tui                           # simple launcher (prefers .venv)
```

## Folder map

- `scripts/spec_audit.py` — audit/backfill ProtocolSpec for existing runs (`--project-id/--protocol-id/--backfill`).


- `docs/` — overview of TasksGodzilla_Ilyas_Edition_1.0 and CI notes. New: `docs/solution-design.md` (target architecture + risks) and `docs/implementation-plan.md` (phased plan).
- `prompts/` — ready prompts: project bootstrap, new/resume protocols, review/merge flows.
- `.github/workflows/ci.yml` — GitHub Actions using the shared CI scripts.
- `.gitlab-ci.yml` — GitLab CI mirror of the same jobs.
- `scripts/ci/` — editable hooks (`bootstrap.sh`, `lint.sh`, `typecheck.sh`, `test.sh`, `build.sh`).
- `scripts/protocol_pipeline.py` — interactive orchestrator for TasksGodzilla_Ilyas_Edition_1.0 protocols using Codex CLI.
- `schemas/protocol-planning.schema.json` — JSON Schema for the planning agent’s output.
- `scripts/project_setup.py` — prepares a repo with starter docs/prompts/CI/schema/pipeline if they’re missing.
- `prompts/repo-discovery.prompt.md` — Codex prompt to auto-discover stack and fill CI scripts.
- `scripts/spec_audit.py` — audit/backfill ProtocolSpec for existing runs (`--project-id/--protocol-id/--backfill`).
- `scripts/codex_ci_bootstrap.py` — helper to run Codex (codex-5.1-max by default) with the discovery prompt to fill CI scripts.
- `scripts/quality_orchestrator.py` — Codex QA validator that checks a protocol step and writes a report.
- `Makefile` — helper targets: `deps` (install orchestrator deps in `.venv`), `migrate` (alembic upgrade), `orchestrator-setup` (deps + migrate).
- `tasksgodzilla/api/frontend/` — lightweight web console assets served from `/console`.
- `tasksgodzilla/codemachine/` — loaders/runtime adapters for `.codemachine` workspaces plus loop/trigger policy helpers.
- `tasksgodzilla/workers/` — job handlers for Codex execution, CodeMachine import, onboarding, and state helpers.
- `alembic/` — migrations for Postgres/SQLite schema (projects, protocol_runs, step_runs, events).

## How to use the prompts

- Start a project: feed `prompts/project-init.prompt.md` to your agent. It sets expectations for creating the structure, wiring CI for GitHub/GitLab, and preparing protocol artifacts.
- Run day-to-day work: use `prompts/protocol-new.prompt.md` to open a fresh protocol, `prompts/protocol-resume.prompt.md` to resume, and `prompts/protocol-review-merge*.prompt.md` to drive review/merge.

## TasksGodzilla_Ilyas_Edition_1.0 at a glance

1. Git workflow
2. Context collection
3. Protocol discussion
4. Protocol plan lock-in
5. Protocol execution
6. Review and merge
7. Organizational wrap-up

The core idea: ship improvements in parallel streams with strict, explicit protocols. Use the prompts and CI hooks here as the default spine; swap in your stack-specific commands without changing the flow.

## Architecture (Mermaid)

```mermaid
graph TD
  U["User (console/API client)"] --> Console["Console (web/TUI)"]
  Console --> API["Orchestrator API (FastAPI)"]
  API --> Repo["Repo resolver\n(local_path or projects/<project_id>/<repo>)"]
  API --> DB[(DB: Postgres/SQLite)]
  API --> Queue["Queue (Redis/RQ; fakeredis inline in dev)"]
  API --> Spec["ProtocolSpec/StepSpec\nstored on ProtocolRun.template_config"]
  Queue --> Runner["Engine runner\n(prompt/output resolver + QA)"]
  Runner --> Registry["Engine registry\n(Codex, CodeMachine, ... engines)"]
  Runner --> Outputs["Outputs map\n(.protocols + aux paths)"]
  Outputs --> Prot[".protocols/NNNN-[task] artifacts"]
  Outputs --> Aux["Aux outputs (e.g., .codemachine/outputs)"]
  Queue --> GW["Git/CI Worker\n(clone/worktrees/PR/webhooks/branches)"]
  Queue --> OW["Onboarding Worker\n(project setup/spec audit)"]
  GW --> Git["Git worktrees/branches"]
  GW --> CI["CI (GitHub/GitLab)"]
  CI --> Webhooks["Webhooks / report.sh"]
  Webhooks --> API
  Spec --> Runner
  Git --> Prot
```

## Workflow overview (Mermaid)

```mermaid
flowchart LR
  A["Register project (/projects)"] --> B["project_setup_job\nresolve workspace projects/<id>/<repo>, discovery,\nassets, clarifications"]
  A --> B2["optional: codemachine_import_job\nemits ProtocolSpec + StepSpecs"]
  B --> C["plan_protocol_job\nplan + decompose → ProtocolSpec + StepRuns"]
  C --> D["execute_step_job\nspec-driven prompt/output resolver\nengine registry dispatch"]
  D --> E{"Spec QA policy"}
  E -->|full/light| F["run_quality_job"]
  E -->|skip| G["mark per policy\n(needs_qa or completed)"]
  F --> H{"QA verdict"}
  H -->|PASS| I["Step completed\npolicies may enqueue next steps"]
  H -->|FAIL| J{"Loop/trigger policy?"}
  J -->|retry| D
  J -->|stop| K["Protocol blocked"]
  D --> L["optional push/open PR"]
  L --> M["CI pipelines (GitHub/GitLab)"]
  M --> N["Webhooks/report.sh mirror CI → orchestrator"]
  N --> E
```

## Detailed orchestrator pipelines

### Protocol lifecycle (jobs, policies, QA)

```mermaid
flowchart TD
  A[/POST /projects/] --> B["project_setup_job\nensure docs/prompts/CI assets"]
  A --> C["optional codemachine_import_job\npersist ProtocolSpec + steps"]
  B --> D[/POST /projects/&#123;id&#125;/protocols + start/]
  D --> E["plan_protocol_job\nemit ProtocolSpec\nsync StepRuns from spec"]
  E --> F{"Any pending/blocked steps?"}
  F -->|run| G[/steps/&#123;id&#125;/actions/run → execute_step_job/]
  G --> H["Resolve prompt + outputs via spec\nengine registry dispatch"]
  H --> I{"QA policy (spec)"}
  I -->|full/light| J["run_quality_job\nQA prompt → verdict"]
  I -->|skip| K["Step marked per policy\n(needs_qa or completed)"]
  J --> L{"QA verdict"}
  L -->|PASS| M["Step completed\ntrigger policies may enqueue others"]
  L -->|FAIL| N{"Loop policy?"}
  N -->|apply| F
  N -->|none| O["Protocol blocked; manual retry/resume"]
  K --> F
```

### CI feedback loop

```mermaid
flowchart LR
  A["execute_step_job writes changes\nper spec outputs; may push/open PR"] --> B["CI (GitHub/GitLab) pipelines"]
  B --> C["report.sh or /webhooks/{provider}\nbranch or run_id correlation"]
  C --> D{"CI status normalized"}
  D -->|running| E["Step status → running"]
  D -->|success| F{"QA pending?\n(spec policy or TASKSGODZILLA_AUTO_QA_ON_CI)"}
  F -->|yes| G["run_quality_job enqueued"]
  F -->|no| H["Step completed (CI passed)\nmaybe triggers next step"]
  D -->|failure| I["Step failed; Protocol blocked\nloop/trigger policies may requeue"]
  H --> J{"PR merged?"}
  J -->|yes| K["Protocol completed"]
```

## Protocol pipeline (Codex CLI)

Prerequisites:

- `codex` CLI installed and logged in.
- Git repo with a remote `origin` and base branch (default `main`).
- Optional: `gh` for GitHub PRs, `glab` for GitLab MRs.

Run from the repo root:

```bash
python scripts/protocol_pipeline.py
```

The script will:

- Ask for base branch, short task name, and description.
- Compute the next protocol number `NNNN` and create a worktree/branch `NNNN-[Task-short-name]`.
- Call Codex (default models `gpt-5.1-high` for planning, `gpt-5.1-high` for decomposition) to:
  - Generate `.protocols/NNNN-[Task-short-name]/plan.md`, `context.md`, `log.md`, and step files.
  - Decompose each step into smaller Sub-tasks.

Environment overrides:

- `PROTOCOL_PLANNING_MODEL` (default `gpt-5.1-high`)
- `PROTOCOL_DECOMPOSE_MODEL` (default `gpt-5.1-high`)
- `PROTOCOL_EXEC_MODEL` (default `codex-5.1-max-xhigh`)

### Auto-running a specific step

You can ask the pipeline to auto-run a single step (non-interactively) with a strong coding model:

```bash
python scripts/protocol_pipeline.py --run-step 01-some-step.md
```

This will:

- Run planning and decomposition as above.
- Then call Codex CLI with `PROTOCOL_EXEC_MODEL` from the worktree root, instructing it to execute the Sub-tasks from that step file, following the protocol workflow.

### Auto-opening Draft PR/MR

To automatically create a Draft PR/MR after planning & decomposition:

```bash
python scripts/protocol_pipeline.py --pr-platform github
# or
python scripts/protocol_pipeline.py --pr-platform gitlab
```

The script will:

- Commit the protocol artifacts in the worktree.
- Push branch `NNNN-[Task-short-name]` to `origin`.
- GitHub: use `gh pr create --draft ...` to open a Draft PR.
- GitLab: if `glab` is installed, use `glab mr create --draft ...` to open a Draft MR; otherwise it prints manual instructions.

You can still skip `--pr-platform` to review and commit manually before opening a PR/MR yourself.

## Bootstrap an existing project

If you want to drop this starter into an existing repo (or ensure required files exist), run:

```bash
python3 scripts/project_setup.py --base-branch main --init-if-needed
```

The script will:

- Verify git repo (optionally `git init -b <base>` if missing with `--init-if-needed`).
- Warn if `origin` is not configured or base branch is missing locally.
- Ensure directories/files exist (docs, prompts, CI configs, schema, pipeline); it copies from this starter when available or writes placeholders otherwise.
- Make CI scripts executable.
- Optional: `--clone-url <git-url>` to clone a repo before prep (use `--clone-dir` to set the folder name).
- Optional: `--run-discovery` to call Codex (default `codex-5.1-max`) with `prompts/repo-discovery.prompt.md` to auto-fill CI scripts based on detected stack.

You can also run Codex CI bootstrap directly later:

```bash
python3 scripts/codex_ci_bootstrap.py --model codex-5.1-max
```

## QA orchestrator (Codex CLI)

Validate a protocol step with Codex and stop on failure:

```bash
python3 scripts/quality_orchestrator.py \
  --protocol-root ../worktrees/NNNN-[Task-short-name]/.protocols/NNNN-[Task-short-name] \
  --step-file 01-some-step.md \
  --model codex-5.1-max
```

Behavior:

- Collects plan/context/log, the step file, git status, latest commit message.
- Calls Codex with `prompts/quality-validator.prompt.md`.
- Writes `quality-report.md` in the protocol folder.
- Exits 1 if the verdict is FAIL, halting any pipeline that wraps it.
