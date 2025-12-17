# Devgodzilla Frontend ↔ Windmill Integration Plan

## Goal
Wire the MVP React UI in `dev-pipeline-frontend` to “devgodzilla Windmill” so users can: start runs, watch status/logs, and view outputs/artifacts—without exposing Windmill secrets in the browser.

## Key Decision (do this first)
### A) Recommended: Frontend → Devgodzilla API (FastAPI) → Windmill
- Pros: keeps Windmill token server-side, consistent auth, avoids CORS/token leakage, easier auditing.
- Cons: may require adding a few proxy endpoints in the API if they don’t exist yet.

### B) Direct: Frontend → Windmill API
- Pros: fastest if you accept a public token.
- Cons: insecure (browser token), CORS headaches, harder auth.

Proceed with **A** unless you explicitly choose **B**.

## Detailed Plan

### Phase 0 — Inputs needed (blocking)
1. Windmill connection details
   - `WINDMILL_BASE_URL` (e.g. `https://windmill.mycorp.com`)
   - Workspace/tenant name
   - Auth method: service token, OAuth, SSO, etc.
   - Which Windmill “scripts/flows” map to Devgodzilla actions (names/paths)
2. Devgodzilla API details (if it already exists)
   - API base URL for dev/staging
   - Auth: cookie session vs bearer token, and how login happens
   - Any existing endpoints for “runs/jobs/logs/artifacts” (OpenAPI link if available)

### Phase 1 — Repo discovery + run locally
1. Clone `https://github.com/ilyafedotov-ops/dev-pipeline-frontend` into the workspace (or as sibling).
2. Install deps, run the dev server, and inventory:
   - routes/pages/components
   - current mocked data / placeholder services
   - state management (Redux/Zustand/Context) and data fetching patterns
   - where “run” objects, logs, and artifacts should live in UI

Deliverable: a short mapping doc: “screen → data required → API call”.

### Phase 2 — Define the integration contract (UI-facing)
Design the minimal UI API (either already present in Devgodzilla, or added to it):
- `POST /runs` (start run; parameters include repo, branch, options)
- `GET /runs?…` (list runs)
- `GET /runs/{id}` (run detail + current state)
- `GET /runs/{id}/events` (SSE stream for status/log lines) OR `GET /runs/{id}/logs` (poll)
- `GET /runs/{id}/artifacts` (outputs: links/files/metadata)

If using Windmill under the hood, the API maps these to Windmill run IDs and normalizes states.

Deliverable: concrete request/response JSON shapes + error codes used by the UI.

### Phase 3 — Backend wiring (only if needed)
If Devgodzilla doesn’t already expose a safe UI API:
1. Add config/env for Windmill (server-side only).
2. Implement a Windmill client wrapper (timeouts/retries, typed responses).
3. Implement the proxy endpoints above:
   - trigger Windmill run
   - translate Windmill status → UI status (`queued/running/succeeded/failed/canceled`)
   - stream logs (best: SSE) or provide polling endpoints
4. Add tests for the proxy layer.

Deliverable: UI-safe API with stable contract; no Windmill secrets in frontend.

### Phase 4 — Frontend data layer
1. Add environment config (`VITE_API_BASE_URL`, etc.).
2. Implement a typed API client (fetch/axios) + standardized error handling.
3. Add React Query (or match existing pattern) for:
   - list runs
   - run detail
   - start run mutation
   - logs/events subscription (SSE or polling)
4. Add auth handling (attach token/cookie, 401 redirect).

Deliverable: `src/api/*` (or equivalent) powering real data with loading/error states.

### Phase 5 — Wire UI screens end-to-end
For each screen in the MVP design:
1. Replace mocks with real queries/mutations.
2. Ensure UX states:
   - empty state
   - loading skeletons
   - retry on failure
   - “run in progress” with live updates
3. Artifacts UX: download links, copy-to-clipboard, etc.

Deliverable: user can start a run and watch it complete.

### Phase 6 — Hardening + developer experience
1. Add minimal tests (API client unit tests + a couple component tests).
2. Add `.env.example` and README “How to run locally”.
3. Validate build (`npm run build`) and ensure no secrets bundled.
4. Optional: e2e smoke test (Playwright) if the repo already uses it.

### Phase 7 — Deployment wiring
1. Decide where it’s hosted (Vercel, Docker, static behind nginx).
2. Provide env var matrix for dev/staging/prod.
3. Verify CORS/cookies if API uses session auth.

## Questions to unblock
1. Windmill base URL + workspace name?
2. Do you want **Frontend → Devgodzilla API → Windmill** (recommended) or direct-to-Windmill?
3. What are the top 3 user actions the UI must support in MVP (e.g., “start protocol run”, “view logs”, “download artifact”)?
4. Is there already a Devgodzilla API endpoint spec (OpenAPI URL) to match?

