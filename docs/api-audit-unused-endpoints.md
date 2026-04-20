# API Audit: Backend Endpoints Without Frontend Consumers

**Generated:** 2026-04-20  
**Scope:** `devgodzilla/api/routes/*.py` (28 router files) vs `frontend/` (hooks, pages, components)

## Summary

| Category | Count |
|----------|-------|
| Total backend endpoints (excl. webhooks/health) | ~110 |
| Endpoints consumed by frontend | ~85 |
| **Endpoints with NO frontend consumer** | **~25** |
| Of those: user-facing features invisible to users | **~15** |

---

## Endpoints With NO Frontend Consumer — User-Facing Features

These endpoints are fully implemented in the backend but the frontend doesn't expose them. Users cannot access these features through the UI.

### 1. Authentication & User Management

| # | Method | Path | File | What It Does | Frontend Benefit |
|---|--------|------|------|--------------|------------------|
| 1 | `POST` | `/auth/refresh` | `auth.py:170` | Refresh JWT tokens | **HIGH** — No silent token refresh; users get kicked out on expiry |
| 2 | `PUT` | `/users/me` | `users.py:77` | Update user profile (name, email) | **MEDIUM** — Profile page exists but has no edit form |
| 3 | `POST` | `/users/me/password` | `users.py:103` | Change password | **MEDIUM** — No password change UI; security risk if users can't rotate |

### 2. Protocol Operations

| # | Method | Path | File | What It Does | Frontend Benefit |
|---|--------|------|------|--------------|------------------|
| 4 | `GET` | `/protocols/{id}/next-step` | `protocols.py:596` | Preview what the next step would be without executing | **MEDIUM** — Could show "Up Next" preview before user clicks "Run Next Step" |
| 5 | `POST` | `/protocols` | `protocols.py:181` | Create a protocol without associating to a project | **LOW** — Frontend always creates via `/projects/{id}/protocols` |
| 6 | `POST` | `/protocols/from-spec` | `protocols.py:211` | Create protocol from a specification | **LOW** — Hook exists (`useCreateProtocolFromSpec`) but no page uses it |

### 3. Agent Management

| # | Method | Path | File | What It Does | Frontend Benefit |
|---|--------|------|------|--------------|------------------|
| 7 | `GET` | `/agents/projects/{project_id}` | `agents.py:468` | Get all agent config overrides for a project (bulk) | **MEDIUM** — Could power a "Project Agent Settings" overview page |
| 8 | `PUT` | `/agents/projects/{project_id}` | `agents.py:488` | Bulk update all agent overrides for a project | **MEDIUM** — Could enable bulk agent config per project |
| 9 | `PUT` | `/agents/{agent_id}` | `agents.py:571` | Full agent update (enables model, capabilities, etc.) | **LOW** — Frontend uses `/agents/{id}/config` instead; this is a superset |

### 4. Task Management

| # | Method | Path | File | What It Does | Frontend Benefit |
|---|--------|------|------|--------------|------------------|
| 10 | `PUT` | `/tasks/{task_id}` | `tasks.py:93` | Full task update (replace) | **MEDIUM** — Frontend only uses PATCH; full PUT could support task restructuring |
| 11 | `POST` | `/tasks` | `tasks.py:11` | Create standalone task | **LOW** — Frontend creates tasks via sprint import only |

### 5. SpecKit / Specification

| # | Method | Path | File | What It Does | Frontend Benefit |
|---|--------|------|------|--------------|------------------|
| 12 | `POST` | `/speckit/constitution/{project_id}/sync` | `speckit.py:288` | Sync constitution from file system to DB | **MEDIUM** — Could add a "Sync from disk" button on constitution page |
| 13 | `POST` | `/speckit/implement` | `speckit.py:732` | Run implementation via top-level speckit endpoint (non-project) | **LOW** — Frontend uses `/projects/{id}/speckit/implement` instead |
| 14 | `POST` | `/speckit/spec-runs/{id}/stop` | `speckit.py:822` | Stop a running spec run | **HIGH** — No way to cancel a long-running speckit operation from UI |
| 15 | `GET` | `/speckit/status/{project_id}` | `speckit.py:764` | Get speckit pipeline status | **LOW** — Already used via hook but useful for status polling |

### 6. CLI Executions

| # | Method | Path | File | What It Does | Frontend Benefit |
|---|--------|------|------|--------------|------------------|
| 16 | `POST` | `/cli-executions/{id}/cancel` | `cli_executions.py:287` | Cancel a running CLI execution | **HIGH** — Executions page shows running tasks but has no cancel button |

### 7. Policy Packs

| # | Method | Path | File | What It Does | Frontend Benefit |
|---|--------|------|------|--------------|------------------|
| 17 | `GET` | `/policy_packs/{key}/{version}` | `policy_packs.py:44` | Get a specific version of a policy pack | **MEDIUM** — Policy pack detail page exists but only shows latest version |

### 8. Metrics

| # | Method | Path | File | What It Does | Frontend Benefit |
|---|--------|------|------|--------------|------------------|
| 18 | `GET` | `/metrics` | `metrics.py:295` | Raw Prometheus-style metrics endpoint | **LOW** — Internal/ops use; not needed in UI |

### 9. Projects

| # | Method | Path | File | What It Does | Frontend Benefit |
|---|--------|------|------|--------------|------------------|
| 19 | `GET` | `/projects/{id}/constitution` | `projects.py:1507` | Get project constitution (non-speckit route) | **LOW** — Frontend uses `/projects/{id}/speckit/constitution` instead |

### 10. Steps

| # | Method | Path | File | What It Does | Frontend Benefit |
|---|--------|------|------|--------------|------------------|
| 20 | `GET` | `/steps/{id}/artifacts/{id}/download` | `steps.py:492` | Download step artifact as binary file | **LOW** — Frontend has `useStepArtifactDownloadUrl` but may not have download button |

### 11. Events

| # | Method | Path | File | What It Does | Frontend Benefit |
|---|--------|------|------|--------------|------------------|
| 21 | `GET` | `/events` | `events.py:122` | Paginated event listing with cursor | **LOW** — Frontend uses `/events/recent` and SSE stream instead |
| 22 | `GET` | `/events/stream` | `events.py:162` | SSE event stream | **LOW** — Frontend uses WebSocket `/ws/events` instead |

### 12. Webhooks (Not Applicable — Server-to-Server)

These are not user-facing endpoints; they receive webhooks from external systems:

| # | Method | Path | File | Notes |
|---|--------|------|------|-------|
| 23 | `POST` | `/webhooks/windmill/job` | `webhooks.py:242` | Windmill job callback |
| 24 | `POST` | `/webhooks/windmill/flow` | `webhooks.py:295` | Windmill flow callback |
| 25 | `POST` | `/webhooks/github` | `webhooks.py:334` | GitHub webhook |
| 26 | `POST` | `/webhooks/gitlab` | `webhooks.py:530` | GitLab webhook |

### 13. Health & Infrastructure (Not User-Facing)

| # | Method | Path | File | Notes |
|---|--------|------|------|-------|
| 27 | `GET` | `/health` | `app.py:268` | Used by frontend ops dashboard ✓ |
| 28 | `GET` | `/health/live` | `app.py:274` | K8s liveness probe — not UI |
| 29 | `GET` | `/health/ready` | `app.py:280` | K8s readiness probe — not UI |
| 30 | `GET` | `/health/agents` | `app.py:320` | Agent health detail — not used in UI |

---

## High-Priority Gaps (User Features Users Would Benefit From)

### 🔴 HIGH: Token Refresh — Silent Session Expiry
- **Backend:** `POST /auth/refresh` 
- **Impact:** Users are logged out when JWT expires with no automatic refresh
- **Recommendation:** Add interceptors in `apiClient` to call `/auth/refresh` on 401

### 🔴 HIGH: Cancel CLI Execution
- **Backend:** `POST /cli-executions/{id}/cancel`
- **Impact:** Users see running executions but can't stop them
- **Recommendation:** Add cancel button to executions list/detail page

### 🔴 HIGH: Stop Running SpecKit Operation
- **Backend:** `POST /speckit/spec-runs/{id}/stop`
- **Impact:** Long-running spec operations can't be cancelled from UI
- **Recommendation:** Add stop button on speckit wizard during execution

### 🟡 MEDIUM: Password Change
- **Backend:** `POST /users/me/password`
- **Impact:** No way to change password from the console
- **Recommendation:** Add password change section to Profile/Settings page

### 🟡 MEDIUM: Profile Editing
- **Backend:** `PUT /users/me`
- **Impact:** Name and email can't be updated from the console
- **Recommendation:** Add edit form to Profile page

### 🟡 MEDIUM: Next Step Preview
- **Backend:** `GET /protocols/{id}/next-step`
- **Impact:** Users can't preview what the next step will be before triggering it
- **Recommendation:** Add "Preview Next Step" button/tooltip on protocol detail page

### 🟡 MEDIUM: Policy Pack Version History
- **Backend:** `GET /policy_packs/{key}/{version}`
- **Impact:** Can only see the latest version of a policy pack
- **Recommendation:** Add version selector/history to policy pack detail page

### 🟡 MEDIUM: Constitution Sync from Disk
- **Backend:** `POST /projects/{id}/speckit/constitution/sync` and `POST /speckit/constitution/{project_id}/sync`
- **Impact:** No way to sync constitution changes from filesystem into the system
- **Recommendation:** Add "Sync from disk" button on constitution editor

### 🟡 MEDIUM: Bulk Agent Project Configuration
- **Backend:** `GET/PUT /agents/projects/{project_id}` (AgentProjectOverrides)
- **Impact:** Project-level agent overrides exist but can't be managed as a group
- **Recommendation:** Add project-level agent settings page/tab

---

## Infrastructure Endpoints Not Used in Frontend (Low Priority)

| Endpoint | Reason |
|----------|--------|
| `GET /metrics` | Prometheus scraping, not UI |
| `GET /events` | Frontend uses `/events/recent` + WebSocket |
| `GET /events/stream` | Frontend uses WebSocket instead |
| `GET /health/live` | K8s probe |
| `GET /health/ready` | K8s probe |
| `GET /health/agents` | Could be shown on ops page but not critical |
| `POST /protocols` (no project) | Frontend always uses project-scoped creation |
| `PUT /agents/{agent_id}` (non-config) | Superseded by `/agents/{id}/config` |
| `POST /tasks` (standalone) | Tasks always created via sprints |
| `PUT /tasks/{id}` | Frontend uses PATCH for partial updates |
| `GET /projects/{id}/constitution` | Frontend uses speckit constitution endpoint |
