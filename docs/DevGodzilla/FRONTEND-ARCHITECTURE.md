# DevGodzilla Frontend Architecture

> Status: Active
> Scope: Next.js console architecture, route groups, providers, navigation, and realtime integration
> Source of truth: `frontend/app/`, `frontend/components/layout/`, `frontend/components/providers.tsx`, `frontend/lib/api/`, `frontend/lib/websocket/`, `frontend/next.config.mjs`
> Last updated: 2026-04-20

## Summary

The active UI is the Next.js console under `frontend/`, mounted at `/console`.

The frontend is responsible for:

- contributor-facing navigation across projects, protocols, runs, quality, and operations
- typed access to the FastAPI backend under `/api/v1/*`
- realtime refresh via `/ws/events`
- drill-down into Windmill flows, jobs, and reconciliation without replacing the backend as the source of truth

Windmill's own UI still lives at `/`, but the primary product UI in this repo is the Next.js console.

## Application Shell

Core shell layers:

- App Router pages under `frontend/app/`
- shared providers in `frontend/components/providers.tsx`
- layout shell in `frontend/components/layout/`
- shared UI primitives in `frontend/components/ui/`

Provider stack:

1. `QueryClientProvider`
2. `ThemeProvider`
3. `AuthProvider`
4. `WebSocketProvider`
5. toaster notifications

This means route components normally assume TanStack Query, auth context, and websocket subscriptions are available without page-level wiring.

## Navigation Model

The sidebar is grouped into five operator/contributor clusters:

- Workspace
- Execute
- Automation
- Windmill
- Operations

Current top-level navigation emphasizes:

- project and protocol work
- runs and execution
- quality and policy
- Windmill inspection
- queue, event, log, and metrics pages

Recent projects are also surfaced directly from the sidebar via `useProjects()`.

## Route Groups

Major route families under `frontend/app/`:

- dashboard: `/`
- projects: `/projects`, `/projects/[id]`, and project-scoped flows such as `/branches`, `/constitution`, `/design-solution`, `/execution`, `/generate-specs`, `/implement-feature`, `/onboarding`, `/policy`, `/protocols`, and `/sprint-board`
- protocols: `/protocols`, `/protocols/[id]`, and drill-down pages such as `/steps`, `/runs`, `/events`, `/spec`, `/policy`, and `/clarifications`
- specifications: `/specifications`, `/specifications/[id]`
- steps: `/steps`, `/steps/[id]`
- runs: `/runs`, `/runs/[runId]`
- execution surfaces: `/execution`, `/executions`, `/clarifications`, `/quality`
- ops pages: `/ops/events`, `/ops/logs`, `/ops/metrics`, `/ops/queues`
- policy packs, agents, templates, profile, settings, login
- Windmill pages: `/windmill`, `/windmill/flows`, `/windmill/flows/[flowPath]`, `/windmill/jobs`, `/windmill/jobs/[jobId]`, `/windmill/reconciliation`

The frontend uses route groups for product structure, but the most important contributor work happens in the project and protocol workspaces.

## Data And State Model

The frontend is backend-driven:

- API calls go through `frontend/lib/api/client.ts`
- typed hooks live in `frontend/lib/api/hooks/`
- query invalidation is organized through `frontend/lib/api/query-keys.ts`
- lightweight adapters normalize backend response shapes where needed

Common pattern:

1. page or composite component calls a domain hook
2. hook uses the shared `apiClient`
3. TanStack Query manages caching and background refetch
4. websocket events invalidate relevant query keys

## Realtime Model

Realtime updates are implemented with the shared `WebSocketProvider` targeting `/api/v1/ws/events`.

The frontend does not try to mirror backend state in a permanent client store. Instead it:

- subscribes to channels such as `protocol:<id>` or `step:<id>`
- invalidates query keys when relevant events arrive
- lets TanStack Query refetch the current truth from the backend

This keeps pages eventually consistent with backend state without inventing a separate client-owned workflow model.

## Relationship To Windmill

The frontend treats Windmill as an execution/runtime companion, not as the primary app shell.

Current Windmill-related responsibilities in the console:

- inspect flow inventory and details
- inspect job runs and logs
- expose reconciliation surfaces
- create protocol-linked flows from protocol detail pages

The frontend does not embed Windmill internals into its own domain model. It reads backend Windmill passthrough routes and renders them alongside project and protocol views.

## Contributor Guidance

When adding a new UI surface:

- put product routes under `frontend/app/`
- add or extend a domain hook in `frontend/lib/api/hooks/`
- add query keys before wiring invalidation
- prefer composites in `components/features/`, `components/workflow/`, `components/agile/`, or `components/wizards/`
- keep `components/ui/` for reusable primitives, not backend-specific logic

## Related Docs

- `FRONTEND-WORKSPACES.md`
- `FRONTEND-API-CONTRACTS.md`
- `FRONTEND-COMPONENT-SYSTEM.md`
- `WINDMILL-CONTRACTS.md`
