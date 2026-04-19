# DevGodzilla API Reference

DevGodzilla provides a FastAPI-based REST API.

## Base URL

```
http://localhost:8000
```

Canonical frontend-facing versioned routes are also available under:

```
http://localhost:8000/api/v1
```

Most primary routers are mounted at both locations:

- `/api/v1/*` is the canonical API surface
- root-level routes remain available for backward compatibility

## Authentication

Authentication is partially implemented and depends on route category:

- most operational routes use `DEVGODZILLA_API_TOKEN` when configured
- webhook routes use `DEVGODZILLA_WEBHOOK_TOKEN` when configured
- JWT/session-style auth is available under `/auth/*`
- authenticated profile operations are available under `/users/me` and `/auth/me`

Current auth endpoints:

- `POST /auth/login`
- `POST /auth/refresh`
- `GET /auth/me`
- `POST /auth/logout`
- `GET /users/me`
- `PUT /users/me`
- `POST /users/me/password`

---

## Health Check

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

---

## Projects

### `POST /projects`

Create a new project.

**Request Body:**
```json
{
  "name": "my-project",
  "git_url": "https://github.com/user/repo.git",
  "base_branch": "main",
  "auto_onboard": true,
  "auto_discovery": true
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "name": "my-project",
  "git_url": "https://github.com/user/repo.git",
  "base_branch": "main",
  "created_at": "2024-01-01T00:00:00Z"
}
```

**Notes:**
- When `auto_onboard=true` (default), DevGodzilla enqueues onboarding in Windmill.
- Set `auto_discovery=false` to skip discovery during onboarding.
- Windmill must be configured (`DEVGODZILLA_WINDMILL_*`) when auto onboarding is enabled.

### `GET /projects`

List all projects.

### `GET /projects/{id}`

Get a project by ID.

### `PUT /projects/{id}`

Update a project.

### `POST /projects/{id}/actions/onboard`

Onboard a project repo for DevGodzilla workflows:
- ensure repo exists locally (clone if missing)
- checkout branch
- initialize `.specify/`
- (optional) run headless agent discovery (writes `specs/discovery/_runtime/*`)

**Request Body:**
```json
{
  "branch": "main",
  "clone_if_missing": true,
  "constitution_content": "# Optional custom constitution\n...",
  "run_discovery_agent": true,
  "discovery_pipeline": true,
  "discovery_engine_id": "opencode",
  "discovery_model": "zai-coding-plan/glm-5"
}
```

**Response:**
```json
{
  "success": true,
  "project": { "id": 1, "name": "my-project", "git_url": "https://...", "base_branch": "main" },
  "local_path": "/abs/path/to/repo",
  "speckit_initialized": true,
  "speckit_path": "/abs/path/to/repo/.specify",
  "constitution_hash": "abc123",
  "warnings": [],
  "discovery_success": true,
  "discovery_log_path": "/abs/path/to/repo/specs/discovery/_runtime/opencode-discovery.log",
  "discovery_missing_outputs": [],
  "discovery_error": null,
  "error": null
}
```

---

## SpecKit

### `POST /speckit/init`

Initialize SpecKit for a project.

**Request Body:**
```json
{
  "project_id": 1,
  "constitution_content": "# My Constitution\n..."
}
```

**Response:**
```json
{
  "success": true,
  "path": "/path/to/.specify",
  "constitution_hash": "abc123...",
  "warnings": []
}
```

### `GET /speckit/constitution/{project_id}`

Get project constitution.

**Response:**
```json
{
  "content": "# Project Constitution\n..."
}
```

### `PUT /speckit/constitution/{project_id}`

Update project constitution.

**Request Body:**
```json
{
  "content": "# Updated Constitution\n..."
}
```

### `POST /speckit/specify`

Generate a feature specification.

Execution model:

- tries to complete synchronously first
- if it does not finish inside the current synchronous window, the API returns `202 Accepted` and continues in background
- the current synchronous window for `specify` is 15 seconds
- failed generation attempts now persist the related `SpecRun` as `failed`

**Request Body:**
```json
{
  "project_id": 1,
  "description": "Add user authentication with OAuth2",
  "feature_name": "auth-oauth2"
}
```

**Response:**
```json
{
  "success": true,
  "spec_path": "specs/001-auth-oauth2/spec.md",
  "spec_number": 1,
  "feature_name": "auth-oauth2",
  "spec_run_id": 42,
  "worktree_path": "/abs/path/to/worktree",
  "branch_name": "001-auth-oauth2"
}
```

**Deferred Response (`202 Accepted`):**
```json
{
  "spec_run_id": null,
  "status": "specifying",
  "message": "Specification generation deferred to background.",
  "poll_url": null
}
```

### `POST /speckit/plan`

Generate an implementation plan.

Execution model:

- tries synchronous execution first
- may return `202 Accepted` for slow AI-backed runs and continue in background

**Request Body:**
```json
{
  "project_id": 1,
  "spec_path": "specs/001-auth/spec.md"
}
```

**Response:**
```json
{
  "success": true,
  "plan_path": "specs/001-auth/plan.md",
  "data_model_path": "specs/001-auth/data-model.md",
  "contracts_path": "specs/001-auth/contracts",
  "spec_run_id": 42
}
```

**Deferred Response (`202 Accepted`):**
```json
{
  "spec_run_id": 42,
  "status": "planning",
  "message": "Plan generation deferred to background.",
  "poll_url": null
}
```

### `POST /speckit/tasks`

Generate a task list.

Execution model:

- tries synchronous execution first
- may return `202 Accepted` for slow AI-backed runs and continue in background

**Request Body:**
```json
{
  "project_id": 1,
  "plan_path": "specs/001-auth/plan.md"
}
```

**Response:**
```json
{
  "success": true,
  "tasks_path": "specs/001-auth/tasks.md",
  "task_count": 12,
  "parallelizable_count": 5,
  "spec_run_id": 42
}
```

### `GET /speckit/specs/{project_id}`

List all specs in a project.

### `GET /speckit/status/{project_id}`

Get SpecKit status for a project.

### `POST /speckit/spec-runs/{spec_run_id}/stop`

Force a stuck SpecRun into `stopped` so cleanup can proceed.

### `POST /speckit/spec-runs/{spec_run_id}/cleanup`

Clean up worktree state and optional remote branch state for a SpecRun.

---

## Protocols

### `POST /protocols`

Create a new protocol run.

**Request Body:**
```json
{
  "project_id": 1,
  "name": "implement-auth",
  "description": "Add OAuth2 authentication"
}
```

### `GET /protocols`

List protocol runs.

**Query Parameters:**
- `project_id` - Filter by project
- `status` - Filter by status
- `limit` - Max results

### `GET /protocols/{id}`

Get a protocol by ID.

### `POST /protocols/{id}/actions/start`

Start planning for a protocol run (async background task).

Notes:
- Planning is **protocol-file driven**: it reads `.protocols/<protocol_name>/step-*.md` in the protocol worktree.
- If protocol files are missing and `DEVGODZILLA_AUTO_GENERATE_PROTOCOL` is enabled (default `true`), DevGodzilla runs a headless agent to generate:
  - `.protocols/<protocol_name>/plan.md`
  - `.protocols/<protocol_name>/step-*.md`
- Planning also ensures a git worktree exists for isolation and persists `worktree_path` on the protocol run.

### `POST /protocols/{id}/actions/run_next_step`

Select the next runnable step for a protocol (selection-only; does not execute).

**Response:**
```json
{ "step_run_id": 123 }
```

When there is no runnable step (blocked/completed), it returns:
```json
{ "step_run_id": null }
```

### `POST /protocols/{id}/actions/pause`

Pause a protocol run.

### `POST /protocols/{id}/actions/resume`

Resume a paused protocol.

### `POST /protocols/{id}/actions/cancel`

Cancel a protocol run.

---

## Steps

### `GET /steps`

List steps for a protocol.

**Query Parameters:**
- `protocol_id` - Filter by protocol
- `status` - Filter by status

### `GET /steps/{id}`

Get a step by ID.

### `POST /steps/{id}/actions/execute`

Execute a step.

### `POST /steps/{id}/actions/qa`

Run QA on a step.

**Request Body:**
```json
{
  "gates": ["test", "lint", "type"]
}
```

Notes:
- Omit `gates` (or set it to `null`) to run the default QA gate set.
- `gates` selects additional deterministic gates (lint/type/test); prompt-driven QA always runs.

### `POST /steps/{id}/actions/assign_agent`

Assign a specific engine/agent to a step.

**Request Body:**
```json
{ "agent_id": "opencode" }
```

### `GET /steps/{id}/quality`

Return a lightweight quality summary derived from the persisted QA verdict.

### `GET /steps/{id}/artifacts`

List step artifacts stored under `.protocols/<protocol_name>/.devgodzilla/steps/<step_run_id>/artifacts/*`.

### `GET /steps/{id}/artifacts/{artifact_id}/content`

Fetch artifact content for preview (truncates large files).

### `GET /steps/{id}/artifacts/{artifact_id}/download`

Download an artifact as a file.

---

## Agents

### `GET /agents`

List available AI agents.

**Response:**
```json
[
  {
    "id": "codex",
    "name": "OpenAI Codex",
    "status": "available",
    "capabilities": ["code_gen", "sandbox"]
  },
  {
    "id": "claude-code",
    "name": "Claude Code",
    "status": "available",
    "capabilities": ["code_gen", "review"]
  }
]
```

### `GET /agents/{id}`

Get agent details.

### `POST /agents/{id}/health`

Check agent health.

---

## Clarifications

### `GET /clarifications`

List clarifications.

**Query Parameters:**
- `project_id` - Filter by project
- `protocol_id` - Filter by protocol
- `status` - Filter by status (open, answered)

### `POST /clarifications/{id}/answer`

Answer a clarification.

**Request Body:**
```json
{
  "answer": "Use PostgreSQL for the database"
}
```

---

## OpenAPI Documentation

Interactive API documentation is available at:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`
