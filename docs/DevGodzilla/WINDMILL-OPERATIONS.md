# DevGodzilla Windmill Operations

> Status: Active
> Scope: Operator runbook for local Windmill bootstrap, inspection, import, and troubleshooting
> Source of truth: `docs/DevGodzilla/WINDMILL-WORKFLOWS.md`, `windmill/import_to_windmill.py`, `scripts/run-local-dev.sh`, `docker-compose*.yml`
> Last updated: 2026-04-20

## Summary

Windmill is the workflow runtime and companion operator UI. Operators use it to inspect flows and jobs, while the backend remains the source of truth for project, protocol, and step state.

## Local Bootstrap

Full Docker stack:

```bash
docker compose up --build -d
scripts/run-local-dev.sh import
```

Host-backed topology:

```bash
docker compose -f docker-compose.devgodzilla.yml up -d
scripts/run-local-dev.sh backend start
scripts/run-local-dev.sh frontend start
scripts/run-local-dev.sh import
```

Important note:

- `scripts/run-local-dev.sh up` uses `docker-compose.yml`, not `docker-compose.devgodzilla.yml`

## Required Configuration

Windmill integration depends on:

- `DEVGODZILLA_WINDMILL_URL`
- `DEVGODZILLA_WINDMILL_TOKEN`
- optional `DEVGODZILLA_WINDMILL_WORKSPACE`

Import helper expectations:

- local token/env file commonly lives at `windmill/apps/devgodzilla-react-app/.env.development`

## Primary Operator Surfaces

Use these in order:

- DevGodzilla console Windmill pages under `/console/windmill/*`
- backend `/flows*`, `/jobs*`, and `/reconciliation/*` endpoints
- Windmill native UI at `/`

The console is best for project-linked inspection. The native Windmill UI is best for raw flow/job debugging.

## Typical Playbooks

### Flow import or bootstrap issue

1. run `scripts/run-local-dev.sh import`
2. verify token/env configuration
3. inspect `windmill/import_to_windmill.py`
4. inspect imported flow and script visibility in Windmill UI

### Job appears stuck

1. inspect `/console/windmill/jobs`
2. inspect protocol or run pages in the DevGodzilla console
3. inspect backend `/jobs*` output and logs
4. inspect `/reconciliation/*` if DB and job state disagree

### Flow exists but protocol state is wrong

1. inspect protocol detail page
2. inspect flow/job surfaces
3. run reconciliation
4. inspect events and logs for the related protocol and step ids

## Current Operator Expectations

- Windmill scripts should remain thin API adapters
- backend lifecycle truth should still be visible without opening the native Windmill UI
- protocol-linked flow creation should be discoverable from the protocol workspace
- reconciliation is the last-mile repair tool when job and DB state drift apart

## Related Docs

- `WINDMILL-WORKFLOWS.md`
- `WINDMILL-CONTRACTS.md`
- `OPERATIONS-OBSERVABILITY.md`
