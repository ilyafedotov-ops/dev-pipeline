# DevGodzilla - Comprehensive Architecture Document

## Table of Contents
1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Frontend Architecture](#frontend-architecture)
4. [Backend Architecture](#backend-architecture)
5. [Services Layer](#services-layer)
6. [Engines Layer](#engines-layer)
7. [Windmill Integration](#windmill-integration)
8. [Data Layer](#data-layer)
9. [CI/CD & Deployment](#cicd--deployment)
10. [Origins & Vendored Components](#origins--vendored-components)
11. [Authentication & Authorization](#authentication--authorization)
12. [Quality Assurance](#quality-assurance)
13. [Configuration Management](#configuration-management)
14. [Event System](#event-system)
15. [Workflow Execution](#workflow-execution)

---

## Overview

DevGodzilla is an open-source, specification-driven, AI-powered development platform that combines:

- **SpecKit**: Specification-driven development workflow
- **Windmill**: Industrial-grade workflow orchestration
- **Multi-Agent Execution**: 18+ AI coding agents (Codex, Claude, OpenCode, etc.)

The platform runs a headless SWE-agent workflow where AI agents write artifacts into the repo/worktree, and DevGodzilla validates/records outputs.

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS, Radix UI |
| **Backend** | Python 3.12+, FastAPI 0.124, Pydantic 2.12 |
| **Database** | PostgreSQL 16 (production), SQLite (development) |
| **Cache/Queue** | Redis 7, RQ 2.6 |
| **Workflow** | Windmill (self-hosted from Origins/) |
| **Testing** | pytest 9.0, Vitest 4.0 |
| **Container** | Docker, Docker Compose |

### Key Directories

```
dev-pipeline/
├── devgodzilla/           # Primary backend (FastAPI, services, engines)
├── frontend/              # Primary frontend (Next.js console at /console)
├── windmill/              # Windmill flows/scripts/apps (syncs to Windmill)
├── Origins/               # Vendored upstream sources (Windmill, SpecKit)
├── archive/               # Archived legacy code (TasksGodzilla)
├── scripts/               # Operational CLIs and CI hooks
├── tests/                 # pytest tests for DevGodzilla API/services
├── docs/                  # Architecture and process documentation
├── prompts/               # Reusable agent prompts
├── schemas/               # JSON schemas
├── alembic/               # Database migrations
├── k8s/                   # Kubernetes deployment configs
└── tui-rs/                # Rust-based TUI
```

---

## System Architecture

### High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Access                           │
│  Browser (http://localhost:8080) → Nginx Reverse Proxy      │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Next.js    │    │   Windmill   │    │ DevGodzilla  │
│   Console    │    │   Platform   │    │     API      │
│   (/console) │    │      (/)     │    │   (:8000)    │
└──────────────┘    └──────────────┘    └──────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   PostgreSQL │    │    Redis     │    │   Workers    │
│ (devgodzilla │    │    Queue     │    │  (Windmill)  │
│   + Windmill)│    │   + Cache    │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
```

### Request Routing (Nginx)

```nginx
# DevGodzilla API endpoints
/health, /projects, /protocols, /steps, /agents, /clarifications,
/speckit, /sprints, /tasks, /metrics, /webhooks, /events, /flows,
/jobs, /runs, /docs, /redoc, /openapi.json
→ devgodzilla-api:8000

# Next.js Console (primary frontend)
/console, /_next → frontend:3000

# LSP WebSocket
/ws/ → lsp:3001

# Default (Windmill platform)
/ → windmill:8000
```

---

## Frontend Architecture

### Primary Frontend: Next.js Console (`/console`)

The Next.js application is the primary user interface, served at `/console` path.

| Component | Location | Description |
|-----------|----------|-------------|
| **Next.js App** | `frontend/` | Next.js 16 with App Router, React 19, Tailwind CSS |
| **Base Path** | `/console` | All routes served under this path |
| **Build Mode** | Standalone export | Optimized for Docker deployment |

#### Key Features

- **Projects Dashboard** - Project management and onboarding
- **Protocols & Steps** - Workflow execution monitoring
- **Sprint Management** - Agile board with Kanban view (`/console/sprints`)
- **Runs & Artifacts** - Execution history and outputs
- **Policy Management** - Policy pack configuration
- **Quality Dashboard** - QA gate monitoring

#### Route Structure

```
frontend/app/
├── page.tsx                    # Dashboard
├── projects/
│   ├── page.tsx                # Projects list
│   └── [id]/
│       ├── page.tsx            # Project overview
│       ├── protocols/          # Protocol management
│       ├── sprint-board/       # Sprint Kanban
│       ├── onboarding/         # Onboarding flow
│       ├── clarifications/     # User clarifications
│       └── policy/            # Policy configuration
├── protocols/
│   ├── page.tsx               # Protocol list
│   └── [id]/
│       ├── page.tsx           # Protocol detail
│       ├── steps/             # Step execution
│       ├── runs/              # Run history
│       └── clarifications/    # Clarification requests
├── runs/
│   ├── page.tsx              # Runs list
│   └── [runId]/
│       ├── artifacts/         # Artifacts viewer
│       └── logs/             # Execution logs
├── sprints/
│   └── page.tsx             # Sprint management
├── policy-packs/             # Policy management
├── quality/                  # QA monitoring
└── ops/                      # Operations dashboard
    ├── events/               # Event log
    ├── logs/                 # System logs
    ├── metrics/              # Metrics dashboard
    └── queues/              # Queue monitoring
```

#### UI Component Stack

- **Radix UI**: Unstyled component primitives
- **Tailwind CSS**: Utility-first styling
- **shadcn/ui**: Pre-built Radix components
- **Lucide React**: Icon set
- **Monaco Editor**: Code editor integration
- **React Query**: Data fetching and caching
- **TanStack Table**: Data tables
- **D3.js**: Visualization libraries

#### API Client

```typescript
// lib/api/* provides typed API client
import { useProjects, useProtocols, useRuns } from "@/lib/api"

// React Query integration for automatic caching
const { data: projects } = useProjects()
```

---

## Backend Architecture

### DevGodzilla API

FastAPI-based backend providing comprehensive REST endpoints.

| Endpoint Group | Purpose |
|---------------|---------|
| `/health` | Health checks and readiness |
| `/projects` | Project CRUD and management |
| `/protocols` | Protocol lifecycle |
| `/steps` | Step execution and status |
| `/agents` | Agent configuration and health |
| `/clarifications` | User clarification requests |
| `/speckit` | SpecKit integration |
| `/sprints` | Agile sprint management |
| `/tasks` | Task management |
| `/flows` | Windmill flow proxies |
| `/jobs` | Windmill job proxies |
| `/runs` | Run management and artifacts |
| `/metrics` | Prometheus metrics |
| `/webhooks` | CI/CD webhook handling |
| `/events` | Event streaming |
| `/logs` | Log access |
| `/queues` | Queue management |
| `/policy_packs` | Policy management |
| `/specifications` | Specification CRUD |
| `/quality` | QA gate endpoints |
| `/profile` | User profile |
| `/cli-executions` | CLI execution tracking |

### API Structure

```
devgodzilla/api/
├── app.py                      # FastAPI application
├── dependencies.py              # Dependency injection
├── schemas.py                  # Pydantic models
└── routes/
    ├── projects.py              # Project endpoints
    ├── protocols.py            # Protocol endpoints
    ├── steps.py               # Step endpoints
    ├── agents.py              # Agent endpoints
    ├── clarifications.py      # Clarification endpoints
    ├── speckit.py            # SpecKit endpoints
    ├── sprints.py            # Sprint endpoints
    ├── tasks.py              # Task endpoints
    ├── windmill.py           # Windmill proxy endpoints
    ├── runs.py               # Run endpoints
    ├── metrics.py            # Metrics endpoints
    ├── webhooks.py           # Webhook endpoints
    ├── events.py             # Event endpoints
    ├── logs.py               # Log endpoints
    ├── queues.py             # Queue endpoints
    ├── policy_packs.py       # Policy pack endpoints
    ├── specifications.py     # Specification endpoints
    ├── quality.py            # QA endpoints
    ├── profile.py            # User profile
    └── cli_executions.py    # CLI execution tracking
```

### Dependency Injection

```python
from devgodzilla.api.dependencies import (
    get_db,                # Database connection
    get_service_context,    # Service context
    require_api_token,     # Auth middleware
    require_webhook_token,  # Webhook auth
)
```

---

## Services Layer

The services layer is the primary business logic interface, organized into two tiers:

### Platform Services (Infrastructure)

| Service | Purpose | Dependencies |
|---------|---------|--------------|
| **QueueService** | Job queue management (Redis/RQ) | None |
| **TelemetryService** | Metrics and observability | None |

### Application Services (Business Logic)

| Service | Purpose | Dependencies |
|---------|---------|--------------|
| **OrchestratorService** | Protocol/step lifecycle orchestration | DB, Queue, SpecService |
| **ExecutionService** | Step execution coordination | DB, Budget, Git, Orchestrator, Spec, Prompt, Quality |
| **QualityService** | QA and validation | DB, Budget, Git, Orchestrator, Spec, Prompt |
| **SpecService** | Specification management | DB |
| **PromptService** | Prompt resolution and context | None |
| **OnboardingService** | Project onboarding | DB, Git |
| **GitService** | Git operations (worktrees, PRs, CI) | DB |
| **BudgetService** | Token budget tracking | None |
| **DecompositionService** | Step decomposition | None |
| **CodeMachineService** | CodeMachine workspace import | DB |
| **AgentConfigService** | Agent configuration management | DB |
| **ConstitutionService** | Policy/constitution management | DB |
| **PolicyService** | Policy pack enforcement | DB, ConstitutionService |
| **EventPersistenceService** | Event sink for database | DB |

### Service Architecture Pattern

```python
class MyService:
    def __init__(self, context: ServiceContext, db: Database):
        self.context = context
        self.db = db

    async def some_business_method(self, entity_id: str) -> Result:
        # Business logic here
        pass
```

### Key Service Patterns

1. **OrchestratorService** - High-level coordination
   - Protocol lifecycle management
   - Trigger/loop policy application
   - Step completion handling
   - Next step selection

2. **ExecutionService** - Step execution
   - Prompt resolution
   - Engine selection
   - Token budgeting
   - Git/worktree operations
   - Inline QA orchestration

3. **QualityService** - QA gates
   - QA prompt resolution
   - Engine execution
   - Verdict recording
   - Auto-fix attempts

---

## Engines Layer

### Engine Registry

The engines layer provides a unified interface for AI agent execution.

| Engine | Type | Purpose |
|--------|------|---------|
| **opencode** | Default | Primary coding agent |
| **claude_code** | LLM | Claude Code integration |
| **codex** | LLM | OpenAI Codex |
| **cursor** | LLM | Cursor AI |
| **gemini** | LLM | Google Gemini |
| **dummy** | Mock | Testing stub |

### Engine Interface

```python
from devgodzilla.engines.interface import Engine

class Engine:
    async def execute(
        self,
        prompt: str,
        context: dict,
        model: str
    ) -> ExecutionResult:
        """Execute AI agent with prompt and context"""
        pass

    async def health_check(self) -> bool:
        """Check engine availability"""
        pass
```

### Engine Configuration

```yaml
# config/agents.yaml
engines:
  opencode:
    enabled: true
    default_model: "zai-coding-plan/glm-4.6"
  claude_code:
    enabled: true
    default_model: "claude-3-5-sonnet-20241022"
```

### Artifact Locations

- Repo discovery: `specs/discovery/_runtime/DISCOVERY.md`, `DISCOVERY_SUMMARY.json`
- Protocol definitions: `.protocols/<protocol_name>/plan.md` + `step-*.md`
- Execution artifacts: `.protocols/<protocol_name>/.devgodzilla/steps/<step_run_id>/artifacts/*`

---

## Windmill Integration

### Windmill Components

| Component | Purpose |
|-----------|---------|
| **Windmill Server** | Workflow orchestration platform |
| **Windmill Workers** | Job execution (Python, Deno) |
| **LSP Server** | Code intelligence (Language Server Protocol) |

### Windmill Flows

```yaml
windmill/flows/devgodzilla/
├── execute_protocol.flow.json      # Execute full protocol
├── project_onboarding.flow.json    # Onboard new project
├── spec_to_protocol.flow.json     # Convert spec to protocol
├── step_execute_with_qa.flow.json # Execute step with QA
├── sprint_from_protocol.flow.json  # Create sprint from protocol
└── sync_tasks_to_sprint.flow.json # Sync tasks to sprint board
```

### Windmill Scripts

```yaml
windmill/scripts/devgodzilla/
├── _api.py                       # Base API client
├── execute_step.py               # Step execution script
├── generate_plan.py               # Generate implementation plan
├── generate_spec.py              # Generate specification
├── clone_repo.py                 # Git clone operations
├── open_pr.py                    # Pull request creation
└── handle_feedback.py            # User feedback handling
```

### Windmill Apps

```yaml
windmill/apps/devgodzilla/
├── devgodzilla_projects.app.json       # Projects app
├── devgodzilla_protocols.app.json     # Protocols app
├── devgodzilla_project_detail.app.json # Project detail app
└── devgodzilla_protocol_detail.app.json # Protocol detail app
```

### Windmill Integration Pattern

```python
from devgodzilla.windmill.client import WindmillClient, WindmillConfig

client = WindmillClient(
    WindmillConfig(
        base_url="http://localhost:8000",
        token="windmill-token",
        workspace="devgodzilla"
    )
)

# Execute flow
result = await client.execute_flow(
    path="f/devgodzilla/execute_protocol",
    input={"protocol_id": "123"}
)
```

---

## Data Layer

### Database Schema

Two PostgreSQL databases:

| Database | Purpose |
|----------|---------|
| `windmill_db` | Windmill workflows, jobs, users |
| `devgodzilla_db` | DevGodzilla projects, protocols, steps |

### Key Tables

**Projects**
- `id`, `name`, `repo_url`, `base_branch`, `created_at`, `updated_at`

**ProtocolRuns**
- `id`, `project_id`, `protocol_name`, `status`, `created_at`, `updated_at`

**StepRuns**
- `id`, `protocol_run_id`, `step_name`, `status`, `engine_id`, `model`

**Events**
- `id`, `entity_type`, `entity_id`, `event_type`, `message`, `timestamp`

**Clarifications**
- `id`, `project_id`, `protocol_run_id`, `question`, `answer`

**PolicyPacks**
- `id`, `key`, `version`, `pack_json`, `status`

**Sprints**
- `id`, `project_id`, `protocol_run_id`, `status`, `columns`

**Tasks**
- `id`, `sprint_id`, `column_id`, `title`, `description`, `status`

### Database Configuration

```python
# Via environment
DEVGODZILLA_DB_URL=postgresql://user:pass@host:5432/devgodzilla_db

# SQLite fallback (development)
DEVGODZILLA_DB_PATH=.devgodzilla.sqlite
```

### Migrations

```bash
# Alembic migrations
alembic upgrade head    # Apply migrations
alembic revision --autogenerate -m "description"  # Create migration
```

---

## CI/CD & Deployment

### Docker Compose Stack

```yaml
services:
  nginx           # Reverse proxy (8080)
  frontend        # Next.js console (3000)
  devgodzilla-api # FastAPI backend (8000)
  windmill        # Windmill server (8000)
  windmill_worker # Job execution
  db              # PostgreSQL (5432)
  redis           # Redis (6379)
  lsp             # Language Server Protocol (3001)
```

### Local Development

```bash
# Start everything
scripts/run-local-dev.sh dev

# Start infra only
docker compose up --build -d

# Import Windmill assets
scripts/run-local-dev.sh import
```

### CI Pipeline (GitHub Actions)

```yaml
.github/workflows/ci.yml:
  - Bootstrap (scripts/ci/bootstrap.sh)
  - Lint (scripts/ci/lint.sh)         # ruff check
  - Typecheck (scripts/ci/typecheck.sh) # compileall
  - Test (scripts/ci/test.sh)           # pytest
  - Build (scripts/ci/build.sh)         # Next.js build
```

### Kubernetes Deployment

```yaml
k8s/
├── api-deployment.yaml      # DevGodzilla API
└── worker-deployment.yaml   # Worker pods
```

---

## Origins & Vendored Components

### SpecKit (`Origins/spec-kit/`)

SpecKit provides specification-driven development workflow.

- Templates: `templates/` (spec, plan, tasks)
- CLI: `specify_cli/`
- Memory: `memory/constitution.md`

### Windmill (`Origins/Windmill/`)

Self-hosted Windmill source (vendored).

- Server: `Dockerfile`, `openflow.openapi.yaml`
- Python Client: `python-client/wmill/`
- TypeScript Client: `typescript-client/`
- LSP: `lsp/`

### CodeMachine (`Origins/CodeMachine-CLI/`)

CodeMachine CLI for workspace import and management.

---

## Authentication & Authorization

### Auth Methods

| Method | Env Vars |
|--------|----------|
| **Bearer Token** | `DEVGODZILLA_API_TOKEN` |
| **JWT** | `DEVGODZILLA_JWT_SECRET`, `DEVGODZILLA_ADMIN_USERNAME`, `DEVGODZILLA_ADMIN_PASSWORD_HASH` |
| **OIDC/SSO** | `DEVGODZILLA_OIDC_ISSUER`, `DEVGODZILLA_OIDC_CLIENT_ID`, `DEVGODZILLA_OIDC_CLIENT_SECRET` |

### Auth Flow

```python
# API token middleware
@app.get("/projects", dependencies=[Depends(require_api_token)])
async def list_projects():
    pass

# JWT auth
@app.post("/api/auth/login")
async def login(credentials: LoginRequest):
    token = create_access_token(credentials.username)
    return {"access_token": token}
```

### Frontend Auth

```typescript
// /api/auth/login - Login endpoint
// /api/auth/callback - OIDC callback
// /api/auth/logout - Logout
// /api/auth/me - Current user
```

---

## Quality Assurance

### QA Gates

| Gate Type | Purpose |
|-----------|---------|
| **Execution QA** | Validate step outputs |
| **Constitution QA** | Ensure policy compliance |
| **Security QA** | Security vulnerability checks |
| **SpecKit QA** | Specification validation |

### QA Flow

```python
from devgodzilla.services.quality import QualityService

qa = QualityService(context, db)

# Evaluate step
result = await qa.evaluate_step(step_run_id)

# Auto-fix attempts
if result.verdict == "fail" and config.qa_auto_fix_enabled:
    result = await qa.auto_fix_step(step_run_id)
```

### QA Configuration

```python
# Environment variables
DEVGODZILLA_AUTO_QA_ON_CI=true          # Auto-run QA on CI success
DEVGODZILLA_AUTO_QA_AFTER_EXEC=true      # Auto-run QA after execution
DEVGODZILLA_QA_AUTO_FIX_ENABLED=true     # Enable auto-fix
DEVGODZILLA_QA_MAX_AUTO_FIX_ATTEMPTS=3   # Max fix attempts
```

---

## Configuration Management

### Centralized Config (`devgodzilla/config.py`)

All configuration via Pydantic models with `DEVGODZILLA_` prefix.

### Key Categories

**Database**
- `DEVGODZILLA_DB_URL`, `DEVGODZILLA_DB_PATH`, `DEVGODZILLA_DB_POOL_SIZE`

**Environment**
- `DEVGODZILLA_ENV`, `DEVGODZILLA_LOG_LEVEL`, `DEVGODZILLA_API_TOKEN`

**Auth**
- `DEVGODZILLA_JWT_SECRET`, `DEVGODZILLA_OIDC_ISSUER`, `DEVGODZILLA_ADMIN_USERNAME`

**Models**
- `DEVGODZILLA_PLANNING_MODEL`, `DEVGODZILLA_EXEC_MODEL`, `DEVGODZILLA_QA_MODEL`

**Engines**
- `DEVGODZILLA_DEFAULT_ENGINE_ID`, `DEVGODZILLA_DISCOVERY_ENGINE_ID`

**Token Budgets**
- `DEVGODZILLA_MAX_TOKENS_PER_STEP`, `DEVGODZILLA_MAX_TOKENS_PER_PROTOCOL`

**QA**
- `DEVGODZILLA_AUTO_QA_ON_CI`, `DEVGODZILLA_AUTO_QA_AFTER_EXEC`

**Windmill**
- `DEVGODZILLA_WINDMILL_URL`, `DEVGODZILLA_WINDMILL_TOKEN`, `DEVGODZILLA_WINDMILL_WORKSPACE`

### Config Loading

```python
from devgodzilla.config import load_config, get_config

config = load_config()
# or
config = get_config()  # Singleton
```

---

## Event System

### Event Types

| Type | Purpose |
|------|---------|
| `protocol_created` | Protocol run created |
| `protocol_started` | Protocol execution started |
| `protocol_completed` | Protocol finished |
| `protocol_failed` | Protocol failed |
| `step_started` | Step execution started |
| `step_completed` | Step execution completed |
| `step_failed` | Step execution failed |
| `qa_passed` | QA gate passed |
| `qa_failed` | QA gate failed |
| `policy_finding` | Policy violation detected |
| `git_pr_created` | Pull request created |
| `ci_success` | CI pipeline passed |
| `ci_failure` | CI pipeline failed |

### Event Streaming

```python
from devgodzilla.services.events import emit_event

await emit_event(
    entity_type="protocol",
    entity_id=protocol_run_id,
    event_type="protocol_started",
    message="Protocol execution started",
    metadata={"step_count": 5}
)
```

### Event API

```http
GET /events?entity_type=protocol&entity_id=123
```

---

## Workflow Execution

### Protocol Lifecycle

```
pending → planning → planned → running → (paused | blocked | failed | completed)
```

### Step Lifecycle

```
pending → running → needs_qa → (completed | failed | cancelled | blocked)
```

### Execution Flow

```python
# 1. Create protocol
protocol = await orchestrator.create_protocol_run(
    project_id=project.id,
    protocol_name="implement-feature",
    description="Add OAuth2 authentication"
)

# 2. Plan protocol (decompose steps)
await orchestrator.plan_protocol(protocol.id)

# 3. Execute steps (loop)
while True:
    step_run = await orchestrator.get_next_step(protocol.id)
    if not step_run:
        break

    # Execute step
    await execution_service.execute_step(step_run.id)

    # Run QA
    qa_result = await quality_service.evaluate_step(step_run.id)

    # Handle completion
    await orchestrator.handle_step_completion(
        step_run.id,
        qa_result.verdict
    )

# 4. Open PR
await git_service.push_and_open_pr(
    worktree_path,
    protocol_name,
    base_branch
)
```

### Local vs Windmill Execution

**Mode: LOCAL** (default)
- Direct execution without Windmill
- `devgodzilla step execute <step_run_id> --engine opencode`

**Mode: WINDMILL**
- Orchestrated via Windmill flows
- Windmill workers execute jobs
- Better for production scaling

### Trigger/Loop Policies

```python
# Trigger policy: enqueue follow-up work on completion
await orchestrator.apply_trigger_policy(
    step_run_id=step_run.id,
    trigger_type="on_success"
)

# Loop policy: retry failed steps
await orchestrator.apply_loop_policy(
    step_run_id=step_run.id,
    loop_count=3
)
```

---

## Appendix

### Environment Variables Reference

```bash
# Database
DEVGODZILLA_DB_URL=postgresql://user:pass@host:5432/devgodzilla_db
DEVGODZILLA_DB_PATH=.devgodzilla.sqlite

# Auth
DEVGODZILLA_API_TOKEN=your-api-token
DEVGODZILLA_JWT_SECRET=your-secret
DEVGODZILLA_ADMIN_USERNAME=admin
DEVGODZILLA_ADMIN_PASSWORD_HASH=pbkdf2_sha256$...

# Models
DEVGODZILLA_DEFAULT_ENGINE_ID=opencode
DEVGODZILLA_OPENCODE_MODEL=zai-coding-plan/glm-4.6

# Budgets
DEVGODZILLA_MAX_TOKENS_PER_STEP=100000
DEVGODZILLA_MAX_TOKENS_PER_PROTOCOL=1000000

# QA
DEVGODZILLA_AUTO_QA_ON_CI=true
DEVGODZILLA_AUTO_QA_AFTER_EXEC=true

# Windmill
DEVGODZILLA_WINDMILL_URL=http://localhost:8001
DEVGODZILLA_WINDMILL_TOKEN=windmill-token
DEVGODZILLA_WINDMILL_WORKSPACE=devgodzilla

# CORS
DEVGODZILLA_CORS_ORIGINS=*
```

### CLI Commands

```bash
# Project management
devgodzilla project create my-project --repo https://github.com/org/repo.git
devgodzilla project discover 1 --agent --engine opencode

# Protocol management
devgodzilla protocol create 1 "implement-auth"
devgodzilla protocol plan 1
devgodzilla protocol worktree 1

# Step execution
devgodzilla step execute <step_run_id> --engine opencode --model zai-coding-plan/glm-4.6
devgodzilla step qa <step_run_id>

# API server
python -m devgodzilla.api.app

# Frontend dev
cd frontend && pnpm dev
```

### Testing

```bash
# Run all tests
pytest tests/test_devgodzilla_*.py -v

# Run specific test
pytest tests/test_devgodzilla_api_protocols.py -v

# E2E tests (opt-in, real repo)
DEVGODZILLA_RUN_E2E=1 scripts/ci/test_e2e_real_repo.sh

# Frontend tests
cd frontend && pnpm test
```

### Documentation

- [DevGodzilla README](devgodzilla/README.md)
- [API Reference](docs/api-reference.md)
- [App Architecture](docs/APP_ARCHITECTURE.md)
- [Services Architecture](docs/services-architecture.md)
- [Services Dependencies](docs/services-dependencies.md)
- [Deployment Guide](DEPLOYMENT.md)
- [CI Documentation](docs/ci.md)

---

**Document Version**: 1.0
**Last Updated**: 2025-12-23
