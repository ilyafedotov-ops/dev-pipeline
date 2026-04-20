# DevGodzilla Frontend API Contracts

> Status: Active
> Scope: Shared frontend client behavior, headers, query keys, hooks, adapters, and realtime invalidation
> Source of truth: `frontend/lib/api/client.ts`, `frontend/lib/api/query-keys.ts`, `frontend/lib/api/hooks/`, `frontend/lib/api/adapters/`, `frontend/lib/websocket/`
> Last updated: 2026-04-20

## Summary

The frontend data layer is intentionally thin:

- one shared `apiClient`
- typed hook families per backend domain
- explicit query-key factory
- websocket events used to invalidate query caches

The frontend does not own a duplicate domain store. Backend state remains authoritative.

## apiClient Behavior

`frontend/lib/api/client.ts` is the shared transport layer.

Current behavior:

- default browser base URL is `/api/v1`
- SSR/default fallback can use `NEXT_PUBLIC_API_BASE_URL` or `http://localhost:8000/api/v1`
- persists API base, token, and project tokens in local storage
- sends `Authorization: Bearer <token>` when configured
- sends `X-Project-Token` when a project-scoped token exists
- sends `X-Request-ID` on every request
- retries retryable failures with exponential backoff and jitter

Client errors are generally not retried, except for explicitly retryable statuses such as `429`.

## Error Model

Shared error type:

- `ApiError`

Error categories exposed by the client:

- `unauthorized`
- `forbidden`
- `not_found`
- `conflict`
- `validation`
- `server_error`
- `network_error`

Pages and hooks should treat `ApiError` as the standard backend failure surface.

## Query Keys

`frontend/lib/api/query-keys.ts` is the cache identity source of truth.

Important rule:

- add query keys before wiring new hooks or websocket invalidation paths

Current query-key families include:

- projects
- protocols
- steps
- runs
- policy packs
- ops
- events
- sprints
- tasks
- agents
- clarifications
- specifications
- speckit
- quality
- profile
- users

## Hook Families

Shared domain hooks live in `frontend/lib/api/hooks/`.

Current families include:

- projects and onboarding
- protocols
- steps
- runs
- quality
- clarifications and feedback
- agents
- policy packs
- specs and SpecKit
- ops, events, logs, queues
- reconciliation
- Windmill flows and jobs

Pattern:

1. hook defines the backend call
2. hook chooses the query key
3. mutations invalidate or refresh affected keys
4. page or component composes hooks rather than building ad hoc fetch logic

## Adapters And Types

Shared type surface:

- `frontend/lib/api/types.ts`
- `frontend/lib/api/types/cli-executions.ts`

Adapters exist for places where backend shape needs frontend normalization, especially around protocol-oriented responses.

Rule of thumb:

- keep raw transport and shared types in `lib/api`
- keep presentational reshaping in adapters or page-level composition

## Realtime Invalidation

Realtime support is websocket-driven.

Current pattern:

- `WebSocketProvider` connects to `/api/v1/ws/events`
- pages subscribe to channels such as `protocol:<id>` or `step:<id>`
- `useWebSocketEvent()` invalidates affected query keys
- TanStack Query refetches the latest backend truth

This is the preferred pattern for execution-heavy pages such as protocol detail, not direct mutation of local caches from socket payloads.

## Provider Contract

The app-wide provider stack guarantees:

- a shared query client
- auth context
- websocket connectivity
- toast notifications

Feature code should rely on those shared providers instead of creating local fetch or websocket infrastructure.

## Contributor Guidance

When adding new backend consumption:

1. add or reuse a query key
2. add a typed hook
3. use `apiClient`
4. wire websocket invalidation only if the surface needs realtime freshness
5. add an adapter only when the backend shape needs stable frontend normalization

## Related Docs

- `FRONTEND-ARCHITECTURE.md`
- `STATE-MODELS.md`
- `API-REFERENCE.md`
