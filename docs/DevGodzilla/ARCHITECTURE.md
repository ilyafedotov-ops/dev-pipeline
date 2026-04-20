# DevGodzilla Architecture

> Status: Active
> Scope: Current implemented architecture with a small target-state section
> Source of truth: `docs/DevGodzilla/CURRENT_STATE.md`, `devgodzilla/`, `frontend/`, `windmill/`, `docker-compose*.yml`, `nginx*.conf`
> Last updated: 2026-04-20

## Summary

DevGodzilla in this repo is a layered system:

1. Edge and routing (`nginx.devgodzilla.conf` and `nginx.local.conf`)
2. UI layer (`frontend/` Next.js console plus Windmill UI)
3. API layer (`devgodzilla/api/`)
4. Service layer (`devgodzilla/services/`)
5. Engine layer (`devgodzilla/engines/`)
6. Data and integration layer (Postgres, Redis, Windmill, filesystem, local project workspaces)

## Current Architecture

### Full Docker topology

```text
Browser
  -> nginx (:8080)
     -> /console, /_next ............ frontend container (:3000)
     -> /api/v1/* and legacy roots .. devgodzilla-api container (:8000)
     -> / ........................... windmill container (:8000)
```

### Host-backed topology

```text
Browser
  -> nginx (:8080)
     -> /console, /_next ............ host frontend (:3000)
     -> /api/v1/* and legacy roots .. host backend (:8000)
     -> / ........................... windmill container (:8000)
```

The repo contains config for both topologies. The default compose startup path is the full Docker topology.

## Layer Responsibilities

### Startup and lifespan responsibilities

FastAPI startup in `devgodzilla/api/app.py` currently does more than router registration. During startup the app:

- bootstraps default engines
- initializes DB schema access
- installs the DB event sink when available
- migrates YAML-backed agent defaults into DB-backed state
- recovers stuck protocols through the orchestrator
- registers sprint event handlers
- validates the path contract
- initializes telemetry and FastAPI instrumentation

When architecture docs and runtime logs disagree, trust the startup behavior in `app.py`.

### 1. Edge and Routing

- `nginx.devgodzilla.conf` proxies to containerized backend/frontend services.
- `nginx.local.conf` proxies to backend/frontend on `host.docker.internal`.
- Both configurations route Windmill UI at `/` and DevGodzilla API/console traffic on explicit prefixes.

### 2. UI Layer

- Primary product console: `frontend/`
- Framework: Next.js App Router with `basePath: "/console"`
- Current major route families: projects, protocols, specifications, steps, runs, execution, executions, clarifications, quality, ops, policy packs, templates, agents, settings, Windmill views
- Windmill UI remains available as an operator-facing companion interface at the site root

### 3. API Layer

- FastAPI app: `devgodzilla/api/app.py`
- Route modules: `devgodzilla/api/routes/*.py`
- Most routers are mounted twice: canonical `/api/v1/*` plus deprecated root-level compatibility routes
- Auth model is mixed by route type: API token for most operational routes, webhook token for webhook endpoints, JWT/session-oriented auth for `/auth/*` and `/users/*`, and unauthenticated WebSocket access for `/ws/events`

### 4. Service Layer

Implemented service modules include:

- orchestration and planning: `orchestrator.py`, `planning.py`, `protocol_generation.py`, `spec_to_protocol.py`, `task_cycle.py`
- execution and QA: `execution.py`, `quality.py`, `retry_config.py`, `cli_execution_tracker.py`
- project/spec flows: `specification.py`, `discovery_agent.py`, `speckit_adapter.py`, `clarifier.py`, `template_manager.py`
- coordination and persistence: `event_persistence.py`, `events.py`, `reconciliation.py`, `onboarding_queue.py`, `sprint_integration.py`, `task_sync.py`
- platform services: `agent_config.py`, `git.py`, `health.py`, `telemetry.py`, `path_contract.py`, `workspace_paths.py`, `worktree.py`

### 5. Engine Layer

Engine adapters live under `devgodzilla/engines/`.

Currently configured defaults are in `devgodzilla/config/agents.yaml`, with `opencode` as the default CLI-backed engine. The codebase also contains adapters for several additional CLI/API-backed engines used by tests, experiments, and per-project configuration.

### 6. Data and Integrations

- DB access: `devgodzilla/db/`
- Alembic migrations: `devgodzilla/alembic/`
- Windmill client/runtime helpers: `devgodzilla/windmill/`
- Windmill exported assets: `windmill/scripts/devgodzilla/`, `windmill/flows/devgodzilla/`, `windmill/apps/devgodzilla/`, `windmill/resources/devgodzilla/`
- Project workspaces and generated artifacts: `projects/`, `.protocols/`, `.specify/`, `runs/`

## Current Constraints and Known Leftovers

- Some generated discovery artifacts still use `tasksgodzilla/*` names for compatibility.
- The repo contains both full-Docker and host-backed runtime assets; documentation must name the exact compose/nginx pair being discussed.
- API naming intentionally mixes underscore API paths such as `/policy_packs` with hyphenated frontend slugs such as `/console/policy-packs`.

## Target Notes

These are directional and should not be read as implemented work:

- automated route/doc drift checks in CI
- stronger internal service contracts around protocol artifacts and event streams
- broader observability correlation across API, Windmill jobs, and local artifact lineage

## Documentation Governance

When docs conflict, use this order:

1. Runtime code and config (`devgodzilla/api/app.py`, route modules, compose files, nginx configs)
2. `docs/DevGodzilla/CURRENT_STATE.md`
3. Other active docs under `docs/DevGodzilla/`
4. Archived docs under `docs/legacy/`

## Related Docs

- `API-ARCHITECTURE.md`
- `BACKEND-FLOWS.md`
- `SUBSYSTEMS.md`
- `FRONTEND-ARCHITECTURE.md`
