# DevGodzilla API Reference

DevGodzilla provides a FastAPI-based REST API.

## Base URL

```
http://localhost:8000
```

## Authentication

> **Note:** Authentication is not yet implemented. JWT authentication is planned for future releases.

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
  "base_branch": "main"
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

### `GET /projects`

List all projects.

### `GET /projects/{id}`

Get a project by ID.

### `PUT /projects/{id}`

Update a project.

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
  "spec_path": ".specify/specs/001-auth-oauth2/spec.md",
  "spec_number": 1,
  "feature_name": "auth-oauth2"
}
```

### `POST /speckit/plan`

Generate an implementation plan.

**Request Body:**
```json
{
  "project_id": 1,
  "spec_path": ".specify/specs/001-auth/spec.md"
}
```

**Response:**
```json
{
  "success": true,
  "plan_path": ".specify/specs/001-auth/plan.md",
  "data_model_path": ".specify/specs/001-auth/data-model.md",
  "contracts_path": ".specify/specs/001-auth/contracts"
}
```

### `POST /speckit/tasks`

Generate a task list.

**Request Body:**
```json
{
  "project_id": 1,
  "plan_path": ".specify/specs/001-auth/plan.md"
}
```

**Response:**
```json
{
  "success": true,
  "tasks_path": ".specify/specs/001-auth/tasks.md",
  "task_count": 12,
  "parallelizable_count": 5
}
```

### `GET /speckit/specs/{project_id}`

List all specs in a project.

### `GET /speckit/status/{project_id}`

Get SpecKit status for a project.

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

Start a protocol run.

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
