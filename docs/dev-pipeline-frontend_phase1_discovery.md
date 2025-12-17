# Phase 1 Discovery: `dev-pipeline-frontend` (MVP Console)

Repo cloned to: `./dev-pipeline-frontend`  
Upstream: `https://github.com/ilyafedotov-ops/dev-pipeline-frontend`  
HEAD: `307dfbc5c1f4780ed590d23e3c791158849e0239`

## How to run locally
```bash
cd dev-pipeline-frontend
pnpm install
pnpm dev --port 3006
```

Notes:
- By default the UI runs in **Mock Mode** (demo data). Toggle via `Settings → Demo Mode`.
- Real API connection is configured in-browser in `Settings → API Configuration` (stored in `localStorage`).

## Tech stack & architecture
- Framework: Next.js App Router (`app/`), Next `16.0.10` (Turbopack), React `19.2.0`.
- Styling/UI: Tailwind CSS v4, Radix UI primitives + shadcn-like components under `components/ui/*`.
- Data fetching/state: `@tanstack/react-query` hooks under `lib/api/hooks/*`.

### Runtime configuration & auth
- API client: `dev-pipeline-frontend/lib/api/client.ts`
  - `localStorage` key: `tasksgodzilla_config`
  - fields: `apiBase`, `token`, `projectTokens`
  - default `apiBase`: `http://localhost:8011`
  - headers:
    - `Authorization: Bearer <token>` (if configured)
    - `X-Project-Token: <token>` (if configured per project)
    - `X-Request-ID: <uuid>`
- Mock Mode:
  - enabled by default in browser (`apiClient.setMockMode(true)` on load)
  - can be toggled in `dev-pipeline-frontend/app/settings/page.tsx`
  - fallback behavior: if an API request errors, client may switch to mock mode (“API unavailable, using mock data”).
- Auth:
  - `AuthProvider` + `AuthGuard` exist (`dev-pipeline-frontend/lib/auth/*`) but the guard is **not** applied in `app/layout.tsx`.
  - `/login` is a demo login; `/api/auth/*` routes are mock implementations (cookie session placeholder).

## Frontend → API contract (what the UI calls today)
All calls are made via `apiClient` (unless Mock Mode is enabled).

### Health / Ops
- `GET /health` (Settings connection status)
- `GET /queues` (Ops → Queues)
- `GET /queues/jobs?status=...` (Ops → Queues)
- `GET /events?project_id&protocol_run_id&kind&spec_hash&limit` (Ops → Events)

### Projects
- `GET /projects` (Dashboard, Projects, Ops filters)
- `POST /projects` (hook exists; UI wizard currently mostly mock)
- `GET /projects/{id}` (Project detail, wrapper pages)
- `GET /projects/{id}/protocols` (Project → Protocols tab)
- `GET /projects/{id}/onboarding` (Project → Onboarding tab)
- `POST /projects/{id}/onboarding/actions/start` (Start onboarding)
- `GET /projects/{id}/policy` (Project → Policy tab)
- `PUT /projects/{id}/policy` (Update policy)
- `GET /projects/{id}/policy/effective` (Effective policy)
- `GET /projects/{id}/policy/findings` (Policy findings)
- `GET /projects/{id}/clarifications?status=...` (Project clarifications)
- `POST /projects/{id}/clarifications/{key}` body `{ "answer": "..." }` (Answer clarification)
- `GET /projects/{id}/branches` (Branches tab)
- `POST /projects/{id}/branches/{branch}/delete` (Delete branch)

### Protocols
- `GET /protocols` (Protocols list page)
- `GET /protocols/{id}` (Protocol detail, wrapper pages)
- `POST /projects/{projectId}/protocols` body `ProtocolCreate` (Create protocol from Project page)
- `GET /protocols/{id}/steps` (Protocol steps)
- `GET /protocols/{id}/events` (Protocol events)
- `GET /protocols/{id}/runs?job_type&status&run_kind&limit` (Protocol runs)
- `GET /protocols/{id}/spec` (Spec tab)
- `GET /protocols/{id}/policy/findings` (Protocol policy findings)
- `GET /protocols/{id}/policy/snapshot` (Policy snapshot)
- `GET /protocols/{id}/clarifications?status=...` (Protocol clarifications)
- `POST /protocols/{id}/clarifications/{key}` body `{ "answer": "..." }` (Answer clarification)
- `POST /protocols/{id}/actions/{action}` where action ∈ `start|pause|resume|cancel|run_next_step|retry_latest|open_pr`

### Steps
- `GET /steps/{id}/runs` (Step runs)
- `GET /steps/{id}/policy/findings` (Step policy findings)
- `POST /steps/{id}/actions/{action}` where action ∈ `run|run_qa|approve`

### Runs (Codex)
- `GET /codex/runs?job_type&status&run_kind&project_id&protocol_run_id&step_run_id&limit` (Runs explorer, Dashboard)
- `GET /codex/runs/{runId}` (Run detail + wrapper pages)
- `GET /codex/runs/{runId}/logs` (Run detail → Logs tab)
- `GET /codex/runs/{runId}/artifacts` (Run detail → Artifacts tab; Run artifacts page)

Important gaps:
- The Run Artifacts page tries to download content via `window.open("/api/codex/runs/{runId}/artifacts/{id}/content")`,
  but there is **no** `app/api/codex/*` route in the frontend repo today. This will need to be implemented or changed
  to hit the real backend API host.
- Streaming logs UI (`dev-pipeline-frontend/components/features/streaming-logs.tsx`) is currently mock; it expects an SSE
  endpoint like `/api/codex/runs/{runId}/logs/stream` in production.

### Policy packs
- `GET /policy_packs` (Policy packs page + detail page lookup)
- `POST /policy_packs` (Create policy pack)

## Route map (screens → data needs → API calls)
### Primary (non-mock) screens
- `/` Dashboard → projects/protocols/runs summary → `GET /projects`, `GET /protocols`, `GET /codex/runs`
- `/projects` → projects list → `GET /projects`
- `/projects/[id]` → project + onboarding + protocols → `GET /projects/{id}`, `GET /projects/{id}/onboarding`, `GET /projects/{id}/protocols`
- `/projects/[id]/*` (protocols/policy/branches/clarifications/onboarding wrappers) → same as corresponding tab hooks
- `/protocols` → all protocols → `GET /protocols` (note: UI has some field-name mismatches; see below)
- `/protocols/[id]` + `/protocols/[id]/*` → protocol + steps/events/runs/spec/policy/clarifications + actions
- `/steps/[id]` → step runs/policy + actions → `GET /steps/{id}/runs`, `GET /steps/{id}/policy/findings`, `POST /steps/{id}/actions/*`
- `/runs` → run list → `GET /codex/runs`
- `/runs/[runId]` → run detail + logs + artifacts → `GET /codex/runs/{runId}`, `GET /codex/runs/{runId}/logs`, `GET /codex/runs/{runId}/artifacts`
- `/ops/queues` → queues + jobs → `GET /queues`, `GET /queues/jobs`
- `/ops/events` → events timeline + project filter → `GET /events`, `GET /projects`
- `/settings` → health check + client config → `GET /health`
- `/policy-packs` → policy packs list/create → `GET /policy_packs`, `POST /policy_packs`

### Currently mock-only screens (no real API contract yet)
- `/agents`, `/quality`, `/specifications`, `/specifications/[id]` (hardcoded demo data)
- “Generate specs / implement feature / design solution” flows under `/projects/[id]/*` are UI-only stubs today.

## Notable mismatches / cleanup candidates (before wiring to Devgodzilla/Windmill)
- `dev-pipeline-frontend/app/protocols/page.tsx` references fields like `protocol.name`, `protocol.branch`, `step_index`,
  but the shared `ProtocolRun` type uses `protocol_name`, `base_branch`, etc. Next is configured with
  `typescript.ignoreBuildErrors: true`, so this currently builds, but we should align the fields before relying on it.
- The mock-response handler in `dev-pipeline-frontend/lib/api/client.ts` contains a few shape mismatches
  (example: filtering runs by `step_id` vs `step_run_id`), which can confuse discovery/debugging if Mock Mode is used.

## Phase 1 deliverable summary
The MVP console already has a clear data layer (`lib/api/*`) and a consistent set of hooks; wiring to Devgodzilla/Windmill
is primarily about:
1) matching/proxying the endpoints above (recommended: frontend → Devgodzilla API → Windmill), and
2) implementing missing “logs streaming” and “artifact content download” endpoints.

