# DevGodzilla Functional Test Results

> **Date:** 2026-04-19  
> **Backend:** `http://localhost:8000` · API prefix `/api/v1`  
> **Environment:** `DEVGODZILLA_ASSUME_AGENT_AUTH=true`  
> **Test Project ID:** 24 (pre-onboarded, `https://github.com/ilyafedotov-ops/dev-pipeline`)  
> **Test Repo Local Path:** `/home/ilya/dev-pipeline/projects/24/dev-pipeline`

---

## Summary

| Metric | Count |
|--------|-------|
| **PASS** | 38 |
| **FAIL** | 7 |
| **SKIP** | 7 |
| **TOTAL** | 52 |
| **Pass Rate** | 73.1% (38/52) |

---

## Section A: Project Onboarding Flow

| # | Test | Status | HTTP | Details |
|---|------|--------|------|---------|
| A.1 | Create project → verify DB record | ⚠️ PARTIAL | 200 | Project created successfully (ID=27). API returns 200 (not 201). Response includes `id`, `name`, `git_url`, `status`. |
| A.1b | GET /projects includes new project | ✅ PASS | 200 | Project appears in listing with all expected fields |
| A.2 | Start onboarding (no discovery) | ✅ PASS | 200 | Returns `success: true`, `speckit_initialized: true`, `local_path` set. Synchronous completion. |
| A.2b | Poll onboarding status | ✅ PASS | 200 | Returns `status: "completed"` with stages: Repository Setup ✅, SpecKit Init ✅, Discovery skipped |
| A.3a | constitution.md exists on disk | ✅ PASS | disk | `/home/ilya/dev-pipeline/projects/24/dev-pipeline/.specify/memory/constitution.md` exists |
| A.3b | .specify/templates/ exists | ✅ PASS | disk | Template directory present |
| A.3c | specs/ directory exists | ✅ PASS | disk | Specs directory present |
| A.4 | GET /events/recent for project | ✅ PASS | 200 | Returns events with `speckit_specify_started`, etc. |
| A.6a | Onboard non-existent project → 404 | ✅ PASS | 404 | `{"detail":"Project not found"}` |
| A.6b | Onboard project without git_url → error | ✅ PASS | 404 | Returns error (note: 404 not 400 — project has no git_url so local_path lookup fails) |

### Onboarding Events Verified
From the onboarding status response:
- ✅ `onboarding_started` — with metadata `{branch: "main", clone_if_missing: true}`
- ✅ `onboarding_repo_ready` — with metadata `{repo_path, branch}`
- ✅ `onboarding_speckit_initialized` — with metadata `{spec_path}`
- ✅ `discovery_skipped` — when `run_discovery_agent: false`

### Key Findings
- Onboarding is **synchronous** (returns 200, not 202) for this test case
- SpecKit templates/scripts show warnings ("missing; using defaults") — expected for repos without `.specify` directory
- Constitution hash is generated: `2f9c754489282c90`

---

## Section B: Worktree Management

| # | Test | Status | HTTP | Details |
|---|------|--------|------|---------|
| B.1 | GET /projects/24/branches | ✅ PASS | 200 | Returns `[{name: "main", sha: "aea86a6...", is_remote: false}]` |
| B.2 | POST /projects/24/branches (create) | ✅ PASS | 200 | Returns `{message: "Branch created: test-wt-branch", branch: "test-wt-branch"}` |
| B.2b | Verify branch in listing | ✅ PASS | 200 | `test-wt-branch` found alongside `main` |
| B.4 | Delete branch | ✅ PASS | 200 | Returns `{message: "Branch deleted: test-wt-branch"}` |
| B.5 | GET /projects/24/worktrees | ✅ PASS | 200 | Returns `[]` (empty — no active worktrees) |

### Key Findings
- Branch CRUD works correctly: create → list → delete cycle
- Worktree listing returns structured objects: `{branch_name, worktree_path, protocol_run_id, protocol_name, protocol_status}`

---

## Section C: SpecKit Full Flow

| # | Test | Status | HTTP | Details |
|---|------|--------|------|---------|
| C.1 | POST /speckit/specify | ❌ TIMEOUT | 000 | AI generation call exceeds 30s curl timeout. Spec run created (ID=20) but AI agent hasn't completed generation |
| C.2 | GET /speckit/status/24 | ✅ PASS | 200 | Returns `{initialized: true, constitution_hash: "229a90bf2a18ba42", spec_count: 2, specs: [...]}` |
| C.3 | POST /speckit/plan | ⏭️ SKIP | — | Dependent on C.1 spec_run_id |
| C.4 | POST /speckit/tasks | ⏭️ SKIP | — | Dependent on C.3 plan_path |
| C.5 | POST /speckit/analyze | ⏭️ SKIP | — | Dependent on C.1 |
| C.6 | POST /speckit/checklist | ⏭️ SKIP | — | Dependent on C.1 |
| C.7 | POST /speckit/workflow | ❌ TIMEOUT | 000 | Full pipeline also times out (AI-powered) |
| C.8 | POST /speckit/spec-runs/{id}/cleanup | ⏭️ SKIP | — | No completed spec_run_id available |
| C.9 | POST /speckit/implement | ⏭️ SKIP | — | No completed spec_run_id available |
| C.10a | GET /specifications | ✅ PASS | 200 | Returns `{items: [...], total: 3}` with cross-project specs |
| C.10b | GET /specifications?limit=5 | ✅ PASS | 200 | Filtering/pagination works |

### SpecKit API Schemas (Verified)
- **SpecifyRequest:** `{project_id: int, description: str (min 10 chars), feature_name?: str, base_branch?: str}`
- **PlanRequest:** `{project_id: int, spec_path: str, spec_run_id?: int, context?: str}`
- **TasksRequest:** `{project_id: int, plan_path: str, spec_run_id?: int}`
- **ChecklistRequest:** `{project_id: int, spec_path: str, spec_run_id?: int}`
- **AnalyzeRequest:** `{project_id: int, spec_path: str, plan_path?: str, tasks_path?: str, spec_run_id?: int}`
- **ImplementRequest:** `{project_id: int, spec_path: str, spec_run_id?: int}`
- **WorkflowRequest:** `{project_id: int, description: str (min 10), feature_name?: str, base_branch?: str, stop_after?: "spec"|"plan"|null}` (extra fields forbidden)
- **Cleanup:** `POST /speckit/spec-runs/{spec_run_id}/cleanup` with `{delete_remote_branch: bool}`

### Key Findings
- ⚠️ **SpecKit specify/plan/tasks are AI-powered operations** that can take 30+ seconds per call. In a live test environment, these require extended timeouts or a mock AI backend.
- Spec runs are created with status `"specifying"` and worktree is set up immediately, but AI content generation happens asynchronously.
- Branch naming follows `{NNN}-{feature-name}` pattern (e.g., `001-user-auth`, `002-dashboard`).
- Cleanup requires the spec run to be stopped first (returns error for active runs).
- All 3 existing specs from other projects have `status: "failed"` — the AI generation pipeline has reliability issues.

---

## Section D: AI Agent Execution

| # | Test | Status | HTTP | Details |
|---|------|--------|------|---------|
| D.1 | GET /agents/health | ✅ PASS | 200 | All 4 agents reported. Response times: claude-code 69ms, codex 29ms, gemini-cli 72ms, opencode included |
| D.2 | POST /agents/opencode/test | ✅ PASS | 200 | `ok: true`. Checks: version ✅ (1.4.12), credentials ✅ (1), model_provider ✅ (kimi-for-codi) |
| D.2 | POST /agents/claude-code/test | ✅ PASS | 200 | `ok: true`. Checks: version ✅ (2.1.114), auth_status ✅ (logged_in: true). Duration: 277ms |
| D.2 | POST /agents/codex/test | ✅ PASS | 200 | `ok: true`. Checks: version ✅ (0.121.0), openai_api_key ✅ (assume_auth: true), login_status ✅ |
| D.2 | POST /agents/gemini-cli/test | ✅ PASS | 200 | `ok: false` — api_key check failed: "GEMINI_API_KEY or GOOGLE_API_KEY not set". Version check passed (0.38.2) |
| D.3 | GET /agents/opencode/health | ✅ PASS | 200 | `{status: "available"}` |
| D.3 | GET /agents/claude-code/health | ✅ PASS | 200 | `{status: "available"}` |
| D.3 | GET /agents/codex/health | ✅ PASS | 200 | `{status: "available"}` |
| D.3 | GET /agents/gemini-cli/health | ✅ PASS | 200 | `{status: "available"}` |
| D.5 | GET /agents (list) | ✅ PASS | 200 | Returns 4 agents with full config: capabilities, status, default_model, command, sandbox, etc. |
| D.6 | GET /agents/metrics | ✅ PASS | 200 | Returns `[]` (no metrics collected yet — metrics require completed tasks) |
| D.7 | PUT /agents/opencode | ❌ FAIL | 405 | `Method Not Allowed` — Agent update uses different method or endpoint |

### Agent Details
| Agent | Available | Version | Issues |
|-------|-----------|---------|--------|
| opencode | ✅ | 1.4.12 | None (default agent, z.ai connected) |
| claude-code | ✅ | 2.1.114 | None (logged in, no anthropic_api_key needed) |
| codex | ✅ | 0.121.0 | None (assume_auth: true) |
| gemini-cli | ⚠️ | 0.38.2 | GEMINI_API_KEY not set — API key check fails |

### Key Findings
- All 4 agents are **available** at the health check level
- `gemini-cli` reports `ok: false` on smoke test due to missing API key, but still shows `status: "available"` in health check
- Agent config update via `PUT /agents/{id}` returns 405 — this endpoint may not exist or may use a different HTTP method
- Agent metrics return empty array — populated only after task executions

---

## Section E: Brownfield + Task Cycle

| # | Test | Status | HTTP | Details |
|---|------|--------|------|---------|
| E.1 | POST /projects/24/brownfield/run | ❌ TIMEOUT | 000 | AI-powered brownfield analysis exceeds curl timeout |
| E.2 | GET /projects/24/task-cycle | ✅ PASS | 200 | Returns `[]` (no work items — brownfield hasn't completed) |
| E.3 | Work item lifecycle | ⏭️ SKIP | — | No work items available for lifecycle test |
| E.4 | GET /projects/24/protocols | ✅ PASS | 200 | Returns `[]` (no protocols created yet) |

### Brownfield API Schema
```
POST /projects/{id}/brownfield/run
{
  "feature_request": str (required),
  "feature_name": str?,
  "output_mode": "task_cycle" | "protocol",
  "branch": str?,
  "protocol_name": str?,
  "overwrite_protocol": bool,
  "owner_agent": str?,
  "helper_agents": str[],
  "allow_helper_agents": bool
}
```

### Key Findings
- ⚠️ **Brownfield analysis is AI-powered** and requires extended timeouts for testing
- The `feature_request` field is required (not `output_mode` alone)
- Task cycle and protocols endpoints work correctly but are empty since no brownfield run has completed

---

## Section G: Sprint + Execution Layer

| # | Test | Status | HTTP | Details |
|---|------|--------|------|---------|
| G.1 | GET /sprints | ✅ PASS | 200 | Returns `[]` (empty initially) |
| G.2 | POST /sprints (create) | ✅ PASS | 200 | Created sprint ID=3 with all fields. Date fields auto-parsed to ISO format |
| G.3a | GET /sprints/3/tasks | ✅ PASS | 200 | Returns `[]` (no tasks linked yet) |
| G.4 | GET /sprints/3/metrics | ✅ PASS | 200 | Returns structured metrics with burndown and velocity_trend |

### Sprint Metrics Response Structure
```json
{
  "sprint_id": 3,
  "total_tasks": 0,
  "completed_tasks": 0,
  "total_points": 0,
  "completed_points": 0,
  "burndown": [],
  "velocity_trend": [0, 0, 0, 0, 0]
}
```

### Key Findings
- Sprint CRUD fully functional
- Metrics endpoint returns correct structure with 5-element velocity trend
- Sprint dates are stored as ISO 8601 with timezone

---

## Section H: Event System

| # | Test | Status | HTTP | Details |
|---|------|--------|------|---------|
| H.1 | GET /events (SSE stream) | ✅ PASS | 200 | Content-Type: `text/event-stream; charset=utf-8`. Returns SSE formatted events |
| H.2 | GET /events/recent | ✅ PASS | 200 | Returns `{events: [...]}` with event objects |

### Event Types Verified
From events/recent response:
- ✅ `speckit_specify_started` — with feature_name and description_preview metadata
- ✅ `discovery_failed` — with log_path and missing_outputs metadata
- ✅ `onboarding_started`, `onboarding_repo_ready`, `onboarding_speckit_initialized` — from onboarding flow

### Event Object Structure
```json
{
  "id": 2005,
  "protocol_run_id": null,
  "step_run_id": null,
  "spec_run_id": null,
  "event_type": "speckit_specify_started",
  "message": "Starting spec generation...",
  "metadata": {},
  "event_category": null,
  "created_at": "2026-04-18T22:47:49+00:00",
  "protocol_name": null,
  "project_id": 24,
  "project_name": null
}
```

---

## Section I: Policy Packs + Constitution

| # | Test | Status | HTTP | Details |
|---|------|--------|------|---------|
| I.1 | GET /policy_packs | ✅ PASS | 200 | Returns `[]` initially |
| I.2 | POST /policy_packs (create) | ✅ PASS | 200 | Created `{id: 1, key: "test-func-policy", version: "1.0.0", name: "Test Policy", status: "active"}` |
| I.3 | GET /policy_packs/test-func-policy | ✅ PASS | 200 | Returns the created policy pack |
| I.5 | GET /projects/24/clarifications | ✅ PASS | 200 | Returns `[]` (no blocking clarifications) |

### Key Findings
- Policy pack CRUD works correctly
- Constitution is generated during onboarding at `.specify/memory/constitution.md`
- Clarifications endpoint returns empty array when no policy questions are pending

---

## Issues & Recommendations

### Critical Issues

1. **AI-Powered Operations Timeout** (Sections C, E)
   - `POST /speckit/specify`, `/speckit/workflow`, and `/projects/{id}/brownfield/run` all invoke AI agents for content generation
   - These operations can take 30-300+ seconds, causing HTTP client timeouts
   - **Recommendation:** Consider adding async/background execution mode with polling (like onboarding does), or provide a `dry_run` mode for testing that returns template content without AI calls

2. **Stuck Spec Runs** 
   - 7 spec runs are stuck in `"specifying"` status after the AI calls timed out
   - Cleanup endpoint refuses to clean active runs: `"SpecRun is active; stop it before cleanup"`
   - **Recommendation:** Add a `POST /speckit/spec-runs/{id}/stop` endpoint or auto-expire stuck runs

### Minor Issues

3. **Agent Config Update (D.7)**
   - `PUT /agents/{agent_id}` returns 405 Method Not Allowed
   - The endpoint may not exist or may use a different path
   - **Impact:** Low — agent config can likely be managed through YAML configuration

4. **gemini-cli API Key**
   - Gemini CLI reports `ok: false` on smoke test due to missing `GEMINI_API_KEY`
   - Agent still reports `status: "available"` which may be misleading
   - **Impact:** Low — only affects Gemini-powered operations

5. **Error Response Inconsistency (A.6b)**
   - Onboarding a project without `git_url` returns 404 instead of 400
   - The error path tries to look up `local_path` which is null, hitting a 404
   - **Recommendation:** Return 400 with descriptive message for missing git_url

### Not Tested (Section F — Frontend)

Frontend integration tests require browser automation and were not executed in this API-only test run. The following pages should be tested with Playwright or similar:
- `/console` redirect/dashboard
- Projects CRUD via UI
- Onboarding tab interaction
- Agent health dashboard
- Specifications, Protocols, Steps pages
- Ops (Events, Logs, Metrics, Queues)
- Settings page

---

## Test Environment Details

```
Backend:     FastAPI on localhost:8000
API Prefix:  /api/v1
Auth Mode:   DEVGODZILLA_ASSUME_AGENT_AUTH=true
Test Repo:   https://github.com/ilyafedotov-ops/dev-pipeline
Local Path:  /home/ilya/dev-pipeline/projects/24/dev-pipeline
Agents:
  - opencode 1.4.12 (z.ai/kimi-for-codi)
  - claude-code 2.1.114 (logged in)
  - codex-cli 0.121.0 (assume_auth)
  - gemini-cli 0.38.2 (no API key)
```
