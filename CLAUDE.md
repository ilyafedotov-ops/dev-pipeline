# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TasksGodzilla Hobby Edition Alpha 0.1 is an agent-driven development orchestrator that implements the TasksGodzilla_Ilyas_Edition_1.0 protocol. It provides protocol-based workflow automation using Codex CLI, with FastAPI orchestration, Redis/RQ queuing, and comprehensive services architecture.

## Development Commands

### Environment Setup
```bash
# Create virtual environment and install dependencies
make orchestrator-setup

# Install dependencies only
make deps

# Run database migrations
make migrate

# Start only Redis/Postgres containers for local development
make compose-deps

# Stop containers
make compose-down
```

### Running the Application

**Local development (SQLite + Redis):**
```bash
TASKSGODZILLA_REDIS_URL=redis://localhost:6379/15 \
TASKSGODZILLA_INLINE_RQ_WORKER=true \
.venv/bin/python scripts/api_server.py
```

**With Docker Compose (full stack):**
```bash
docker compose up --build
# API at http://localhost:8011 (default token: changeme)
# Postgres on 5433, Redis on 6380
```

**With containers for dependencies only:**
```bash
make compose-deps
TASKSGODZILLA_DB_URL=postgresql://tasksgodzilla:tasksgodzilla@localhost:5433/tasksgodzilla \
TASKSGODZILLA_REDIS_URL=redis://localhost:6380/0 \
.venv/bin/python scripts/api_server.py --host 0.0.0.0 --port 8010
```

**RQ Worker (for background jobs):**
```bash
TASKSGODZILLA_REDIS_URL=redis://localhost:6379/15 \
TASKSGODZILLA_DB_PATH=.tasksgodzilla.sqlite \
.venv/bin/python scripts/rq_worker.py
```

**CLI and TUI:**
```bash
# Interactive CLI menu
python -m tasksgodzilla.cli.main
./scripts/tasksgodzilla_cli.py projects list --json

# Textual TUI dashboard
python -m tasksgodzilla.cli.tui
./scripts/tasksgodzilla_tui.py
./tui  # launcher script
```

### Testing

**End-to-End Test (Real Services):**
```bash
# Complete E2E test with API + Worker (~30 seconds)
./scripts/test_e2e_real.sh
```

**Workflow Tests:**
```bash
# Simple workflow test (no external deps, ~10 seconds)
./scripts/test_workflow_simple.sh

# Full workflow test (requires Redis)
./scripts/test_real_workflow.sh
```

**Unit Tests:**
```bash
# Via CI script (recommended)
scripts/ci/test.sh

# Direct pytest
.venv/bin/pytest -q --disable-warnings --maxfail=1

# Single test file
.venv/bin/pytest tests/test_orchestrator_service.py -v

# Test pattern matching
.venv/bin/pytest -k "service" -v
```

**CLI Workflow Harness (integration tests):**
```bash
# Smoke tests (quick validation)
python scripts/cli_workflow_harness.py --mode smoke

# Full workflow validation
python scripts/cli_workflow_harness.py --mode full

# Specific components
python scripts/cli_workflow_harness.py --mode component \
  --components onboarding discovery protocol
```

**Test Hierarchy (run in this order):**
```bash
# 1. Unit tests
pytest tests/

# 2. Workflow tests
./scripts/test_workflow_simple.sh

# 3. E2E with real services
./scripts/test_e2e_real.sh

# 4. Full harness (if needed)
python scripts/cli_workflow_harness.py --mode full
```

### Linting and Type Checking

```bash
# Lint (syntax and undefined names only)
scripts/ci/lint.sh

# Type checking (import smoke tests)
scripts/ci/typecheck.sh

# Manual ruff check (full)
.venv/bin/ruff check tasksgodzilla scripts tests
```

### Project Setup and Protocol Workflows

**Bootstrap a new project:**
```bash
python3 scripts/project_setup.py --base-branch main --init-if-needed
# Optional: --clone-url <git-url> --run-discovery
```

**Create a protocol:**
```bash
python3 scripts/protocol_pipeline.py \
  --base-branch main \
  --short-name "task-name" \
  --description "task description"
# Optional: --pr-platform github|gitlab --run-step 01-some-step.md
```

**Run quality validation:**
```bash
python3 scripts/quality_orchestrator.py \
  --protocol-root ../worktrees/NNNN-task/.protocols/NNNN-task \
  --step-file 01-some-step.md \
  --model codex-5.1-max
```

## Architecture

### Services Layer (Primary Integration Point)

**CRITICAL: Always use the services layer for new features.** The codebase follows a services architecture where:

- **Application Services** (`tasksgodzilla/services/`): Orchestrator, Execution, Quality, Onboarding, Spec, Prompt, Decomposition, Git, Budget, CodeMachine
- **Platform Services** (`tasksgodzilla/services/platform/`): Queue, Storage, Telemetry, Engines
- **API** (`tasksgodzilla/api/`): Thin FastAPI adapter that calls services
- **Workers** (`tasksgodzilla/workers/`): Thin job adapters that delegate to services
- **CLI/TUI** (`tasksgodzilla/cli/`): Use services or API client wrappers

**Service Guidelines:**
- Each service has single responsibility
- Services use dependency injection (pass `db`, other services as constructor args)
- Services follow verb_noun naming (`get_protocol`, `create_step`, etc.)
- Never import workers directly from API endpoints or CLI
- Test services independently with mocks

**Example (correct):**
```python
from tasksgodzilla.services.orchestrator import OrchestratorService
orchestrator = OrchestratorService(db)
run = orchestrator.create_protocol_run(...)
```

**Example (incorrect):**
```python
from tasksgodzilla.workers.codex_worker import handle_plan_protocol  # ❌ Never import workers directly
```

### Key Modules

- `tasksgodzilla/storage.py`: Database operations (SQLAlchemy models, queries)
- `tasksgodzilla/jobs.py`: RQ job definitions
- `tasksgodzilla/pipeline.py`: Protocol pipeline orchestration
- `tasksgodzilla/spec.py`: ProtocolSpec and StepSpec handling
- `tasksgodzilla/engines.py`: Engine registry (Codex, CodeMachine)
- `tasksgodzilla/codex.py`: Codex CLI integration
- `tasksgodzilla/git_utils.py`: Git operations (worktrees, branches)
- `tasksgodzilla/config.py`: Environment-based configuration

### Data Flow

1. **API/CLI** → Services → Workers (enqueue jobs) → Redis Queue
2. **Workers** → Services → Execute engines → Write outputs → Update DB
3. **Quality** → Services → Run QA → Verdict → Update step status
4. **CI** → Webhooks → Services → Update protocol status

### Database Schema

- **projects**: Project metadata, local paths, git config
- **protocol_runs**: Protocol instances (status, spec, metrics)
- **step_runs**: Individual step executions (status, budgets, retries)
- **events**: Audit log and activity feed

Migrations: `alembic/` (use `make migrate` to apply)

## Environment Variables

### Core Configuration
- `TASKSGODZILLA_DB_URL`: PostgreSQL connection (preferred)
- `TASKSGODZILLA_DB_PATH`: SQLite path (default: `.tasksgodzilla.sqlite`)
- `TASKSGODZILLA_REDIS_URL`: Redis connection (required for queuing)
- `TASKSGODZILLA_ENV`: Environment name (default: `local`)
- `TASKSGODZILLA_API_TOKEN`: Optional bearer token for API auth
- `TASKSGODZILLA_WEBHOOK_TOKEN`: Optional shared secret for webhooks

### Execution Models
- `PROTOCOL_PLANNING_MODEL`: Planning model (default: `gpt-5.1-high`)
- `PROTOCOL_DECOMPOSE_MODEL`: Decomposition model (default: `gpt-5.1-high`)
- `PROTOCOL_EXEC_MODEL`: Execution model (default: `codex-5.1-max-xhigh`)
- `PROTOCOL_QA_MODEL`: Quality validation model

### Behavior Flags
- `TASKSGODZILLA_INLINE_RQ_WORKER=true`: Run worker inline with API (dev/test)
- `TASKSGODZILLA_AUTO_QA_AFTER_EXEC=true`: Auto-enqueue QA after execution
- `TASKSGODZILLA_AUTO_QA_ON_CI=true`: Auto-enqueue QA on CI success
- `TASKSGODZILLA_AUTO_CLONE=false`: Disable auto-cloning projects
- `TASKSGODZILLA_GH_SSH=true`: Rewrite GitHub URLs to SSH format
- `TASKSGODZILLA_REQUIRE_ONBOARDING_CLARIFICATIONS=true`: Block until clarifications acknowledged
- `TASKSGODZILLA_LOG_JSON=true`: Emit structured JSON logs
- `PROTOCOL_SKIP_SIMPLE_DECOMPOSE=true`: Skip decomposition for simple steps

### Budget and Limits
- `TASKSGODZILLA_MAX_TOKENS_PER_STEP`: Token limit per step
- `TASKSGODZILLA_MAX_TOKENS_PER_PROTOCOL`: Token limit per protocol
- `TASKSGODZILLA_TOKEN_BUDGET_MODE`: Budget enforcement (strict|warn|off)

### Git Configuration
- `TASKSGODZILLA_GIT_USER`: Git commit author name
- `TASKSGODZILLA_GIT_EMAIL`: Git commit author email
- `TASKSGODZILLA_PROJECTS_ROOT`: Base directory for cloned projects (default: `projects/`)

## Protocol Lifecycle

**Status flow:**
```
pending → planning → planned → running → (paused|blocked|failed|cancelled|completed)
```

**Step status flow:**
```
pending → running → needs_qa → (completed|failed|cancelled|blocked)
```

**QA policies (from spec):**
- `skip`: No QA, mark step as completed or needs_qa per config
- `light`: Quick validation with fast model
- `full`: Comprehensive validation with strong model

**Loop/trigger policies:**
- Loop policy: Retry on QA failure (limited by max attempts)
- Trigger policy: Enqueue dependent steps on success

## Protocol Artifacts

Protocols create worktrees and artifacts in:
```
projects/<project_id>/<repo_name>/       # primary working copy
  .protocols/<protocol_name>/
    plan.md                               # protocol plan
    context.md                            # execution context
    log.md                                # execution log
    NN-step-name.md                       # step files
    quality-report.md                     # QA verdict
worktrees/<protocol_name>/                # isolated worktree for this protocol
  .protocols/<protocol_name>/...
```

## CI Integration

The repo includes dual CI templates for GitHub Actions and GitLab CI that call shared scripts in `scripts/ci/`:

- `bootstrap.sh`: Install dependencies
- `lint.sh`: Run ruff (syntax/undefined names)
- `typecheck.sh`: Import smoke tests
- `test.sh`: Run pytest with proper env vars
- `build.sh`: Build artifacts (placeholder)
- `report.sh`: Send CI status to orchestrator webhook

**CI callback integration:**
```bash
# In CI, export API base and call report.sh
export TASKSGODZILLA_API_BASE=http://api:8010
scripts/ci/report.sh success|failure
```

Set `TASKSGODZILLA_PROTOCOL_RUN_ID` if branch detection is ambiguous.

## Testing Strategy

- **Unit tests**: `tests/test_*_service.py` for services
- **Integration tests**: `tests/test_integration_*.py` for service interactions
- **API tests**: `tests/test_api_*.py` for endpoints
- **Property tests**: `tests/test_*_properties.py` using Hypothesis
- **Workflow tests**: `scripts/cli_workflow_harness.py` for end-to-end validation

Target: 85%+ test coverage

## Logging

Set `TASKSGODZILLA_LOG_JSON=true` for structured JSON logs from CLIs/workers/API.

Log levels: DEBUG, INFO, WARNING, ERROR (controlled by `TASKSGODZILLA_LOG_LEVEL`)

## Common Patterns

### Creating a new service
1. Add service module in `tasksgodzilla/services/`
2. Define service class with dependency injection
3. Export from `tasksgodzilla/services/__init__.py`
4. Call from API endpoints or workers
5. Write unit tests with mocked dependencies

### Adding a new API endpoint
1. Define route in `tasksgodzilla/api/app.py`
2. Create Pydantic schema in `tasksgodzilla/api/schemas.py`
3. Call appropriate service method
4. Return structured response
5. Add endpoint test in `tests/test_api_endpoints.py`

### Creating a new worker job
1. Define job function in `tasksgodzilla/jobs.py`
2. Enqueue via service (don't import job directly)
3. Worker delegates to service method
4. Service handles all business logic
5. Test service independently

## CodeMachine Integration

Import `.codemachine` workspaces via `POST /projects/{id}/codemachine/import` to:
- Persist template graph as ProtocolSpec + StepSpecs
- Use spec-driven execution with unified engine runner
- Apply QA policies (skip/light/full) from spec
- Handle loop/trigger module policies

## Monitoring

- `/metrics`: Prometheus metrics endpoint
- `/queues`: Queue statistics
- `/queues/jobs`: Job payloads and status
- `/console`: Web-based dashboard
- Events API: Activity feed and audit log

## Protocol Execution with Codex

**Example step execution:**
```bash
codex --model codex-5.1-max-xhigh \
  --cd ../worktrees/NNNN-task \
  --sandbox workspace-write \
  --ask-for-approval on-request \
  "Follow .protocols/NNNN-task/plan.md and implement the current step."
```

Default models are configured via environment variables or per-protocol spec.
