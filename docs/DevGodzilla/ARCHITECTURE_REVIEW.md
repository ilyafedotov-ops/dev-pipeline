# DevGodzilla Architecture Review (Solutions + Gaps + Roadmap)

Date: 2025-12-17

This document captures an end-to-end architecture review of the **DevGodzilla** stack in this repository, with focus on:
- DevGodzilla API + services architecture (`devgodzilla/`)
- Windmill integration (`windmill/` exports + `windmill_import`)
- Embedded React app approach (preferred UI)
- Security/ops best practices and missing pieces

## Implementation Status (As of 2025-12-18)

- SpecKit: **agent-assisted** (prompt-driven) and does **not** require an external `specify` binary (`devgodzilla/services/specification.py`).
- Windmill execution model: **standardized on API-wrapper scripts** for supported flows (see `docs/DevGodzilla/CURRENT_STATE.md`).
- Events/SSE: **DB-backed events table + SSE stream** (EventBus events are persisted; `/events` streams from DB).
- Auth/CORS: **configurable** via env (`DEVGODZILLA_API_TOKEN`, `DEVGODZILLA_CORS_ORIGINS`).
- Embedded app: `.env.example` is committed; `.env.development` remains local-only/ignored.

## Decisions (Confirmed)

1. **No legacy support for TasksGodzilla**
   - The DevGodzilla stack is the only supported runtime path.
   - Legacy TasksGodzilla artifacts may remain archived, but are not a supported deployment target.

2. **Preferred UI: embedded React app**
   - UI should be embedded/served in the Windmill context (or alongside it), but **must not expose Windmill tokens in the browser**.
   - Recommended data path: **Browser → DevGodzilla API → Windmill API** (server-side proxying).

3. **Windmill should be multi-language**
   - Multi-language features (including JavaScript `input_transforms`) are allowed/expected.
   - `WINDMILL_FEATURES` may include `deno_core` (Compose default already does).

## System Overview (Current Runtime)

### Docker Compose topology

The default stack runs:
- `nginx` reverse proxy (`nginx.devgodzilla.conf`)
- `devgodzilla-api` (FastAPI, `devgodzilla/api/app.py`)
- `windmill` server + workers (built from `Origins/Windmill`)
- `db` (Postgres)
- `windmill_import` one-shot bootstrap job to import assets (`windmill/import_to_windmill.py`)

See: `docker-compose.yml`, `DEPLOYMENT.md`, `README.md`.

### Core interaction model

- **DevGodzilla** owns:
  - project/protocol/step state in DB
  - services layer (`devgodzilla/services/*`) for planning/execution/QA/orchestration
  - safe public API surface via nginx

- **Windmill** owns:
  - workflow execution (flows/scripts) and job logs/results
  - the UI shell (served via nginx, with optional embedded DevGodzilla UI)

- **Asset import**:
  - flows under `windmill/flows/devgodzilla/` → `f/devgodzilla/*`
  - scripts under `windmill/scripts/devgodzilla/` → `u/devgodzilla/*`
  - apps under `windmill/apps/devgodzilla/`

## Strengths (What’s Working Well)

- Clear separation of concerns in code:
  - API routes are thin and mostly delegate to services (`devgodzilla/api/routes/*`, `devgodzilla/services/*`).
- Windmill integration exists in two useful modes:
  - API-driven scripts (`windmill/scripts/devgodzilla/*_api.py`) that call DevGodzilla API (portable, low coupling).
  - DevGodzilla-side Windmill API client (`devgodzilla/windmill/client.py`) for server-side orchestration/proxying.
- Stable operational entrypoint:
  - `windmill_import` produces a repeatable “bootstrap workspace assets” flow for local dev.

## Major Gaps / Mismatches (Highest Priority)

### 1) SpecKit integration: documentation vs implementation mismatch

Resolved: current SpecKit implementation is agent-assisted (prompt-driven) and does not call an external `specify` CLI.

**Why it matters**
- Deployment and reproducibility: the stack behavior differs depending on whether `specify` is installed in the runtime.
- UI expectations: API endpoints under `/speckit/*` and `/projects/{id}/speckit/*` may fail differently across environments.

**Recommendation**
- Document the “current behavior” and “target behavior” explicitly, and decide on one:
  - **Option A (recommended for packaging):** Python library integration (no external CLI required).
  - **Option B:** Keep CLI dependency, but make it first-class:
    - install it in the container image
    - add explicit health checks and clear error messages when missing
    - pin version and expose it in `/health/ready`

### 2) Windmill flow generation vs Windmill exported flows diverge

- Exported flows typically call API-wrapper scripts (`u/devgodzilla/step_execute_api`, `u/devgodzilla/step_run_qa_api`, etc.).
- DevGodzilla’s internal flow generator defaults to scripts that may import DevGodzilla directly (e.g. `u/devgodzilla/execute_step`, `u/devgodzilla/run_qa`).
- Orchestrator service queues `u/devgodzilla/plan_protocol` on Windmill, while planning is also available via DevGodzilla API background tasks.

**Why it matters**
- “Supported stack” ambiguity: flows may or may not work depending on whether Windmill workers have the DevGodzilla package available.
- Operator confusion: two different orchestration/control paths for the same lifecycle operations.

Resolved: supported flows use `*_api` adapter scripts; non-API scripts/flows are treated as deprecated/demo paths.

### 3) Embedded React app: security model must be explicit

There is an ignored local env file used for Windmill bootstrap tokens:
- `windmill/apps/devgodzilla-react-app/.env.development` (ignored by `.gitignore`)

**Why it matters**
- Embedded UI must never require browser access to Windmill tokens.
- Auth/CORS needs tightening when not purely local.

**Recommendation**
- Commit an `.env.example` (no secrets) and document:
  - which secrets are server-side only (Windmill token)
  - which values are safe for browser config (DevGodzilla API base URL)
- Ensure all “start run / view logs / view artifacts” UX flows through DevGodzilla endpoints, not direct Windmill API calls.

### 4) Authentication and CORS are currently “local dev” defaults

Resolved: CORS origins and API auth are now environment-configurable.

**Recommendation**
- Add a minimal auth layer for non-local environments:
  - bearer token or session auth
  - restrict CORS to configured origins
  - document “local dev mode” vs “staging/prod mode”

### 5) Events/SSE is not wired to service events

Resolved: service `EventBus` events are persisted to the DB `events` table and streamed from DB via SSE.

**Recommendation**
- Decide on one event architecture:
  - DB-backed events table + SSE streaming (recommended), or
  - Windmill job event streaming only (harder for UI to unify)
- Wire service lifecycle events (protocol/step/QA) into that store/stream.

## Windmill Best Practices (Recommended for This Repo)

### Preferred pattern: Windmill scripts are API adapters

**Do**
- Keep Windmill scripts small and stable:
  - validate inputs
  - call DevGodzilla API
  - return structured JSON for apps/flows
- Use Windmill for scheduling/parallelism/visibility, and DevGodzilla for policy/decision-making.

**Avoid**
- Importing `devgodzilla` in Windmill scripts unless the Windmill worker image is explicitly built to include it (and documented as such).

### Multi-language flow hygiene

- JavaScript `input_transforms` are allowed (multi-language requirement), but keep them:
  - minimal and deterministic (pure mapping, not business logic)
  - easy to remove/port if build complexity becomes painful

### Observability / correlation

Target a single correlation model:
- A DevGodzilla “run” references a Windmill `job_id` where applicable.
- UI can fetch:
  - normalized run status
  - normalized logs (proxying Windmill logs)
  - artifacts (filesystem artifacts + Windmill result refs where needed)

## Feature Roadmap (Suggested Order)

### P0 — Convergence + correctness (reduce split-brain)
- Add `docs/DevGodzilla/CURRENT_STATE.md` (or update `ARCHITECTURE.md`) to explicitly describe “what runs today”.
- Pick one SpecKit approach (library vs CLI) and update docs + Docker image accordingly.
- Standardize Windmill execution to API-wrapper scripts and align:
  - DevGodzilla orchestrator defaults
  - DevGodzilla flow generator defaults
  - exported flows

### P1 — Embedded React app integration (secure by design)
- Define a UI-safe API contract (runs, logs, artifacts, events).
- Ensure DevGodzilla is the only component that holds Windmill tokens.
- Add basic auth and tighten CORS for non-local deployments.
- Replace in-memory SSE with persisted events streaming.

### P2 — Product capabilities
- “Run protocol until blocked/completed” as a first-class operation.
- Policy-driven gating and clarifications wired end-to-end (planning → execution → QA).
- First-class “QA report” artifacts per step/protocol in UI.

## Appendix: Key Files

- DevGodzilla API: `devgodzilla/api/app.py`
- DevGodzilla services: `devgodzilla/services/`
- Windmill assets: `windmill/flows/devgodzilla/`, `windmill/scripts/devgodzilla/`, `windmill/apps/devgodzilla/`
- Windmill import: `windmill/import_to_windmill.py`
- Deployment: `docker-compose.yml`, `DEPLOYMENT.md`, `nginx.devgodzilla.conf`
