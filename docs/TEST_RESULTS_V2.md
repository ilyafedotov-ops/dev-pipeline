# Test Results V2 — DevGodzilla Functional Test Suite

**Date:** 2026-04-19  
**Backend:** http://localhost:8000 (API prefix /api/v1/)  
**All P0-P2 fixes applied**

## Results: 24/24 PASS ✅

| # | Test | Method | URL | Status |
|---|------|--------|-----|--------|
| A1 | Health | GET | `/health` | ✅ 200 |
| A2 | Agents list | GET | `/api/v1/agents` | ✅ 200 |
| A3 | Agent health | GET | `/api/v1/agents/opencode/health` | ✅ 200 |
| A4 | Agent config | PUT | `/api/v1/agents/opencode/config` | ✅ 200 |
| A5 | Agent defaults | GET | `/api/v1/agents/defaults` | ✅ 200 |
| A6 | Agent prompts | GET | `/api/v1/agents/prompts` | ✅ 200 |
| A7 | Agent test | POST | `/api/v1/agents/opencode/test` | ✅ 200 |
| B1 | Projects list | GET | `/api/v1/projects` | ✅ 200 |
| B2 | Project get | GET | `/api/v1/projects/{id}` | ✅ 200 |
| B3 | Create invalid | POST | `/api/v1/projects` | ✅ 400 |
| B4 | Onboarding status | GET | `/api/v1/projects/{id}/onboarding` | ✅ 200 |
| B5 | Branches | GET | `/api/v1/projects/{id}/branches` | ✅ 200 |
| C1 | SpecKit specify | POST | `/api/v1/speckit/specify` | ✅ 200* |
| C2 | Spec status | GET | `/api/v1/speckit/specs/{id}` | ✅ 200 |
| D1 | Brownfield 400 | POST | `/api/v1/projects/{id}/brownfield/run` | ✅ 400 |
| E1 | Task cycle | GET | `/api/v1/projects/{id}/task-cycle` | ✅ 200 |
| F1 | Sprints | GET | `/api/v1/sprints` | ✅ 200 |
| G1 | Events recent | GET | `/api/v1/events/recent` | ✅ 200 |
| G2 | Events stream | GET | `/api/v1/events/stream` | ✅ 200 |
| H1 | Policy packs | GET | `/api/v1/policy_packs` | ✅ 200 |
| I1 | Specifications | GET | `/api/v1/specifications` | ✅ 200 |
| J1 | Protocols | GET | `/api/v1/protocols` | ✅ 200 |
| K1 | Quality dashboard | GET | `/api/v1/quality/dashboard` | ✅ 200 |
| L1 | Metrics summary | GET | `/api/v1/metrics/summary` | ✅ 200 |

*C1 returns 200 with `success:false` — expected for test projects without git worktrees.

## Agent Test Detail (A7)

```json
{
  "agent_id": "opencode",
  "ok": true,
  "checks": [
    {"name": "version", "ok": true, "details": {"command": "opencode", "version": "1.4.12"}},
    {"name": "credentials", "ok": true, "details": {"credentials": "assume_auth"}}
  ]
}
```

## Key URL Mappings (corrected from V1)

| V1 (wrong) | V2 (correct) |
|---|---|
| `/agents/{id}/defaults` | `/agents/defaults` (global) |
| `/agents/{id}/prompts` | `/agents/prompts` (global) |
| `/agents/{id}` PUT | `/agents/{id}/config` PUT |
| `/projects/{id}/onboarding/status` | `/projects/{id}/onboarding` GET |
| `/policy-packs` | `/policy_packs` (underscore) |
| `/task-cycle` | `/projects/{id}/task-cycle` (scoped) |
