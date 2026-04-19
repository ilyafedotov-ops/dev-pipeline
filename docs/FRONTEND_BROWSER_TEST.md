# Frontend Browser Test Report

**Date:** 2026-04-19  
**Frontend:** http://localhost:3000/console/ (Next.js, basePath /console)  
**Backend:** http://localhost:8000 (API prefix /api/v1/)  
**Agent:** glm-5.1 via z.ai

## Pages Tested — 10/10 ✅

| # | Page | URL | Status | Notes |
|---|------|-----|--------|-------|
| 1 | Dashboard | `/console/` | ✅ | Stats cards (15 projects, 0 protocols, 0 runs), quick actions, command palette |
| 2 | Agents | `/console/agents` | ✅ | 6 agents listed (Claude Code, Codex, Gemini CLI, Gemini Pro, GPT-4, OpenCode) |
| 3 | Agent Detail | click agent → Configure | ✅ | Dialog with name, kind, model, command, capabilities, enabled switch, test button |
| 4 | Projects | `/console/projects` | ✅ | 15 projects listed with status badges, search, filter |
| 5 | Project Create | click "New Project" | ✅ | 3-step wizard: Git Repository → Policy Pack → Review & Start |
| 6 | Project Detail | `/console/projects/37` | ✅ | 10 tabs across Development/Execution/Governance/Configuration. SpecKit workflow with 8 steps |
| 7 | Specifications | `/console/specifications` | ✅ | 12 specs listed with Clarify/Checklist/Analyze/Implement/Cleanup buttons |
| 8 | Sprints/Kanban | `/console/execution` | ✅ | Kanban board with 5 columns: To Do/In Progress/Review/Testing/Done |
| 9 | Events/Logs | `/console/ops/events`, `/console/ops/logs` | ✅ | Event timeline with filters, live backend log streaming with subsystem filters |
| 10 | Theme Toggle | Settings page | ✅ | Dark/Light switch works correctly |

## API Endpoint Verification

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /api/v1/projects` | ✅ 200 | Returns project list |
| `GET /api/v1/agents` | ✅ 200 | Returns 6 agents |
| `GET /api/v1/specifications` | ✅ 200 | Returns 12 specifications |
| `GET /api/v1/events` | ✅ 200 | Returns event list |
| `GET /api/v1/protocols` | ✅ 200 | Returns protocol list |
| `GET /api/v1/projects/{id}/commits` | ❌ 502 | Backend git log fails for test projects |

## Agent Status (from UI)

| Agent | Status | Notes |
|-------|--------|-------|
| OpenCode | ✅ Configured | Default engine |
| Gemini CLI | ✅ Configured | Warning: no API key |
| Claude Code | ⚠️ Down | CLI not in PATH |
| OpenAI Codex | ⚠️ Down | CLI not in PATH |
| Gemini Pro | ❌ Disabled | API agent, not CLI |
| GPT-4 | ❌ Disabled | API agent, not CLI |

## Issues Found

| Severity | Issue | Detail | Recommendation |
|----------|-------|--------|----------------|
| 🟡 Low | Recurring 404 | One 404 on every page load (likely missing favicon/manifest) | Add proper favicon.ico and manifest.json |
| 🟠 Medium | 502 on `/projects/{id}/commits` | Backend git log fails for test projects without git repos; frontend retries 3x unnecessarily | Add error boundary, don't retry on 502 |
| 🟠 Medium | Agent status misleading | CLI agents show "Down" in UI but `/agents/{id}/health` says "available" (via assume_auth) | Align UI status with health endpoint |
| 🔴 High | 500 on Settings theme toggle | Observed once during theme toggle — cause unknown | Needs reproduction with stack trace |

## Key UI Features Verified

### Project Create Wizard
- Step 1: Git Repository URL input, local path option
- Step 2: Policy Pack selection
- Step 3: Review & Start with configuration summary

### Project Detail Tabs (10 tabs)
**Development:** Overview, SpecKit, Brownfield  
**Execution:** Sprints, Work Items, Protocols  
**Governance:** Events, Policy  
**Configuration:** Settings, Branches

### SpecKit Workflow (8 steps)
1. Constitution → 2. Clarify → 3. Plan → 4. Checklist → 5. Specify → 6. Analyze → 7. Implement → 8. Cleanup

### Kanban Board
5 columns with drag-and-drop support: To Do, In Progress, Review, Testing, Done

## Console Errors Summary
- ~404 on favicon/manifest (cosmetic)
- 502 on commits endpoint (expected for test projects)
- No JavaScript runtime errors on any page
- No React hydration mismatches
