# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DevGodzilla is an AI-powered development platform combining:
- **SpecKit**: Specification-driven workflow (artifacts in `.specify/`)
- **Windmill**: Workflow orchestration engine with UI
- **Multi-Agent Execution**: Headless SWE-agent approach (default: `opencode` engine with `zai-coding-plan/glm-4.6` model)

## Architecture

### Core Components

1. **DevGodzilla API** (`devgodzilla/api/app.py`): FastAPI backend
2. **Next.js Console** (`frontend/`): Primary UI at `/console`
3. **Windmill UI**: Secondary workflow UI at root `/`
4. **PostgreSQL**: Two databases - `windmill_db` and `devgodzilla_db`
5. **Redis**: Job queues and caching

### Request Routing (Nginx)

- `/console`, `/_next` → Next.js frontend (port 3000)
- `/projects`, `/protocols`, `/steps`, `/agents`, `/clarifications`, `/speckit`, `/sprints`, `/tasks`, `/docs` → DevGodzilla API (port 8000)
- `/` (default) → Windmill UI (port 8000)
- `/ws/` → LSP server (port 3001)

### Directory Structure

```
devgodzilla/
├── api/           # FastAPI routes and app
├── cli/           # Click-based CLI
├── services/      # Core business logic
├── engines/       # AI agent integrations
├── qa/            # Quality assurance gates
├── db/            # Database models
├── windmill/      # Windmill integration
└── alembic/       # Database migrations

frontend/          # Next.js 16 console (primary UI)
├── app/           # App Router pages
├── components/    # UI components
└── lib/api/       # API client and hooks

windmill/          # Windmill assets
├── flows/         # Workflow definitions
├── scripts/       # Script definitions
└── apps/          # App definitions (including React IIFE bundle)

tests/             # pytest test suite
└── e2e/           # E2E tests with real agents
```

## Common Commands

### Docker Compose Stack

```bash
# Start all services
docker compose up --build -d

# View logs
docker compose logs -f

# Rebuild specific service
docker compose build devgodzilla-api
docker compose up -d devgodzilla-api
```

**Access points:**
- UI: `http://localhost:8080` (or `$DEVGODZILLA_NGINX_PORT`)
- Next.js Console: `http://localhost:8080/console`
- API docs: `http://localhost:8080/docs`
- Health check: `http://localhost:8080/health`

### Development

```bash
# Lint (focuses on syntax/undefined names)
scripts/ci/lint.sh

# Tests (requires opencode CLI installed and authenticated)
scripts/ci/test.sh

# Run single test
.venv/bin/pytest tests/test_devgodzilla_api_e2e_headless_workflow.py -v

# Run with specific markers
.venv/bin/pytest -k "not integration" tests/

# E2E tests with real agents (opt-in)
DEVGODZILLA_RUN_E2E_REAL_AGENT=1 scripts/ci/test_e2e_real_agent.sh
```

### Frontend Development

```bash
cd frontend

# Install dependencies
pnpm install

# Development server (hot reload)
pnpm dev

# Production build
pnpm build

# Lint
pnpm lint
```

**Note:** Next.js console uses `basePath: "/console"` and runs in standalone mode for Docker deployment.

## Agent-Driven Workflow

DevGodzilla executes code via **headless SWE-agents** that write artifacts to the repository:

1. **Discovery** (optional): Agent writes `tasksgodzilla/DISCOVERY.md`, `ARCHITECTURE.md`, etc.
2. **Protocol Planning**: Agent generates `.protocols/<protocol_name>/plan.md` + `step-*.md` (auto-generated if missing when `DEVGODZILLA_AUTO_GENERATE_PROTOCOL=true`)
3. **Step Execution**: Agent runs in protocol worktree; DevGodzilla records artifacts in `.protocols/<protocol_name>/.devgodzilla/steps/<step_run_id>/artifacts/*`
4. **QA Gates**: Quality checks validate step outputs; empty `"gates": []` skips QA

**Default engine/model:**
- `DEVGODZILLA_DEFAULT_ENGINE_ID=opencode`
- `DEVGODZILLA_OPENCODE_MODEL=zai-coding-plan/glm-4.6`

## CLI Commands

Key command groups (via `devgodzilla` CLI):

- `devgodzilla spec`: SpecKit operations (init, specify, plan, tasks)
- `devgodzilla project`: Project CRUD and discovery
- `devgodzilla protocol`: Protocol lifecycle (create, plan, worktree)
- `devgodzilla step`: Step execution and QA
- `devgodzilla agent`: Agent management

## Testing Requirements

- All tests in `tests/` directory
- Unit tests use stub opencode (fast, deterministic)
- E2E tests require real `opencode` CLI installed and authenticated
- Test command checks for `opencode` availability before running

## Key Documentation

- Architecture: `docs/DevGodzilla/ARCHITECTURE.md`
- App architecture: `docs/APP_ARCHITECTURE.md`
- Deployment: `DEPLOYMENT.md`
- DevGodzilla overview: `devgodzilla/README.md`
- Current state: `docs/DevGodzilla/CURRENT_STATE.md`

## Legacy Components

TasksGodzilla (archived under `archive/`) is the legacy orchestrator and is not part of the main stack.

