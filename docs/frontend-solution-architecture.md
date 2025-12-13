# Frontend Solution Architecture

**Version**: 1.0  
**Date**: 2025-12-13  
**Status**: Proposed

---

## Executive Summary

This document defines the **frontend architecture and site structure** for the TasksGodzilla Web Console, fully aligned with the current backend services layer (11 services) and FastAPI API (56 endpoints).

The goal is to evolve from the current single-file static console into a maintainable, feature-oriented frontend that provides:

- **Projects & Onboarding**: register repos, configure policy, resolve clarifications
- **Protocol Lifecycle**: create → plan → execute → QA → PR → CI → complete
- **Policy Governance**: policy packs, effective policy, findings, enforcement
- **Execution Traceability**: runs, logs, artifacts per step/protocol
- **Operational Visibility**: queues, jobs, events, metrics

---

## Table of Contents

1. [Current State Analysis](#1-current-state-analysis)
2. [Backend Alignment](#2-backend-alignment)
3. [Frontend Architecture](#3-frontend-architecture)
4. [Site Structure & Route Map](#4-site-structure--route-map)
5. [Feature Module Specifications](#5-feature-module-specifications)
6. [Data Model & State Management](#6-data-model--state-management)
7. [Component Library](#7-component-library)
8. [API Integration Layer](#8-api-integration-layer)
9. [Error Handling & UX Patterns](#9-error-handling--ux-patterns)
10. [Security Model](#10-security-model)
11. [Repository Structure](#11-repository-structure)
12. [Migration Plan](#12-migration-plan)
13. [Appendix: Complete API Mapping](#appendix-complete-api-mapping)

---

## 1. Current State Analysis

### 1.1 Existing Frontend

**Location**: `tasksgodzilla/api/frontend/`

| File | Purpose |
|------|---------|
| `index.html` | Single-page shell with embedded structure |
| `console.js` | ~2500 lines of imperative JS (DOM manipulation, API calls, state) |
| `console.css` | Dark theme styling (~560 lines) |
| `logo.png`, `banner.png` | Branding assets |

**Current capabilities** (all in one page):
- Projects: list, create, per-project token
- Onboarding: summary, stages, start/inline, clarifications
- Policy: pack selection, overrides, effective preview, findings, pack admin
- Protocols: list, create, actions (start/pause/resume/cancel/run_next/retry/open_pr)
- Steps: list table, actions (run_qa, approve)
- Runs: protocol runs table with links to logs/artifacts
- Events: protocol events, recent events with filters
- Queue: stats, jobs list
- Metrics: summary panel
- Spec audit: enqueue, history

### 1.2 Limitations

| Issue | Impact |
|-------|--------|
| **No routing** | Cannot bookmark or share links to specific protocols/steps/runs |
| **Monolithic state** | Global `state` object with manual invalidation |
| **No type safety** | Easy to break API contracts |
| **Tight coupling** | UI logic mixed with data fetching |
| **No component model** | Copy-paste patterns, hard to maintain |
| **Poor scalability** | Large event/run lists cause performance issues |
| **No offline resilience** | Network errors break the entire page |

### 1.3 What Works Well (to preserve)

- Dark theme aesthetic
- Two-column layout (projects sidebar + main content)
- Quick actions pattern
- Status pill styling
- Polling model for live updates

---

## 2. Backend Alignment

### 2.1 Services Layer (11 services)

The frontend should align with the services layer as the conceptual model:

| Service | Frontend Domain |
|---------|-----------------|
| `OrchestratorService` | Protocol lifecycle, step orchestration |
| `ExecutionService` | Step execution status |
| `QualityService` | QA status, verdicts |
| `OnboardingService` | Project setup flow |
| `SpecService` | Protocol spec viewing |
| `GitService` | Branches, worktrees (read-only view) |
| `BudgetService` | Token usage display |
| `PolicyService` | Policy packs, findings, effective policy |
| `ClarificationsService` | Questions/answers UI |
| `CodeMachineService` | CodeMachine import modal |
| `PlanningService` | Planning status (part of protocol) |

### 2.2 Domain Models

```
Project
├── id, name, git_url, local_path, base_branch, ci_provider
├── default_models, secrets
├── project_classification
└── Policy fields: policy_pack_key, policy_pack_version, policy_overrides,
                   policy_repo_local_enabled, policy_effective_hash,
                   policy_enforcement_mode

ProtocolRun
├── id, project_id, protocol_name, status, base_branch
├── worktree_path, protocol_root, description
├── template_config, template_source
├── spec_hash, spec_validation_status, spec_validated_at
└── Policy snapshot: policy_pack_key, policy_pack_version,
                     policy_effective_hash, policy_effective_json

StepRun
├── id, protocol_run_id, step_index, step_name, step_type
├── status, retries, model, engine_id
├── policy (loop/trigger policies from spec)
├── runtime_state (loop counts, trigger depth)
└── summary

Event
├── id, protocol_run_id, step_run_id
├── event_type, message, metadata
├── created_at
└── Joined: protocol_name, project_id, project_name

CodexRun (job execution record)
├── run_id, job_type, run_kind, status
├── project_id, protocol_run_id, step_run_id
├── attempt, worker_id, queue
├── prompt_version, params, result, error
├── log_path, cost_tokens, cost_cents
└── started_at, finished_at

RunArtifact
├── id, run_id, name, kind, path
├── sha256, bytes
└── created_at

PolicyPack
├── id, key, version, name, description, status
└── pack (JSON: meta, defaults, requirements, clarifications, enforcement)

Clarification
├── id, scope, project_id, protocol_run_id, step_run_id
├── key, question, recommended, options, applies_to
├── blocking, answer, status
└── answered_at, answered_by
```

### 2.3 Status Enums

**ProtocolRun.status**:
```
pending → planning → planned → running → paused|blocked|failed|cancelled|completed
```

**StepRun.status**:
```
pending → running → needs_qa → completed|failed|cancelled|blocked
```

**CodexRun.status**:
```
queued → running → succeeded|failed|cancelled
```

### 2.4 Policy Packs (built-in)

| Key | Description |
|-----|-------------|
| `default` | Baseline policy (warnings only) |
| `beginner-guided` | More structure for inexperienced users |
| `startup-fast` | Minimal overhead, iteration speed |
| `team-standard` | Balanced for professional teams |
| `enterprise-compliance` | Regulated/audited workflows |

---

## 3. Frontend Architecture

### 3.1 Architecture Decision: SPA

**Choice**: Single-Page Application (SPA)

**Rationale**:
- Control-plane dashboard with live data
- Many tables, forms, and action buttons
- Need routing, state management, component composition
- TUI already exists for terminal users; web needs full UX

### 3.2 Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Language** | TypeScript | Type safety, better DX |
| **UI Framework** | React 18+ | Ecosystem, hooks, concurrent features |
| **Build** | Vite | Fast dev server, ESM-first |
| **Routing** | TanStack Router | Type-safe routes, search params |
| **Data Fetching** | TanStack Query v5 | Cache, mutations, optimistic updates |
| **UI Components** | Radix UI + Tailwind CSS | Accessible primitives + utility styling |
| **Forms** | React Hook Form + Zod | Validation, type inference |
| **Tables** | TanStack Table | Virtual scrolling, sorting, filtering |
| **Testing** | Vitest + Testing Library | Fast, React-native |

### 3.3 Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                        App Shell                                │
│  (Layout, Navigation, Providers, Auth, Global Error Boundary)   │
├─────────────────────────────────────────────────────────────────┤
│                      Feature Modules                            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │Projects │ │Protocols│ │  Steps  │ │  Runs   │ │   Ops   │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐                          │
│  │ Policy  │ │Clarific.│ │CodeMach.│                          │
│  └─────────┘ └─────────┘ └─────────┘                          │
├─────────────────────────────────────────────────────────────────┤
│                     Shared Components                           │
│  (Tables, Forms, Modals, Pills, Actions, Timeline, CodeBlock)   │
├─────────────────────────────────────────────────────────────────┤
│                      API Client Layer                           │
│  (Typed client, auth headers, error normalization, query hooks) │
├─────────────────────────────────────────────────────────────────┤
│                     Backend (FastAPI)                           │
└─────────────────────────────────────────────────────────────────┘
```

### 3.4 Data Flow

```
User Action
    │
    ▼
Route Change / Form Submit / Button Click
    │
    ▼
TanStack Query Mutation / Query
    │
    ▼
API Client (fetch + auth headers)
    │
    ▼
FastAPI Endpoint
    │
    ▼
Service Layer → DB/Queue
    │
    ▼
Response (JSON)
    │
    ▼
Query Cache Update / Invalidation
    │
    ▼
React Re-render
```

---

## 4. Site Structure & Route Map

### 4.1 Navigation Structure

```
┌──────────────────────────────────────────────────────────────────┐
│  [Logo] TasksGodzilla Console          [Settings] [API Status]  │
├──────────────────────────────────────────────────────────────────┤
│  Nav: Projects | Operations | Policy Packs | Runs | Settings    │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 Complete Route Map

#### Global Routes

| Route | Page | Description |
|-------|------|-------------|
| `/` | Redirect | → `/projects` |
| `/settings` | Settings | API base, tokens, preferences |

#### Projects Feature (`/projects`)

| Route | Page | Key Components |
|-------|------|----------------|
| `/projects` | Projects List | Project cards, create form, filters |
| `/projects/:id` | Project Detail | Tabs: Overview, Onboarding, Protocols, Policy, Clarifications, Branches |
| `/projects/:id/onboarding` | Onboarding Tab | Stage progress, events, start actions |
| `/projects/:id/protocols` | Protocols Tab | Protocol list for project |
| `/projects/:id/policy` | Policy Tab | Pack selection, overrides, effective preview, findings |
| `/projects/:id/clarifications` | Clarifications Tab | Open/answered questions |
| `/projects/:id/branches` | Branches Tab | Remote branches, delete action |

#### Protocols Feature (`/protocols`)

| Route | Page | Key Components |
|-------|------|----------------|
| `/protocols/:id` | Protocol Detail | Header with status/actions, tabs |
| `/protocols/:id/steps` | Steps Tab | Steps table, step actions |
| `/protocols/:id/events` | Events Tab | Timeline, filters |
| `/protocols/:id/runs` | Runs Tab | CodexRun list for protocol |
| `/protocols/:id/spec` | Spec Tab | Spec JSON viewer, validation status |
| `/protocols/:id/policy` | Policy Tab | Findings, snapshot |
| `/protocols/:id/clarifications` | Clarifications Tab | Protocol-scope questions |

#### Steps Feature (`/steps`)

| Route | Page | Key Components |
|-------|------|----------------|
| `/steps/:id` | Step Detail | Status, actions, runs, policy findings |
| `/steps/:id/runs` | Step Runs | CodexRun list for step |
| `/steps/:id/policy` | Step Policy | Policy findings for step |

#### Runs Feature (`/runs`)

| Route | Page | Key Components |
|-------|------|----------------|
| `/runs` | Runs Explorer | Global CodexRun list, filters |
| `/runs/:runId` | Run Detail | Status, params, result, error |
| `/runs/:runId/logs` | Run Logs | Log viewer (plain text) |
| `/runs/:runId/artifacts` | Run Artifacts | Artifact list, content viewer |

#### Operations Feature (`/ops`)

| Route | Page | Key Components |
|-------|------|----------------|
| `/ops` | Redirect | → `/ops/queues` |
| `/ops/queues` | Queues | Queue stats, jobs table |
| `/ops/events` | Recent Events | Global event feed with filters |
| `/ops/metrics` | Metrics | Prometheus metrics summary |

#### Policy Packs Feature (`/policy-packs`)

| Route | Page | Key Components |
|-------|------|----------------|
| `/policy-packs` | Pack List | List of packs with versions |
| `/policy-packs/new` | Create Pack | Pack editor form |
| `/policy-packs/:key` | Pack Detail | View pack JSON, versions |
| `/policy-packs/:key/edit` | Edit Pack | Pack editor |

---

## 5. Feature Module Specifications

### 5.1 Projects Module

**Purpose**: Manage projects, onboarding, and project-level configuration.

**Pages**:

#### Projects List (`/projects`)

```
┌────────────────────────────────────────────────────────────────┐
│ Projects                                      [+ Create Project]│
├────────────────────────────────────────────────────────────────┤
│ Filter: [Search] [Status ▼] [Policy Pack ▼]                    │
├────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────┐  │
│ │ project-name                                              │  │
│ │ git_url • main • github                                   │  │
│ │ [onboarding: completed] [policy: team-standard] [warn]    │  │
│ │ 3 protocols • Last: 2h ago                                │  │
│ └──────────────────────────────────────────────────────────┘  │
│ ┌──────────────────────────────────────────────────────────┐  │
│ │ another-project                                           │  │
│ │ [onboarding: blocked] [2 clarifications pending]          │  │
│ └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

**Data**: `GET /projects`

#### Project Detail (`/projects/:id`)

**Tabs**:
- **Overview**: Summary stats, quick actions (start onboarding, create protocol)
- **Onboarding**: Stage pipeline visualization, events timeline
- **Protocols**: List of protocols for this project
- **Policy**: Policy configuration (see 5.5)
- **Clarifications**: Project-scope questions
- **Branches**: Remote branches list, delete action

**Data**:
- `GET /projects/{id}`
- `GET /projects/{id}/onboarding`
- `GET /projects/{id}/protocols`
- `GET /projects/{id}/policy`
- `GET /projects/{id}/policy/effective`
- `GET /projects/{id}/clarifications`
- `GET /projects/{id}/branches`

**Actions**:
- `POST /projects/{id}/onboarding/actions/start`
- `POST /projects/{id}/branches/{branch}/delete`
- `PUT /projects/{id}/policy`

### 5.2 Protocols Module

**Purpose**: Manage protocol lifecycle and step execution.

#### Protocol Detail (`/protocols/:id`)

```
┌────────────────────────────────────────────────────────────────┐
│ Protocol: 0001-feature-auth                                     │
│ Project: my-project • Branch: 0001-feature-auth • Status: ▣ running │
│ Spec: ✓ valid (abc123) • Policy: team-standard@1.0              │
├────────────────────────────────────────────────────────────────┤
│ Actions: [Pause] [Run Next Step] [Retry Latest] [Open PR]       │
├────────────────────────────────────────────────────────────────┤
│ Tabs: [Steps] [Events] [Runs] [Spec] [Policy] [Clarifications]  │
├────────────────────────────────────────────────────────────────┤
│                         Tab Content                             │
└────────────────────────────────────────────────────────────────┘
```

**Steps Tab**:
```
┌─────┬──────────────┬──────────┬─────────┬────────┬───────────┐
│ Idx │ Name         │ Type     │ Status  │ Engine │ Actions   │
├─────┼──────────────┼──────────┼─────────┼────────┼───────────┤
│ 0   │ 00-setup     │ setup    │ ✓ done  │ codex  │           │
│ 1   │ 01-implement │ work     │ ▶ running│ codex  │           │
│ 2   │ 02-test      │ work     │ ○ pending│ codex  │ [Run]     │
│ 3   │ 03-docs      │ work     │ ○ pending│ codex  │ [Run]     │
└─────┴──────────────┴──────────┴─────────┴────────┴───────────┘
```

**Data**:
- `GET /protocols/{id}`
- `GET /protocols/{id}/steps`
- `GET /protocols/{id}/events`
- `GET /protocols/{id}/runs`
- `GET /protocols/{id}/spec`
- `GET /protocols/{id}/policy/findings`
- `GET /protocols/{id}/policy/snapshot`
- `GET /protocols/{id}/clarifications`

**Actions**:
- `POST /protocols/{id}/actions/start`
- `POST /protocols/{id}/actions/pause`
- `POST /protocols/{id}/actions/resume`
- `POST /protocols/{id}/actions/cancel`
- `POST /protocols/{id}/actions/run_next_step`
- `POST /protocols/{id}/actions/retry_latest`
- `POST /protocols/{id}/actions/open_pr`

### 5.3 Steps Module

**Purpose**: View step details and run actions.

#### Step Detail (`/steps/:id`)

```
┌────────────────────────────────────────────────────────────────┐
│ Step: 01-implement-auth                                         │
│ Protocol: 0001-feature-auth • Index: 1 • Type: work            │
│ Status: ⏳ needs_qa • Retries: 0 • Engine: codex               │
├────────────────────────────────────────────────────────────────┤
│ Actions: [Run] [Run QA] [Approve]                               │
├────────────────────────────────────────────────────────────────┤
│ Runtime State:                                                  │
│   loop_counts: {"qa_retry": 1}                                  │
│   inline_trigger_depth: 0                                       │
├────────────────────────────────────────────────────────────────┤
│ Tabs: [Runs] [Policy Findings]                                  │
├────────────────────────────────────────────────────────────────┤
│ Runs for this step:                                             │
│ ┌──────────┬──────────┬─────────┬───────────┬────────────────┐ │
│ │ Run ID   │ Kind     │ Status  │ Attempt   │ Actions        │ │
│ ├──────────┼──────────┼─────────┼───────────┼────────────────┤ │
│ │ abc-123  │ exec     │ ✓       │ 1         │ [Logs] [Artif.]│ │
│ │ def-456  │ qa       │ ✗ fail  │ 1         │ [Logs]         │ │
│ └──────────┴──────────┴─────────┴───────────┴────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

**Data**:
- `GET /protocols/{protocolId}/steps` (find step)
- `GET /steps/{id}/runs`
- `GET /steps/{id}/policy/findings`

**Actions**:
- `POST /steps/{id}/actions/run`
- `POST /steps/{id}/actions/run_qa`
- `POST /steps/{id}/actions/approve`

### 5.4 Runs Module

**Purpose**: Explore execution runs, logs, and artifacts.

#### Runs Explorer (`/runs`)

```
┌────────────────────────────────────────────────────────────────┐
│ Runs                                                            │
├────────────────────────────────────────────────────────────────┤
│ Filters: [Job Type ▼] [Status ▼] [Run Kind ▼] [Project ▼]      │
│          [Protocol] [Step] [Limit: 100]                         │
├────────────────────────────────────────────────────────────────┤
│ ┌────────┬───────────┬────────┬────────┬────────┬─────────────┐│
│ │ Run ID │ Job Type  │ Kind   │ Status │ Tokens │ Created     ││
│ ├────────┼───────────┼────────┼────────┼────────┼─────────────┤│
│ │ abc123 │ execute   │ exec   │ ✓      │ 5,432  │ 2m ago      ││
│ │ def456 │ run_qual  │ qa     │ ✗      │ 2,100  │ 5m ago      ││
│ └────────┴───────────┴────────┴────────┴────────┴─────────────┘│
└────────────────────────────────────────────────────────────────┘
```

#### Run Detail (`/runs/:runId`)

```
┌────────────────────────────────────────────────────────────────┐
│ Run: abc-123-def-456                                            │
│ Job: execute_step_job • Kind: exec • Status: ✓ succeeded        │
├────────────────────────────────────────────────────────────────┤
│ Links: Project #1 → Protocol #5 → Step #12                      │
├────────────────────────────────────────────────────────────────┤
│ Timing: Created 10:30 • Started 10:31 • Finished 10:35 (4m)    │
│ Worker: worker-1 • Attempt: 1 • Queue: default                  │
│ Tokens: 5,432 • Cost: $0.05                                     │
├────────────────────────────────────────────────────────────────┤
│ Tabs: [Params] [Result] [Error] [Logs] [Artifacts]              │
├────────────────────────────────────────────────────────────────┤
│ Result JSON:                                                    │
│ {                                                               │
│   "exec": { "engine": "codex", "model": "...", ... },          │
│   "qa_inline": { "verdict": "PASS", ... }                       │
│ }                                                               │
└────────────────────────────────────────────────────────────────┘
```

**Data**:
- `GET /codex/runs` (with filters)
- `GET /codex/runs/{runId}`
- `GET /codex/runs/{runId}/logs`
- `GET /codex/runs/{runId}/artifacts`
- `GET /codex/runs/{runId}/artifacts/{artifactId}/content`

### 5.5 Policy Module

**Purpose**: Manage policy packs and project policy configuration.

#### Project Policy Tab (`/projects/:id/policy`)

```
┌────────────────────────────────────────────────────────────────┐
│ Policy Configuration                                            │
├────────────────────────────────────────────────────────────────┤
│ Policy Pack: [team-standard ▼]  Version: [latest ▼] or [1.0]   │
│ Enforcement Mode: [warn ▼]                                      │
│ ☑ Enable repo-local override (.tasksgodzilla/policy.yml)        │
├────────────────────────────────────────────────────────────────┤
│ Overrides (JSON):                                               │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ { "defaults": { "models": { "exec": "codex-5.1-max" } } }  │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                              [Save Policy]      │
├────────────────────────────────────────────────────────────────┤
│ Effective Policy Hash: sha256:abc123...                         │
│ [Preview Effective Policy]                                      │
├────────────────────────────────────────────────────────────────┤
│ Policy Findings (3 warnings):                                   │
│ ⚠ policy.ci.required_check_missing: scripts/ci/security.sh     │
│   Suggested fix: Create the file or update policy requirements  │
│ ⚠ policy.step.missing_section: "Rollback" in step 02           │
│ ⚠ policy.step.missing_section: "Observability" in step 03      │
└────────────────────────────────────────────────────────────────┘
```

#### Policy Packs List (`/policy-packs`)

```
┌────────────────────────────────────────────────────────────────┐
│ Policy Packs                                   [+ Create Pack]  │
├────────────────────────────────────────────────────────────────┤
│ ┌──────────────────┬─────────┬────────────┬──────────────────┐ │
│ │ Key              │ Version │ Status     │ Description      │ │
│ ├──────────────────┼─────────┼────────────┼──────────────────┤ │
│ │ default          │ 1.0     │ active     │ Baseline policy  │ │
│ │ beginner-guided  │ 1.0     │ active     │ More structure...│ │
│ │ startup-fast     │ 1.0     │ active     │ Minimal overhead │ │
│ │ team-standard    │ 1.0     │ active     │ Balanced...      │ │
│ │ enterprise-...   │ 1.0     │ active     │ Regulated...     │ │
│ └──────────────────┴─────────┴────────────┴──────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

**Data**:
- `GET /policy_packs`
- `POST /policy_packs`
- `GET /projects/{id}/policy`
- `PUT /projects/{id}/policy`
- `GET /projects/{id}/policy/effective`
- `GET /projects/{id}/policy/findings`

### 5.6 Clarifications Module

**Purpose**: Manage blocking and non-blocking questions.

#### Clarifications View

```
┌────────────────────────────────────────────────────────────────┐
│ Clarifications                           Filter: [Open ▼]       │
├────────────────────────────────────────────────────────────────┤
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ 🔒 BLOCKING: review_policy                                 │ │
│ │ How many approvals are required before merge?              │ │
│ │ Options: [1-approval] [2-approvals]                        │ │
│ │ Recommended: 1-approval                                     │ │
│ │ Applies to: execution                                       │ │
│ │ ┌────────────────────────────────┐                         │ │
│ │ │ Answer: [________________]     │  [Submit Answer]        │ │
│ │ └────────────────────────────────┘                         │ │
│ └────────────────────────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ ✓ ANSWERED: ci_provider                                    │ │
│ │ Which CI provider should be used?                          │ │
│ │ Answer: github (answered by: user@example.com)             │ │
│ └────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

**Data**:
- `GET /projects/{id}/clarifications?status=open|answered`
- `GET /protocols/{id}/clarifications?status=open|answered`
- `POST /projects/{id}/clarifications/{key}`
- `POST /protocols/{id}/clarifications/{key}`

### 5.7 Operations Module

**Purpose**: Operational visibility into queues, events, metrics.

#### Queues (`/ops/queues`)

```
┌────────────────────────────────────────────────────────────────┐
│ Queue Statistics                             [Refresh]          │
├────────────────────────────────────────────────────────────────┤
│ default: 3 queued • 1 started • 0 failed                        │
│ ████████░░ 80% healthy                                          │
├────────────────────────────────────────────────────────────────┤
│ Recent Jobs:                                Filter: [All ▼]     │
│ ┌──────────────┬───────────────┬────────┬────────────────────┐ │
│ │ Job ID       │ Type          │ Status │ Enqueued           │ │
│ ├──────────────┼───────────────┼────────┼────────────────────┤ │
│ │ job-abc-123  │ execute_step  │ started│ 2m ago             │ │
│ │ job-def-456  │ run_quality   │ queued │ 5m ago             │ │
│ └──────────────┴───────────────┴────────┴────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

#### Recent Events (`/ops/events`)

```
┌────────────────────────────────────────────────────────────────┐
│ Recent Events                    [Refresh] [Auto-poll: 5s ▼]   │
├────────────────────────────────────────────────────────────────┤
│ Filters: [Project ▼] [Event Type ▼] [Spec Hash]                 │
├────────────────────────────────────────────────────────────────┤
│ 10:35:22 │ step_completed │ Step 01 completed │ project-1      │
│ 10:34:15 │ qa_enqueued    │ QA run enqueued   │ project-1      │
│ 10:30:00 │ planning_enqueued │ Planning started │ project-2   │
└────────────────────────────────────────────────────────────────┘
```

**Data**:
- `GET /queues`
- `GET /queues/jobs?status=...`
- `GET /events?limit=...&project_id=...&kind=...`

### 5.8 CodeMachine Integration

**Purpose**: Import CodeMachine workspaces.

#### Import Modal (triggered from Project or Protocol)

```
┌────────────────────────────────────────────────────────────────┐
│ Import CodeMachine Workspace                            [×]     │
├────────────────────────────────────────────────────────────────┤
│ Protocol Name:    [0002-cm-import________________]              │
│ Workspace Path:   [/path/to/.codemachine_________]              │
│ Base Branch:      [main______]                                  │
│ Description:      [Optional description__________]              │
│ ☐ Enqueue as job (async)                                        │
│                                                                 │
│                             [Cancel] [Import]                   │
└────────────────────────────────────────────────────────────────┘
```

**Data**: `POST /projects/{id}/codemachine/import`

---

## 6. Data Model & State Management

### 6.1 State Philosophy

1. **URL is the primary state**: route params and search params
2. **Server state in TanStack Query**: all API data
3. **Minimal UI state**: only transient things (modals, form drafts)

### 6.2 Query Key Schema

```typescript
// Query key factory
const queryKeys = {
  // Projects
  projects: {
    all: ['projects'] as const,
    list: () => [...queryKeys.projects.all, 'list'] as const,
    detail: (id: number) => [...queryKeys.projects.all, 'detail', id] as const,
    onboarding: (id: number) => [...queryKeys.projects.all, 'onboarding', id] as const,
    policy: (id: number) => [...queryKeys.projects.all, 'policy', id] as const,
    policyEffective: (id: number) => [...queryKeys.projects.all, 'policyEffective', id] as const,
    policyFindings: (id: number) => [...queryKeys.projects.all, 'policyFindings', id] as const,
    clarifications: (id: number, status?: string) => 
      [...queryKeys.projects.all, 'clarifications', id, { status }] as const,
    branches: (id: number) => [...queryKeys.projects.all, 'branches', id] as const,
  },
  
  // Protocols
  protocols: {
    all: ['protocols'] as const,
    list: (projectId: number) => [...queryKeys.protocols.all, 'list', projectId] as const,
    detail: (id: number) => [...queryKeys.protocols.all, 'detail', id] as const,
    steps: (id: number) => [...queryKeys.protocols.all, 'steps', id] as const,
    events: (id: number) => [...queryKeys.protocols.all, 'events', id] as const,
    runs: (id: number, filters?: RunFilters) => 
      [...queryKeys.protocols.all, 'runs', id, filters] as const,
    spec: (id: number) => [...queryKeys.protocols.all, 'spec', id] as const,
    policyFindings: (id: number) => [...queryKeys.protocols.all, 'policyFindings', id] as const,
    policySnapshot: (id: number) => [...queryKeys.protocols.all, 'policySnapshot', id] as const,
    clarifications: (id: number, status?: string) => 
      [...queryKeys.protocols.all, 'clarifications', id, { status }] as const,
  },
  
  // Steps
  steps: {
    all: ['steps'] as const,
    runs: (id: number) => [...queryKeys.steps.all, 'runs', id] as const,
    policyFindings: (id: number) => [...queryKeys.steps.all, 'policyFindings', id] as const,
  },
  
  // Runs
  runs: {
    all: ['runs'] as const,
    list: (filters: RunFilters) => [...queryKeys.runs.all, 'list', filters] as const,
    detail: (runId: string) => [...queryKeys.runs.all, 'detail', runId] as const,
    logs: (runId: string) => [...queryKeys.runs.all, 'logs', runId] as const,
    artifacts: (runId: string) => [...queryKeys.runs.all, 'artifacts', runId] as const,
  },
  
  // Policy Packs
  policyPacks: {
    all: ['policyPacks'] as const,
    list: () => [...queryKeys.policyPacks.all, 'list'] as const,
  },
  
  // Ops
  ops: {
    queueStats: ['ops', 'queueStats'] as const,
    queueJobs: (status?: string) => ['ops', 'queueJobs', { status }] as const,
    recentEvents: (filters: EventFilters) => ['ops', 'recentEvents', filters] as const,
  },
};
```

### 6.3 Invalidation Patterns

| Action | Invalidations |
|--------|---------------|
| Create project | `projects.list` |
| Start onboarding | `projects.onboarding(id)`, `ops.queueJobs` |
| Update policy | `projects.policy(id)`, `projects.policyEffective(id)`, `projects.policyFindings(id)` |
| Answer clarification | `projects.clarifications(id)` or `protocols.clarifications(id)` |
| Create protocol | `protocols.list(projectId)` |
| Start protocol | `protocols.detail(id)`, `protocols.steps(id)`, `ops.queueJobs` |
| Run step action | `protocols.steps(id)`, `protocols.events(id)`, `protocols.runs(id)` |
| Run QA | `protocols.steps(id)`, `steps.runs(stepId)`, `protocols.events(id)` |

### 6.4 Polling Configuration

```typescript
const pollingIntervals = {
  // Active protocol view
  protocolSteps: 5000,      // 5s when viewing active protocol
  protocolEvents: 5000,
  
  // Onboarding
  onboardingSummary: 3000,  // 3s when onboarding in progress
  
  // Operations
  queueStats: 10000,        // 10s
  queueJobs: 5000,          // 5s
  recentEvents: 10000,      // 10s
  
  // Disabled when tab not visible
  backgroundDisabled: true,
};
```

---

## 7. Component Library

### 7.1 Core UI Components

| Component | Purpose |
|-----------|---------|
| `StatusPill` | Protocol/step/run status badges |
| `ActionButton` | Primary/secondary/danger action buttons |
| `DataTable` | Sortable, filterable tables with pagination |
| `Timeline` | Events timeline with filtering |
| `CodeBlock` | JSON/text viewer with syntax highlighting |
| `Modal` | Accessible modal dialogs |
| `Tabs` | Tab navigation for detail views |
| `Form` | Form wrapper with validation |
| `Select` | Dropdown with search |
| `Toast` | Notification toasts |
| `ErrorBoundary` | Error handling wrapper |
| `LoadingState` | Skeleton/spinner states |
| `EmptyState` | Empty list/error states |

### 7.2 Domain Components

| Component | Purpose |
|-----------|---------|
| `ProjectCard` | Project summary in list |
| `ProtocolHeader` | Protocol detail header with status/actions |
| `StepsTable` | Steps table with inline actions |
| `OnboardingStages` | Stage pipeline visualization |
| `PolicyForm` | Policy configuration form |
| `ClarificationCard` | Single clarification Q&A |
| `FindingsList` | Policy findings display |
| `RunsTable` | CodexRun list table |
| `LogViewer` | Plain text log display |
| `ArtifactList` | Run artifacts with content preview |
| `QueueStatsCard` | Queue health visualization |
| `EventRow` | Single event in timeline |

### 7.3 Status Pill Variants

```typescript
const statusVariants = {
  // Protocol statuses
  pending: { color: 'gray', icon: 'circle' },
  planning: { color: 'blue', icon: 'loader' },
  planned: { color: 'blue', icon: 'check' },
  running: { color: 'blue', icon: 'play' },
  paused: { color: 'yellow', icon: 'pause' },
  blocked: { color: 'red', icon: 'alert' },
  failed: { color: 'red', icon: 'x' },
  cancelled: { color: 'gray', icon: 'slash' },
  completed: { color: 'green', icon: 'check' },
  
  // Step statuses
  needs_qa: { color: 'yellow', icon: 'clipboard' },
  
  // Run statuses
  queued: { color: 'gray', icon: 'clock' },
  succeeded: { color: 'green', icon: 'check' },
};
```

---

## 8. API Integration Layer

### 8.1 API Client

```typescript
// api/client.ts
interface ApiClientConfig {
  baseUrl: string;
  token?: string;
  projectToken?: string;
  onUnauthorized?: () => void;
}

class ApiClient {
  private config: ApiClientConfig;
  
  async fetch<T>(path: string, options?: RequestInit): Promise<T> {
    const headers = new Headers(options?.headers);
    headers.set('Content-Type', 'application/json');
    
    if (this.config.token) {
      headers.set('Authorization', `Bearer ${this.config.token}`);
    }
    if (this.config.projectToken) {
      headers.set('X-Project-Token', this.config.projectToken);
    }
    headers.set('X-Request-ID', crypto.randomUUID());
    
    const response = await fetch(`${this.config.baseUrl}${path}`, {
      ...options,
      headers,
    });
    
    if (response.status === 401) {
      this.config.onUnauthorized?.();
      throw new ApiError('Unauthorized', 401);
    }
    
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new ApiError(body.detail || 'Request failed', response.status, body);
    }
    
    return response.json();
  }
}
```

### 8.2 Type Generation

**Option A (recommended)**: Generate from OpenAPI

```bash
# Generate types from FastAPI OpenAPI spec
npx openapi-typescript http://localhost:8011/openapi.json -o src/api/schema.ts
```

**Option B**: Manual type definitions tracking `schemas.py`

```typescript
// api/types.ts
export interface Project {
  id: number;
  name: string;
  git_url: string;
  local_path: string | null;
  base_branch: string;
  ci_provider: string | null;
  project_classification: string | null;
  default_models: Record<string, string> | null;
  secrets: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  // Policy fields
  policy_pack_key: string | null;
  policy_pack_version: string | null;
  policy_overrides: Record<string, unknown> | null;
  policy_repo_local_enabled: boolean | null;
  policy_effective_hash: string | null;
  policy_enforcement_mode: string | null;
}

// ... all other types from schemas.py
```

### 8.3 Query Hooks

```typescript
// features/projects/hooks.ts
export function useProjects() {
  return useQuery({
    queryKey: queryKeys.projects.list(),
    queryFn: () => apiClient.fetch<Project[]>('/projects'),
  });
}

export function useProject(id: number) {
  return useQuery({
    queryKey: queryKeys.projects.detail(id),
    queryFn: () => apiClient.fetch<Project>(`/projects/${id}`),
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ProjectCreate) => 
      apiClient.fetch<Project>('/projects', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.list() });
    },
  });
}
```

---

## 9. Error Handling & UX Patterns

### 9.1 Error Types

```typescript
type ApiErrorType = 
  | 'unauthorized'      // 401 - missing/invalid token
  | 'forbidden'         // 401 with project token required
  | 'not_found'         // 404
  | 'conflict'          // 409 - state conflict
  | 'validation'        // 400 - input validation
  | 'server_error'      // 5xx
  | 'network_error';    // fetch failed
```

### 9.2 Error Display Patterns

| Error Type | UI Response |
|------------|-------------|
| `unauthorized` | Redirect to settings, show "Configure API token" |
| `forbidden` | Show per-project token input |
| `conflict` | Toast "State changed, please refresh" + refresh button |
| `validation` | Inline field errors in form |
| `server_error` | Toast with retry option |
| `network_error` | Banner "Connection lost", auto-retry |

### 9.3 Optimistic Updates

For frequently-used actions:
- Answer clarification → optimistic update
- Step approve → optimistic status change

### 9.4 Loading States

| State | Display |
|-------|---------|
| Initial load | Skeleton placeholders |
| Refetch | Subtle refresh indicator (not blocking) |
| Mutation pending | Button loading state, disable form |
| Long-running job | Progress banner with job ID |

### 9.5 Job Acknowledgment Pattern

```
User clicks [Run Next Step]
    │
    ▼
API returns { message: "Step enqueued", job: { job_id: "..." } }
    │
    ▼
Show toast: "Step 02-implement enqueued"
    │
    ▼
Start polling protocol.steps + protocol.events
    │
    ▼
Show event: "step_started" → update step status
    │
    ▼
Show event: "step_completed" → update step status
```

---

## 10. Security Model

### 10.1 Authentication

| Method | Implementation |
|--------|----------------|
| API Token | `Authorization: Bearer <token>` header |
| Project Token | `X-Project-Token: <token>` header (optional) |
| Storage | `localStorage` (MVP) |

### 10.2 Token Flow

```
Settings Page
    │
    ▼
User enters API base + token
    │
    ▼
Store in localStorage: { apiBase, token, projectTokens: {} }
    │
    ▼
API Client reads on each request
    │
    ▼
On 401: redirect to settings
```

### 10.3 Security Headers (FastAPI side)

```python
# Recommended CSP for console
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
```

### 10.4 Future Hardening

- Server-side sessions with HttpOnly cookies
- OIDC/SSO integration
- RBAC per project/organization

---

## 11. Repository Structure

### 11.1 New Frontend Workspace

```
web/
└── console/
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── tailwind.config.ts
    ├── index.html
    ├── public/
    │   ├── logo.png
    │   └── banner.png
    └── src/
        ├── main.tsx
        ├── app/
        │   ├── App.tsx
        │   ├── routes.tsx
        │   ├── providers.tsx
        │   └── layout/
        │       ├── Layout.tsx
        │       ├── Navigation.tsx
        │       └── Header.tsx
        ├── api/
        │   ├── client.ts
        │   ├── errors.ts
        │   ├── types.ts          # or schema.ts (generated)
        │   └── queryKeys.ts
        ├── features/
        │   ├── projects/
        │   │   ├── pages/
        │   │   │   ├── ProjectsListPage.tsx
        │   │   │   └── ProjectDetailPage.tsx
        │   │   ├── components/
        │   │   │   ├── ProjectCard.tsx
        │   │   │   ├── ProjectForm.tsx
        │   │   │   └── OnboardingStages.tsx
        │   │   └── hooks.ts
        │   ├── protocols/
        │   │   ├── pages/
        │   │   │   └── ProtocolDetailPage.tsx
        │   │   ├── components/
        │   │   │   ├── ProtocolHeader.tsx
        │   │   │   ├── StepsTable.tsx
        │   │   │   └── ProtocolActions.tsx
        │   │   └── hooks.ts
        │   ├── steps/
        │   │   ├── pages/
        │   │   │   └── StepDetailPage.tsx
        │   │   ├── components/
        │   │   │   └── StepActions.tsx
        │   │   └── hooks.ts
        │   ├── runs/
        │   │   ├── pages/
        │   │   │   ├── RunsListPage.tsx
        │   │   │   └── RunDetailPage.tsx
        │   │   ├── components/
        │   │   │   ├── RunsTable.tsx
        │   │   │   ├── LogViewer.tsx
        │   │   │   └── ArtifactList.tsx
        │   │   └── hooks.ts
        │   ├── policy/
        │   │   ├── pages/
        │   │   │   ├── PolicyPacksPage.tsx
        │   │   │   └── PolicyPackDetailPage.tsx
        │   │   ├── components/
        │   │   │   ├── PolicyForm.tsx
        │   │   │   ├── FindingsList.tsx
        │   │   │   └── PolicyPackEditor.tsx
        │   │   └── hooks.ts
        │   ├── clarifications/
        │   │   ├── components/
        │   │   │   ├── ClarificationCard.tsx
        │   │   │   └── ClarificationsList.tsx
        │   │   └── hooks.ts
        │   ├── ops/
        │   │   ├── pages/
        │   │   │   ├── QueuesPage.tsx
        │   │   │   ├── EventsPage.tsx
        │   │   │   └── MetricsPage.tsx
        │   │   ├── components/
        │   │   │   ├── QueueStats.tsx
        │   │   │   └── EventTimeline.tsx
        │   │   └── hooks.ts
        │   └── settings/
        │       └── pages/
        │           └── SettingsPage.tsx
        ├── components/
        │   ├── ui/
        │   │   ├── Button.tsx
        │   │   ├── StatusPill.tsx
        │   │   ├── Modal.tsx
        │   │   ├── Tabs.tsx
        │   │   ├── Select.tsx
        │   │   └── Toast.tsx
        │   ├── DataTable.tsx
        │   ├── CodeBlock.tsx
        │   ├── Timeline.tsx
        │   ├── ErrorBoundary.tsx
        │   ├── LoadingState.tsx
        │   └── EmptyState.tsx
        ├── lib/
        │   ├── format.ts
        │   ├── time.ts
        │   └── cn.ts
        └── styles/
            └── globals.css
```

### 11.2 Build Output

**Option A** (recommended for MVP):
```
# Build and copy to FastAPI static directory
cd web/console
npm run build
cp -r dist/* ../../tasksgodzilla/api/frontend_dist/

# Mount in FastAPI
app.mount("/console", StaticFiles(directory="frontend_dist"), name="console")
```

**Option B** (separate hosting):
```
# Deploy to CDN/static host
# Configure CORS in FastAPI
# Proxy /api to FastAPI backend
```

---

## 12. Migration Plan

### Phase 1: Foundation (Week 1-2)

- [ ] Initialize `web/console` workspace
- [ ] Set up Vite + React + TypeScript + Tailwind
- [ ] Implement API client with auth
- [ ] Create base layout and navigation
- [ ] Implement settings page (token config)
- [ ] Generate/write API types

### Phase 2: Core Features (Week 3-4)

- [ ] Projects list and create
- [ ] Project detail with tabs
- [ ] Onboarding view
- [ ] Policy configuration
- [ ] Clarifications UI

### Phase 3: Protocol Management (Week 5-6)

- [ ] Protocol detail page
- [ ] Steps table with actions
- [ ] Protocol events timeline
- [ ] Protocol actions (start/pause/etc.)
- [ ] Step detail page

### Phase 4: Runs & Operations (Week 7-8)

- [ ] Runs explorer
- [ ] Run detail with logs/artifacts
- [ ] Queue stats
- [ ] Recent events
- [ ] Metrics summary

### Phase 5: Polish & Cutover (Week 9-10)

- [ ] Error handling refinement
- [ ] Loading states
- [ ] Responsive design
- [ ] A/B serve at `/console2`
- [ ] Parity testing vs old console
- [ ] Cutover `/console` to new SPA

---

## Appendix: Complete API Mapping

### Health & Metrics

| Method | Endpoint | Feature |
|--------|----------|---------|
| GET | `/health` | Settings (API status) |
| GET | `/metrics` | Ops / Metrics |

### Projects

| Method | Endpoint | Feature |
|--------|----------|---------|
| GET | `/projects` | Projects List |
| POST | `/projects` | Create Project |
| GET | `/projects/{id}` | Project Detail |
| GET | `/projects/{id}/onboarding` | Onboarding Tab |
| POST | `/projects/{id}/onboarding/actions/start` | Start Onboarding |
| GET | `/projects/{id}/branches` | Branches Tab |
| POST | `/projects/{id}/branches/{branch}/delete` | Delete Branch |
| GET | `/projects/{id}/clarifications` | Clarifications Tab |
| POST | `/projects/{id}/clarifications/{key}` | Answer Clarification |
| GET | `/projects/{id}/policy` | Policy Tab |
| PUT | `/projects/{id}/policy` | Update Policy |
| GET | `/projects/{id}/policy/effective` | Effective Policy Preview |
| GET | `/projects/{id}/policy/findings` | Policy Findings |
| POST | `/projects/{id}/codemachine/import` | CodeMachine Import |

### Protocols

| Method | Endpoint | Feature |
|--------|----------|---------|
| GET | `/projects/{id}/protocols` | Protocols List |
| POST | `/projects/{id}/protocols` | Create Protocol |
| GET | `/protocols/{id}` | Protocol Detail |
| GET | `/protocols/{id}/steps` | Steps Tab |
| POST | `/protocols/{id}/steps` | Create Step |
| GET | `/protocols/{id}/events` | Events Tab |
| GET | `/protocols/{id}/runs` | Runs Tab |
| GET | `/protocols/{id}/spec` | Spec Tab |
| GET | `/protocols/{id}/clarifications` | Clarifications Tab |
| POST | `/protocols/{id}/clarifications/{key}` | Answer Clarification |
| GET | `/protocols/{id}/policy/findings` | Policy Findings |
| GET | `/protocols/{id}/policy/snapshot` | Policy Snapshot |
| POST | `/protocols/{id}/actions/start` | Start Protocol |
| POST | `/protocols/{id}/actions/pause` | Pause Protocol |
| POST | `/protocols/{id}/actions/resume` | Resume Protocol |
| POST | `/protocols/{id}/actions/cancel` | Cancel Protocol |
| POST | `/protocols/{id}/actions/run_next_step` | Run Next Step |
| POST | `/protocols/{id}/actions/retry_latest` | Retry Latest |
| POST | `/protocols/{id}/actions/open_pr` | Open PR |

### Steps

| Method | Endpoint | Feature |
|--------|----------|---------|
| POST | `/steps/{id}/actions/run` | Run Step |
| POST | `/steps/{id}/actions/run_qa` | Run QA |
| POST | `/steps/{id}/actions/approve` | Approve Step |
| GET | `/steps/{id}/runs` | Step Runs |
| GET | `/steps/{id}/policy/findings` | Step Policy Findings |

### Runs

| Method | Endpoint | Feature |
|--------|----------|---------|
| GET | `/codex/runs` | Runs Explorer |
| POST | `/codex/runs/start` | (internal) |
| GET | `/codex/runs/{runId}` | Run Detail |
| GET | `/codex/runs/{runId}/logs` | Run Logs |
| GET | `/codex/runs/{runId}/artifacts` | Run Artifacts |
| GET | `/codex/runs/{runId}/artifacts/{id}/content` | Artifact Content |

### Policy Packs

| Method | Endpoint | Feature |
|--------|----------|---------|
| GET | `/policy_packs` | Policy Packs List |
| POST | `/policy_packs` | Create/Update Pack |

### Operations

| Method | Endpoint | Feature |
|--------|----------|---------|
| GET | `/queues` | Queue Stats |
| GET | `/queues/jobs` | Queue Jobs |
| GET | `/events` | Recent Events |
| POST | `/specs/audit` | Trigger Spec Audit |

### Webhooks (not directly used by UI)

| Method | Endpoint | Notes |
|--------|----------|-------|
| POST | `/webhooks/github` | CI callback |
| POST | `/webhooks/gitlab` | CI callback |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-13 | Initial comprehensive architecture |
