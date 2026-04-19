# DevGodzilla

DevGodzilla is an AI-powered software development orchestration platform: a FastAPI backend (`devgodzilla/`), a Next.js console (`frontend/`), and Windmill workflow orchestration (`windmill/`) behind nginx.

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy (SQLite/PostgreSQL), Pydantic |
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS, Radix UI, TanStack Query |
| **Orchestration** | Windmill (DAG-based workflow engine), Redis, PostgreSQL |
| **AI Engines** | OpenCode, Claude Code, Codex, Gemini CLI (pluggable adapter system) |
| **Deployment** | Docker Compose, Kubernetes, nginx reverse proxy |

## Documentation Source of Truth

- `docs/DevGodzilla/CURRENT_STATE.md` (what runs today)
- `docs/DevGodzilla/ARCHITECTURE.md` (layered architecture, current vs target)
- `docs/DevGodzilla/API-ARCHITECTURE.md` (API architecture and domains)
- `docs/DevGodzilla/WINDMILL-WORKFLOWS.md` (Windmill scripts/flows/resources)

Historical docs are archived under `docs/legacy/` with mapping in `docs/legacy/README.md`.

## Repository Layout

| Directory | Purpose |
|-----------|---------|
| `devgodzilla/` | FastAPI API, services layer, engine adapters, DB access, Windmill client |
| `frontend/` | Next.js console with DAG visualization, agile boards, real-time events |
| `windmill/` | Windmill scripts/flows/apps exported from this repo |
| `Origins/` | Vendored upstream sources (Windmill, spec-kit) - do not edit |
| `scripts/` | Operational scripts and CI wrappers (`scripts/ci/`) |
| `tests/` | pytest suite for backend/services/workflows |
| `docs/` | Active + archived documentation |
| `prompts/` | Reusable agent/system prompts for protocol workflows |
| `schemas/` | JSON schema contracts for protocol artifacts |
| `k8s/` | Kubernetes deployment manifests |

## Runtime Topology

All services run in Docker. nginx on port 8080 is the single entry point.

| Service | Port | Description |
|---------|------|-------------|
| nginx | 8080 | Reverse proxy, single entry point |
| devgodzilla-api | 8000 | FastAPI backend |
| frontend | 3000 | Next.js console |
| windmill | 8001 | Workflow orchestration server |
| windmill_worker | - | Default worker (Docker socket) |
| windmill_worker_native | - | Native Python worker (8 workers) |
| db | 5432 | PostgreSQL 16 |
| redis | 6379 | Redis 7 |
| lsp | 3001 | Language Server Protocol |

**Routing** (defined in `nginx.devgodzilla.conf`):

| Path | Target |
|------|--------|
| `/console`, `/_next` | frontend (Next.js) |
| `/projects`, `/protocols`, `/steps`, etc. | devgodzilla-api |
| `/ws/events` | Backend WebSocket |
| `/` (fallback) | Windmill UI |

## Quick Start

### Prerequisites

- Docker + Docker Compose
- (Optional) Python 3.12, Node.js 20+ for host-side development

### 1) Start the full stack

```bash
docker compose up --build -d
# or use the helper script
scripts/run-local-dev.sh up
```

### 2) Import Windmill assets (one-shot bootstrap)

```bash
scripts/run-local-dev.sh import
```

### 3) Open interfaces

- **Console**: http://localhost:8080/console
- **API Docs**: http://localhost:8080/docs
- **Windmill UI**: http://localhost:8080/

## Host-side Development (Hybrid Mode)

For development with local API keys and hot-reload:

```bash
# Prerequisites: Python 3.12, Node.js 20+, pnpm
scripts/ci/bootstrap.sh          # create .venv, install deps

# Hybrid mode: infra in Docker, API + frontend on host
scripts/run-local-dev.sh dev

# Or manage individually:
scripts/run-local-dev.sh backend start|stop|restart|status
scripts/run-local-dev.sh frontend start|stop|restart|status
```

### Development Scripts

| Script | Purpose |
|--------|---------|
| `scripts/run-local-dev.sh up` | Build and start full Docker stack |
| `scripts/run-local-dev.sh down` | Stop Docker infra |
| `scripts/run-local-dev.sh clean` | Stop Docker + remove volumes |
| `scripts/run-local-dev.sh status` | Show Docker infra status |
| `scripts/run-local-dev.sh logs` | Tail Docker logs |
| `scripts/run-local-dev.sh dev` | Infra + backend + frontend (hybrid) |

### Stack Manager & Monitor

`scripts/pipeline-ctl.sh` is a unified manager/monitor over the full stack —
containers, host dev processes, HTTP health endpoints, and DB/Redis probes.
Output is coloured and `NO_COLOR`-aware; every column is scriptable.

```bash
scripts/pipeline-ctl.sh status          # one-shot table
scripts/pipeline-ctl.sh health --exit-code  # CI-friendly: non-zero if any down
scripts/pipeline-ctl.sh watch           # live refresh (Ctrl-C to exit)
scripts/pipeline-ctl.sh logs windmill devgodzilla-api --grep ERROR --save
scripts/pipeline-ctl.sh restart windmill          # waits for healthy
scripts/pipeline-ctl.sh fix rebuild-api           # compose build + up -d + wait
```

Makefile shortcuts: `make ctl-status`, `make ctl-health`, `make ctl-watch`,
`make ctl-logs`. See `scripts/pipeline-ctl.sh help` for the full surface.

## Development Commands

```bash
# Lint (ruff - runtime-breaking checks only)
scripts/ci/lint.sh

# Type/import checks (compileall + import smoke)
scripts/ci/typecheck.sh

# Unit tests (pytest, skips integration by default)
scripts/ci/test.sh

# Run all CI checks
scripts/ci/bootstrap.sh && scripts/ci/lint.sh && scripts/ci/typecheck.sh && scripts/ci/test.sh
```

## API Surface

Route domains under `devgodzilla/api/routes/`:

| Domain | Routes | Description |
|--------|--------|-------------|
| **Core** | `/projects`, `/protocols`, `/steps`, `/agents`, `/clarifications` | Project and protocol lifecycle |
| **SpecKit** | `/speckit/*`, `/specifications*` | Specification management |
| **Agile** | `/sprints*`, `/tasks*` | Sprint boards, task tracking |
| **Governance** | `/policy_packs*`, `/projects/{id}/policy*`, `/quality/dashboard` | Policy enforcement, QA gates |
| **Operations** | `/events*`, `/logs*`, `/metrics*`, `/queues*`, `/runs*` | Monitoring and observability |
| **Windmill** | `/flows*`, `/jobs*` | Windmill passthrough |
| **Webhooks** | `/webhooks/*` | External integrations |

For exact schemas: `GET /openapi.json`

## Backend Architecture

### Core Services (`devgodzilla/services/`)

| Service | Responsibility |
|---------|---------------|
| **OrchestratorService** | Protocol lifecycle, Windmill DAG execution, recovery |
| **PlanningService** | Step decomposition, policy resolution, DAG generation |
| **ExecutionService** | Step execution via AI engines, artifact writing |
| **QualityService** | QA gate orchestration, verdict aggregation |
| **SpecificationService** | SpecKit integration, spec/plan/tasks generation |
| **DiscoveryAgentService** | Repository discovery, architecture analysis |
| **PolicyService** | Policy pack resolution, effective policy merging |
| **GitService** | Repository management, worktrees, PRs |
| **AgentConfigService** | Per-project agent/model configuration |

### Engine Adapters (`devgodzilla/engines/`)

Pluggable AI coding agents with unified interface (`plan()`, `execute()`, `qa()`):

| Engine | Kind | Capabilities |
|--------|------|--------------|
| opencode | CLI | code_gen, code_review, reasoning |
| claude-code | CLI | code_gen, code_review |
| codex | CLI | code_gen |
| gemini-cli | CLI | code_gen, reasoning |
| dummy | CLI | Testing/fallback |

### Database Schema

Core tables: `projects`, `protocol_runs`, `step_runs`, `speckit_specs`, `job_runs`, `qa_results`, `events`, `clarifications`, `sprints`, `tasks`, `policy_packs`

Supports SQLite (development) and PostgreSQL (production) via SQLAlchemy.

## Frontend Features

The Next.js console (`/console`) provides:

| Feature | Description |
|---------|-------------|
| **Protocol Management** | Create, start/pause/resume/cancel protocols |
| **DAG Visualization** | Linear and DAG views with D3-dag rendering |
| **Agile Board** | Kanban sprint board with drag-and-drop |
| **Real-time Events** | WebSocket event feed with filtering |
| **Logs Console** | Streaming log viewer |
| **Quality Dashboard** | QA gate status and findings |
| **Agent Health** | Agent status and metrics |
| **Dark/Light Theme** | Theme switching support |

### Key Frontend Routes

| Route | Purpose |
|-------|---------|
| `/` | Dashboard |
| `/projects` | Project management |
| `/protocols/[id]` | Protocol detail (spec, steps, runs, logs, artifacts, quality, policy, feedback) |
| `/sprints` | Sprint/execution board |
| `/quality` | Quality gates dashboard |
| `/ops` | Operations (queues, events, logs, metrics) |
| `/agents` | Agent configuration |
| `/policy-packs` | Policy pack management |

## Windmill Integration

### Directory Structure (`windmill/`)

| Directory | Content |
|-----------|---------|
| `scripts/devgodzilla/` | Python scripts → `u/devgodzilla/*` |
| `flows/devgodzilla/` | Flow definitions → `f/devgodzilla/*` |
| `apps/` | App definitions including React app |

### Key Flows

- `onboard_to_tasks` - Project onboarding pipeline
- `spec_to_protocol` - Specification to protocol conversion
- `execute_protocol` - Protocol execution orchestration

Scripts communicate with DevGodzilla API via `DEVGODZILLA_API_URL` environment variable.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVGODZILLA_DB_URL` | `postgresql://...` | Database URL |
| `DEVGODZILLA_WINDMILL_URL` | `http://windmill:8000` | Windmill API URL |
| `DEVGODZILLA_WINDMILL_WORKSPACE` | `demo1` | Windmill workspace |
| `DEVGODZILLA_NGINX_PORT` | `8080` | External port |
| `WINDMILL_JOB_TIMEOUT_SECONDS` | `3600` | Job timeout |
| `WINDMILL_FEATURES` | `static_frontend python deno_core` | Windmill features |

### Agent Configuration (`devgodzilla/config/agents.yaml`)

Defines available AI engines with their capabilities, commands, and default models. Per-project overrides supported via `AgentConfigService`.

## Documentation Maintenance

If docs and code disagree, trust code first, then update the canonical docs in `docs/DevGodzilla/`.

## Testing

```bash
# Run all unit tests
pytest -q tests/test_devgodzilla_*.py

# Run with coverage
pytest --cov=devgodzilla tests/

# Run integration tests (requires live services)
DEVGODZILLA_RUN_LIVE_INTEGRATION_TESTS=1 pytest tests/test_devgodzilla_frontend_integration.py
```

## Kubernetes Deployment

Manifests in `k8s/`:

- `api-deployment.yaml` - DevGodzilla API (250m-500m CPU, 256-512Mi memory)
- `worker-deployment.yaml` - RQ worker for background jobs

Secrets expected in `devgodzilla-secrets`: `db_url`, `redis_url`, `api_token`
