# DevGodzilla Documentation Maintenance

> Status: Active
> Scope: Canonical documentation ownership, review triggers, and lightweight drift checks
> Source of truth: `README.md`, `docs/DevGodzilla/`, `scripts/docs_inventory.py`
> Last updated: 2026-04-20

## Canonical Active Set

The active contributor-facing documentation lives in `docs/DevGodzilla/` plus the repo `README.md`.

Use these docs first:

- `CURRENT_STATE.md`: runtime truth, local topology, active defaults
- `ARCHITECTURE.md`: system boundaries and lifecycle ownership
- `API-ARCHITECTURE.md`: cross-cutting API rules
- `API-REFERENCE.md`: route-domain reference
- `BACKEND-FLOWS.md`: end-to-end backend lifecycles
- `STATE-MODELS.md`: entity states, transitions, and artifact locations
- `SUBSYSTEMS.md`: service-domain contracts
- `OPERATIONS-OBSERVABILITY.md`: health, logs, events, metrics, reconciliation
- `FRONTEND-ARCHITECTURE.md`: console architecture and route groups
- `FRONTEND-WORKSPACES.md`: project and protocol workspaces
- `SPECKIT-AND-EXECUTION-JOURNEYS.md`: supported happy-path and manual flows
- `FRONTEND-API-CONTRACTS.md`: client, hooks, query keys, and realtime behavior
- `FRONTEND-COMPONENT-SYSTEM.md`: component taxonomy and extension points
- `WINDMILL-WORKFLOWS.md`: high-level Windmill integration overview
- `WINDMILL-CONTRACTS.md`: per-flow contracts
- `WINDMILL-OPERATIONS.md`: operator runbook
- `FRONTEND-TEST-MAP.md`: tests mapped to supported frontend behavior

## What Stays Archived

`docs/legacy/` and `docs/archive/` are preserved for historical context only.

Do not treat archived docs as authoritative when they conflict with:

1. runtime code and config
2. active docs in `docs/DevGodzilla/`
3. generated API schema from `/openapi.json`

## Review Triggers

Update active docs when any of these change:

- new FastAPI route modules, new route families, or auth changes in `devgodzilla/api/`
- status or lifecycle changes in `devgodzilla/models/domain.py` or related services
- new major service domains or ownership changes in `devgodzilla/services/`
- new project, protocol, run, Windmill, or realtime frontend surfaces in `frontend/app/`
- new shared hook families, query-key patterns, or websocket invalidation behavior in `frontend/lib/`
- new Windmill flows, scripts, or import/runtime behavior in `windmill/`

## Lightweight Drift Check

Run the inventory script before or during doc updates:

```bash
python3 scripts/docs_inventory.py
```

It reports current inventories for:

- API route modules and endpoint counts
- service modules
- frontend pages
- frontend hook files and exported hook counts
- Windmill flows and scripts

Use this output to verify that active docs still describe the current surface area.

## Contributor Checklist

When making a change that touches architecture or public behavior:

1. Update the relevant active doc in `docs/DevGodzilla/`.
2. Run `python3 scripts/docs_inventory.py`.
3. Confirm the root `README.md` and `docs/legacy/README.md` still point to the right canonical docs.
4. If a change is schema-only, rely on `/openapi.json` for field-level detail and update prose docs only for behavior, flow, or ownership changes.
