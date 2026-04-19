# DevGodzilla / dev-pipeline — Comprehensive Testing Plan

> **Version:** 1.0  
> **Last updated:** 2026-04-19  
> **Backend:** `localhost:8000` · API prefix `/api/v1`  
> **Frontend:** `localhost:3000` · basePath `/console`

---

## Table of Contents

1. [A. Project Onboarding Flow](#a-project-onboarding-flow)
2. [B. Worktree Management](#b-worktree-management)
3. [C. SpecKit Full Flow](#c-speckit-full-flow)
4. [D. AI Agent Execution](#d-ai-agent-execution)
5. [E. Brownfield + Task Cycle](#e-brownfield--task-cycle)
6. [F. Frontend Integration](#f-frontend-integration)
7. [G. Sprint + Execution Layer](#g-sprint--execution-layer)
8. [H. Event System](#h-event-system)
9. [I. Policy Packs + Constitution](#i-policy-packs--constitution)

---

## A. Project Onboarding Flow

### A.1 Create Project → Verify DB Record

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /api/v1/projects` |
| **Payload** | `{"name": "test-project", "git_url": "https://github.com/ilyafedotov-ops/dev-pipeline", "base_branch": "main"}` |
| **Expected** | `201` or `200` with JSON body containing `id`, `name`, `git_url`, `status` |
| **Verify** | Response body has `id` (int); `GET /api/v1/projects` subsequently lists the project |

### A.2 Start Onboarding → Verify 202 Accepted → Poll Until Complete

|| Item | Detail |
|------|--------|
| **Precondition** | Project must have `git_url` set (non-null, valid URL) |
| **Endpoint** | `POST /api/v1/projects/{id}/actions/onboard` |
| **Payload** | `{}` (empty body, defaults: `clone_if_missing=true`, `run_discovery_agent=false`) |
| **Expected** | `200` (synchronous completion with `ProjectOnboardResponse`) **or** `202 Accepted` (deferred to background) |
| **Verify** | If `200`: body has `success: true`, `speckit_initialized: true`, `local_path` set. If `202`: poll `GET /api/v1/projects/{id}/onboarding` until `status == "completed"` |

### A.3 Verify Files Created on Disk

| Item | Detail |
|------|--------|
| **Precondition** | Project successfully onboarded (A.2) |
| **Check** | `{local_path}/.specify/memory/constitution.md` exists |
| **Check** | `{local_path}/.specify/templates/` directory exists with at least one `.md` file |
| **Check** | `{local_path}/specs/` directory exists |
| **Verify** | Files are non-empty; constitution.md contains valid markdown |

### A.4 Verify Onboarding Events

| Item | Detail |
|------|--------|
| **Endpoint** | `GET /api/v1/events/recent?project_id={id}&limit=20` |
| **Expected** | Events with types: `onboarding_started`, `onboarding_repo_ready`, `onboarding_speckit_initialized`, `onboarding_completed` |
| **Verify** | Each event type present; events ordered chronologically |

### A.5 Verify Discovery Agent Execution (if enabled)

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /api/v1/projects/{id}/actions/onboard` |
| **Payload** | `{"run_discovery_agent": true, "discovery_pipeline": true}` |
| **Expected** | `discovery_completed` or `discovery_failed` or `discovery_skipped` event emitted |
| **Verify** | Event type matches; log path present if completed |

### A.6 Error Cases

| Case | Detail |
|------|--------|
| **Invalid repo URL** | `POST /api/v1/projects` with `git_url: "not-a-url"` → project created but onboarding fails with `onboarding_failed` event |
| **Missing git_url** | `POST /api/v1/projects/{id}/actions/onboard` on project with `git_url: null` → `400` error |
| **Duplicate onboarding** | Call onboard twice → second call should succeed (idempotent) or return meaningful status |
| **Non-existent project** | `POST /api/v1/projects/99999/actions/onboard` → `404` |

### A.7 Alternative: POST /onboarding/actions/start

|| Item | Detail |
|------|--------|
| **Endpoint** | `POST /api/v1/projects/{id}/onboarding/actions/start` |
| **Precondition** | Project must have `git_url` set |
| **Payload** | `{"clone_if_missing": true, "run_discovery_agent": false}` |
| **Expected** | `200` with onboarding result |
| **Verify** | Same behavior as A.2; this is an alternative onboarding entry point |

---

## B. Worktree Management

### B.1 List Branches

| Item | Detail |
|------|--------|
| **Endpoint** | `GET /api/v1/projects/{id}/branches` |
| **Expected** | `200` with JSON array of `{name, sha, is_remote}` objects |
| **Verify** | At minimum `main` branch listed |

### B.2 Create Branch → Verify Git Worktree

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /api/v1/projects/{id}/branches` |
| **Payload** | `{"name": "test-branch-001", "base_ref": "main", "checkout": false}` |
| **Expected** | `200` with `{"message": "Branch created: test-branch-001", "branch": "test-branch-001"}` |
| **Verify** | `GET /api/v1/projects/{id}/branches` now includes `test-branch-001` |

### B.3 SpecKit Specify → Verify Worktree with Correct Branch Naming

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /api/v1/speckit/specify` |
| **Payload** | `{"project_id": {id}, "feature_name": "add-auth"}` |
| **Expected** | `200` with worktree created, branch named `{NNN}-add-auth` |
| **Verify** | Response contains `worktree_path`, `branch_name` matching `NNN-add-auth` pattern |

### B.4 Delete Branch Cleanup

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /api/v1/projects/{id}/branches/{branch}/delete` |
| **Expected** | `200` with `{"message": "Branch deleted: test-branch-001"}` |
| **Verify** | `GET /api/v1/projects/{id}/branches` no longer lists the branch |

### B.5 List Worktrees

| Item | Detail |
|------|--------|
| **Endpoint** | `GET /api/v1/projects/{id}/worktrees` |
| **Expected** | `200` with JSON array of `{branch_name, worktree_path, protocol_run_id, protocol_name, protocol_status}` |
| **Verify** | Worktrees created by SpecKit appear here |

### B.6 Worktree Isolation

| Item | Detail |
|------|--------|
| **Precondition** | Worktree created via SpecKit specify |
| **Check** | Write a file in worktree → verify it does NOT exist in main repo |
| **Verify** | `git diff` between worktree branch and main shows only the worktree changes |

---

## C. SpecKit Full Flow (specify → plan → tasks → implement)

### C.1 POST /speckit/specify → Creates Worktree + spec.md

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /api/v1/speckit/specify` |
| **Payload** | `{"project_id": {id}, "description": "Build a user dashboard with real-time data visualization widgets and chart components", "feature_name": "user-dashboard"}` |
| **Notes** | `description` is required (min 10 chars). This is an **AI-powered operation** that may take 30-300s. Consider using extended timeout or async polling. |
| **Expected** | `200` with `success: true`, `spec_path`, `worktree_path`, `branch_name`, `spec_run_id` |
| **Verify** | `spec.md` file exists in worktree at `{worktree_path}/specs/{NNN}-user-dashboard/spec.md` |

### C.2 GET /speckit/status/{project_id} → Verify Spec Stage

| Item | Detail |
|------|--------|
| **Endpoint** | `GET /api/v1/speckit/status/{project_id}` |
| **Expected** | `200` with spec stage info |
| **Verify** | Stage reflects current state (e.g., `spec` after specify) |

### C.3 POST /speckit/plan → Creates plan.md, data-model.md, research.md

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /api/v1/speckit/plan` |
| **Payload** | `{"project_id": {id}, "spec_path": "{spec_path from C.1}", "spec_run_id": {spec_run_id}}` |
| **Notes** | `spec_path` is required. AI-powered operation. |
| **Expected** | `200` with plan artifacts created |
| **Verify** | `plan.md` exists in spec directory |

### C.4 POST /speckit/tasks → Creates tasks.md with - [ ] Checkboxes

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /api/v1/speckit/tasks` |
| **Payload** | `{"project_id": {id}, "plan_path": "{plan_path from C.3}", "spec_run_id": {spec_run_id}}` |
| **Notes** | `plan_path` is required. AI-powered operation. |
| **Expected** | `200` with tasks artifact created |
| **Verify** | `tasks.md` exists and contains `- [ ]` checkbox items |

### C.5 POST /speckit/analyze → Creates analysis.md

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /api/v1/speckit/analyze` |
| **Payload** | `{"project_id": {id}, "spec_path": "{spec_path}", "spec_run_id": {spec_run_id}}` |
| **Notes** | `spec_path` is required. AI-powered operation. |
| **Expected** | `200` with analysis results |
| **Verify** | Analysis content returned in response or `analysis.md` created |

### C.6 POST /speckit/checklist → Generates Checklist

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /api/v1/speckit/checklist` |
| **Payload** | `{"project_id": {id}, "spec_path": "{spec_path}", "spec_run_id": {spec_run_id}}` |
| **Notes** | `spec_path` is required. AI-powered operation. |
| **Expected** | `200` with checklist content |
| **Verify** | Checklist contains actionable items |

### C.7 POST /speckit/workflow → Full Pipeline (specify → plan → tasks)

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /api/v1/speckit/workflow` |
| **Payload** | `{"project_id": {id}, "description": "Build a dashboard with charts and real-time data visualization widgets", "feature_name": "full-flow-test"}` |
| **Notes** | `description` required (min 10 chars). `spec_content` NOT accepted (extra fields forbidden). AI-powered — may take 3-5 minutes. |
| **Expected** | `200` with full pipeline results (spec + plan + tasks all created) |
| **Verify** | All artifacts exist: `spec.md`, `plan.md`, `tasks.md` |

### C.8 POST /speckit/cleanup → Removes Worktree + Branch

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /api/v1/speckit/spec-runs/{spec_run_id}/cleanup` |
| **Payload** | `{"delete_remote_branch": false}` |
| **Notes** | Spec run must be stopped/inactive before cleanup |
| **Expected** | `200` with cleanup confirmation |
| **Verify** | Worktree removed from disk; branch deleted from git |

### C.9 POST /speckit/implement → Bootstraps Protocol Execution

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /api/v1/speckit/implement` |
| **Payload** | `{"project_id": {id}, "spec_path": "{spec_path}", "spec_run_id": {spec_run_id}}` |
| **Notes** | `spec_path` is required. AI-powered operation. |
| **Expected** | `200` with protocol creation or execution bootstrap |
| **Verify** | Protocol run created and associated with spec |

### C.10 GET /specifications → Cross-Project Listing with Filters

|| Item | Detail |
|------|--------|
| **Endpoint** | `GET /api/v1/specifications` |
| **Query Params** | `project_id`, `status`, `has_plan`, `has_tasks`, `search`, `limit`, `offset` |
| **Expected** | `200` with `{items: [...], total: N, filters_applied: {...}}` |
| **Verify** | Pagination works; filter params narrow results correctly |

### C.11 GET /speckit/specs/{project_id} → Per-Project Spec Listing

|| Item | Detail |
|------|--------|
| **Endpoint** | `GET /api/v1/speckit/specs/{project_id}` |
| **Expected** | `200` with JSON array of spec runs for the project |
| **Verify** | Each spec has `id`, `name`, `status`, `spec_run_id`, `branch_name`, `feature_name` |

---

## D. AI Agent Execution

### D.1 GET /agents/health → All 4 Agents Healthy

| Item | Detail |
|------|--------|
| **Endpoint** | `GET /api/v1/agents/health` |
| **Expected** | `200` with agent health summary |
| **Verify** | Response includes agents: `opencode`, `claude-code`, `codex`, `gemini-cli` with status info |

### D.2 POST /agents/{agent_id}/test → Per-Agent Smoke Test

|| Item | Detail |
|------|--------|
| **Endpoint** | `POST /api/v1/agents/{agent_id}/test` |
| **Agents** | `opencode`, `claude-code`, `codex`, `gemini-cli` |
| **Test URL** | `POST /api/v1/agents/opencode/test` (use real `agent_id`, not placeholder) |
| **Expected** | `200` with test results per agent |
| **Verify** | Each agent returns a success/failure result |

### D.3 GET /agents/{agent_id}/health → Individual Agent Health

| Item | Detail |
|------|--------|
| **Endpoint** | `GET /api/v1/agents/{agent_id}/health` |
| **Expected** | `200` with health status and response time |
| **Verify** | `status` field present; `response_time_ms` or similar latency metric |

### D.4 Agent Assignment: PUT /agents/projects/{project_id}

| Item | Detail |
|------|--------|
| **Endpoint** | `PUT /api/v1/agents/projects/{project_id}` |
| **Payload** | `{"agent_id": "opencode"}` |
| **Expected** | `200` confirming agent assignment |
| **Verify** | Subsequent project operations use assigned agent |

### D.5 Verify opencode (Default) Engine Can Be Dispatched

| Item | Detail |
|------|--------|
| **Precondition** | Agent assigned to project |
| **Check** | Execute a task via SpecKit or protocol → verify agent dispatch logs |
| **Verify** | Default agent (opencode) receives and processes the task |

### D.6 Verify Agent Metrics: GET /agents/metrics

| Item | Detail |
|------|--------|
| **Endpoint** | `GET /api/v1/agents/metrics` |
| **Expected** | `200` with metrics data (tasks completed, avg response time, etc.) |
| **Verify** | Metrics are structured JSON with per-agent breakdowns |

### D.7 Verify Agent Config: PUT /agents/{agent_id}/config

| Item | Detail |
|------|--------|
| **Endpoint** | `PUT /api/v1/agents/{agent_id}` |
| **Payload** | `{"config": {"key": "value"}}` or agent update model |
| **Expected** | `200` with updated agent config |
| **Verify** | Config persisted; subsequent GET reflects changes |

---

## E. Brownfield + Task Cycle

### E.1 POST /projects/{id}/brownfield/run → Start Brownfield Analysis

|| Item | Detail ||
|------|--------|
| **Precondition** | Project must have `local_path` set (project cloned/onboarded first) |
| **Endpoint** | `POST /api/v1/projects/{id}/brownfield/run` |
| **Payload** | `{"feature_request": "Analyze existing codebase and identify improvement areas", "output_mode": "protocol", "feature_name": "brownfield-analysis"}` |
| **Notes** | `feature_request` is **required** (not `output_mode`). AI-powered operation — may take 30-300s. |
| **Expected** | `200` (synchronous) or `202` (background) with `BrownfieldRunOut` |
| **Verify** | `success: true` in response; protocol and work items created |

### E.2 GET /projects/{id}/task-cycle → List Work Items

| Item | Detail |
|------|--------|
| **Endpoint** | `GET /api/v1/projects/{id}/task-cycle` |
| **Expected** | `200` with JSON array of work items |
| **Verify** | Work items have `id`, `status`, `title` fields |

### E.3 Work Item Lifecycle: build-context → implement → review → qa → mark-pr-ready

| Step | Endpoint | Expected |
|------|----------|----------|
| **Build Context** | `POST /api/v1/work-items/{id}/build-context` with `{"refresh": false}` | `200` with enriched work item |
| **Implement** | `POST /api/v1/work-items/{id}/actions/implement` with `{"owner_agent": "opencode"}` | `200` with updated status |
| **Review** | `POST /api/v1/work-items/{id}/actions/review` | `200` with review results |
| **QA** | `POST /api/v1/work-items/{id}/actions/qa` with `{"gates": null}` | `200` with QA results |
| **Mark PR Ready** | `POST /api/v1/work-items/{id}/actions/mark-pr-ready` | `200` with updated status |

### E.4 Verify Protocol Created from Brownfield Run

| Item | Detail |
|------|--------|
| **Precondition** | Brownfield run completed (E.1) |
| **Check** | `GET /api/v1/projects/{id}/protocols` |
| **Verify** | At least one protocol exists with steps derived from brownfield analysis |

### E.5 Verify Work Items Counted from tasks.md

| Item | Detail |
|------|--------|
| **Precondition** | Tasks generated via SpecKit |
| **Check** | `GET /api/v1/projects/{id}/task-cycle` returns items count matching `- [ ]` items in `tasks.md` |
| **Verify** | Count alignment between markdown tasks and DB work items |

---

## F. Frontend Integration (via browser)

> These tests require a browser or headless browser automation (Playwright, Cypress, etc.)

### F.1 Load /console → Verify Redirect or Dashboard

| Item | Detail |
|------|--------|
| **URL** | `http://localhost:3000/console` |
| **Expected** | Redirect to login page OR render dashboard |
| **Verify** | Page loads without 500 error; title contains "DevGodzilla" or similar |

### F.2 Projects Page → Create Project → Verify in List

| Item | Detail |
|------|--------|
| **URL** | `http://localhost:3000/console/projects` |
| **Actions** | Click "New Project", fill form, submit |
| **Verify** | New project card appears in project list |

### F.3 Project Detail → Onboarding Tab → Start Onboarding

| Item | Detail |
|------|--------|
| **URL** | `http://localhost:3000/console/projects/{id}` |
| **Actions** | Navigate to "Onboarding" tab, click "Start Onboarding" |
| **Verify** | Progress stages appear; status updates to running then completed |

### F.4 Agents Page → Verify 4 Agents with Health Status

| Item | Detail |
|------|--------|
| **URL** | `http://localhost:3000/console/agents` |
| **Expected** | 4 agent cards: opencode, claude-code, codex, gemini-cli |
| **Verify** | Each shows health status (green/red indicator) |

### F.5 Specifications Page → Verify Listing

| Item | Detail |
|------|--------|
| **URL** | `http://localhost:3000/console/specifications` |
| **Expected** | Spec listing with filter options |
| **Verify** | Specs from on-boarded projects appear |

### F.6 Protocols Page → Verify Listing

| Item | Detail |
|------|--------|
| **URL** | `http://localhost:3000/console/protocols` |
| **Expected** | Protocol listing with status indicators |
| **Verify** | Protocols from brownfield/spec flow appear |

### F.7 Steps Page → Verify Feedback Tab Present

| Item | Detail |
|------|--------|
| **URL** | `http://localhost:3000/console/protocols/{id}/steps` |
| **Expected** | Step list with feedback mechanism |
| **Verify** | Feedback tab/form present for each step |

### F.8 Ops → Events, Logs, Metrics, Queues Tabs

| Item | Detail |
|------|--------|
| **URL** | `http://localhost:3000/console/ops` |
| **Expected** | Tabs for Events, Logs, Metrics, Queues |
| **Verify** | Each tab renders content; Events shows live SSE stream |

### F.9 Settings Page → Verify Profile and Health

| Item | Detail |
|------|--------|
| **URL** | `http://localhost:3000/console/settings` |
| **Expected** | Profile section, system health indicator |
| **Verify** | Page loads; health check shows backend connectivity |

---

## G. Sprint + Execution Layer

### G.1 GET /sprints → List Sprints

| Item | Detail |
|------|--------|
| **Endpoint** | `GET /api/v1/sprints` |
| **Expected** | `200` with JSON array of sprint objects |
| **Verify** | Each sprint has `id`, `name`, `project_id`, `status`, `start_date`, `end_date` |

### G.2 POST /sprints → Create Sprint

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /api/v1/sprints` |
| **Payload** | `{"project_id": {id}, "name": "Sprint 1", "goal": "Initial sprint", "status": "planning", "start_date": "2026-04-19", "end_date": "2026-05-02"}` |
| **Expected** | `200` with created sprint |
| **Verify** | Sprint appears in `GET /api/v1/sprints` listing |

### G.3 Sprint Board → Task Management

| Item | Detail |
|------|--------|
| **List Tasks** | `GET /api/v1/sprints/{sprint_id}/tasks` → `200` with task array |
| **Link Protocol** | `POST /api/v1/sprints/{sprint_id}/actions/link-protocol` with `{"protocol_run_id": {id}, "auto_sync": true}` |
| **Sync Tasks** | `POST /api/v1/sprints/{sprint_id}/actions/sync-from-protocol` with `{"protocol_run_id": {id}}` |
| **Expected** | Tasks synced from protocol steps to sprint board |

### G.4 Sprint Metrics

| Item | Detail |
|------|--------|
| **Endpoint** | `GET /api/v1/sprints/{sprint_id}/metrics` |
| **Expected** | `200` with `{sprint_id, total_tasks, completed_tasks, total_points, completed_points, burndown, velocity_trend}` |
| **Verify** | Burndown contains data points; velocity trend is 5-element array |

---

## H. Event System

> **Note:** Events endpoint only supports `GET` (no POST). SSE streaming available via `/events/stream`.

### H.1 GET /events → SSE Stream

| Item | Detail |
|------|--------|
| **Endpoint** | `GET /api/v1/events` |
| **Expected** | `200` with `Content-Type: text/event-stream` |
| **Verify** | Initial `event: connected` message; subsequent events follow SSE format |

### H.2 GET /events/recent → Recent Events JSON

| Item | Detail |
|------|--------|
| **Endpoint** | `GET /api/v1/events/recent?limit=50` |
| **Expected** | `200` with `{events: [...]}` |
| **Verify** | Each event has `id`, `event_type`, `message`, `created_at`; events ordered by id descending |

### H.3 Verify Events Emitted for Operations

| Operation | Expected Events |
|-----------|----------------|
| Project create | `project_created` |
| Onboarding start | `onboarding_started` |
| Onboarding complete | `onboarding_repo_ready`, `onboarding_speckit_initialized`, `onboarding_completed` |
| Brownfield run | `brownfield_started`, `brownfield_completed` (or similar) |
| Spec operations | Spec-related events emitted during specify/plan/tasks flow |

---

## I. Policy Packs + Constitution

### I.1 GET /policy_packs → List

| Item | Detail |
|------|--------|
| **Endpoint** | `GET /api/v1/policy_packs` |
| **Expected** | `200` with JSON array of policy packs |
| **Verify** | Each has `key`, `version`, `name`, `status` |

### I.2 POST /policy_packs → Create

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /api/v1/policy_packs` |
| **Payload** | `{"key": "test-policy", "version": "1.0.0", "name": "Test Policy", "description": "A test policy pack", "status": "active", "pack": {"rules": [{"id": "rule-1", "description": "Test rule"}]}}` |
| **Expected** | `200` with created policy pack |
| **Verify** | Pack appears in listing; key+version uniquely identifies it |

### I.3 GET /policy_packs/{key} → Get Specific Pack

| Item | Detail |
|------|--------|
| **Endpoint** | `GET /api/v1/policy_packs/test-policy` |
| **Expected** | `200` with the latest active version |
| **Verify** | Returns pack created in I.2 |

### I.4 Constitution Generation During Onboarding

| Item | Detail |
|------|--------|
| **Precondition** | Project with policy pack assigned |
| **Check** | After onboarding, `{local_path}/.specify/memory/constitution.md` exists |
| **Verify** | Constitution content reflects policy pack rules |

### I.5 Clarification Generation from Policy

| Item | Detail |
|------|--------|
| **Precondition** | Policy pack with clarifications enabled |
| **Endpoint** | `GET /api/v1/projects/{id}/clarifications` |
| **Expected** | `200` with clarification questions derived from policy |
| **Verify** | Clarifications have `key`, `question`, `status` fields |

---

## Test Execution Notes

### Environment Setup
```bash
# Backend must be running
curl -s http://localhost:8000/api/v1/agents/health | python3 -m json.tool

# Environment variable for agent auth
export DEVGODZILLA_ASSUME_AGENT_AUTH=true
```

### Test Project
- Use `https://github.com/ilyafedotov-ops/dev-pipeline` as test repo URL
- Clean up test data after suite completion

### Automation
- Sections A–E can be fully automated via `curl` + `jq`
- Section F requires browser automation (Playwright recommended)
- Sections G–I can be automated via `curl` + `jq`

### Pass Criteria
- **PASS**: HTTP status matches expected, response body contains required fields
- **FAIL**: HTTP status mismatch, missing required fields, or uncaught exceptions
- **SKIP**: Feature not available or intentionally disabled (document reason)
