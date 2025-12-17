# Phase 2: Frontend → Existing API Mapping (dev-pipeline)

This mapping is based on Phase 1 discovery of `dev-pipeline-frontend` and the existing FastAPI implementation in this repo.

## Primary API to target
The Next.js MVP calls a REST API that is already implemented end-to-end by:
- `tasksgodzilla/api/app.py` (FastAPI “TasksGodzilla Orchestrator API”)

The `devgodzilla/api/*` service in this repo is a separate API optimized for the Windmill-native console app under `windmill/apps/devgodzilla-react-app/` and uses different endpoints/shapes.

For the MVP console (`dev-pipeline-frontend`) the shortest path is to wire it to the **TasksGodzilla API** and then add **Windmill-backed proxies** for run logs + artifact content where needed.

## Mapping: Frontend calls → Existing API routes

### Health / Ops
- Frontend `GET /health` → `tasksgodzilla/api/app.py` `GET /health`
- Frontend `GET /queues` → `tasksgodzilla/api/app.py` `GET /queues`
- Frontend `GET /queues/jobs?status=...` → `tasksgodzilla/api/app.py` `GET /queues/jobs`
- Frontend `GET /events?...` (list) → `tasksgodzilla/api/app.py` `GET /events` (JSON list; distinct from DevGodzilla SSE `/events`)

### Projects
- Frontend `GET /projects` → `tasksgodzilla/api/app.py` `GET /projects`
- Frontend `POST /projects` → `tasksgodzilla/api/app.py` `POST /projects`
- Frontend `GET /projects/{id}` → `tasksgodzilla/api/app.py` `GET /projects/{project_id}`
- Frontend `GET /projects/{id}/protocols` → `tasksgodzilla/api/app.py` `GET /projects/{project_id}/protocols`
- Frontend `POST /projects/{id}/protocols` → `tasksgodzilla/api/app.py` `POST /projects/{project_id}/protocols`
- Frontend `GET /projects/{id}/onboarding` → `tasksgodzilla/api/app.py` `GET /projects/{project_id}/onboarding`
- Frontend `POST /projects/{id}/onboarding/actions/start` → `tasksgodzilla/api/app.py` `POST /projects/{project_id}/onboarding/actions/start`
- Frontend `GET /projects/{id}/policy` → `tasksgodzilla/api/app.py` `GET /projects/{project_id}/policy`
- Frontend `PUT /projects/{id}/policy` → `tasksgodzilla/api/app.py` `PUT /projects/{project_id}/policy`
- Frontend `GET /projects/{id}/policy/effective` → `tasksgodzilla/api/app.py` `GET /projects/{project_id}/policy/effective`
- Frontend `GET /projects/{id}/policy/findings` → `tasksgodzilla/api/app.py` `GET /projects/{project_id}/policy/findings`
- Frontend `GET /projects/{id}/clarifications?status=...` → `tasksgodzilla/api/app.py` `GET /projects/{project_id}/clarifications`
- Frontend `POST /projects/{id}/clarifications/{key}` → `tasksgodzilla/api/app.py` `POST /projects/{project_id}/clarifications/{key}`
- Frontend `GET /projects/{id}/branches` → `tasksgodzilla/api/app.py` `GET /projects/{project_id}/branches`
- Frontend `POST /projects/{id}/branches/{branch}/delete` → `tasksgodzilla/api/app.py` `POST /projects/{project_id}/branches/{branch:path}/delete`

### Protocols
- Frontend `GET /protocols` → `tasksgodzilla/api/app.py` `GET /protocols`
- Frontend `GET /protocols/{id}` → `tasksgodzilla/api/app.py` `GET /protocols/{protocol_run_id}`
- Frontend `GET /protocols/{id}/steps` → `tasksgodzilla/api/app.py` `GET /protocols/{protocol_run_id}/steps`
- Frontend `GET /protocols/{id}/events` → `tasksgodzilla/api/app.py` `GET /protocols/{protocol_run_id}/events`
- Frontend `GET /protocols/{id}/runs?...` → `tasksgodzilla/api/app.py` `GET /protocols/{protocol_run_id}/runs`
- Frontend `GET /protocols/{id}/spec` → `tasksgodzilla/api/app.py` `GET /protocols/{protocol_run_id}/spec`
- Frontend `GET /protocols/{id}/policy/findings` → `tasksgodzilla/api/app.py` `GET /protocols/{protocol_run_id}/policy/findings`
- Frontend `GET /protocols/{id}/policy/snapshot` → `tasksgodzilla/api/app.py` `GET /protocols/{protocol_run_id}/policy/snapshot`
- Frontend `GET /protocols/{id}/clarifications?status=...` → `tasksgodzilla/api/app.py` `GET /protocols/{protocol_run_id}/clarifications`
- Frontend `POST /protocols/{id}/clarifications/{key}` → `tasksgodzilla/api/app.py` `POST /protocols/{protocol_run_id}/clarifications/{key}`
- Frontend actions:
  - `POST /protocols/{id}/actions/start` → implemented
  - `POST /protocols/{id}/actions/pause` → implemented
  - `POST /protocols/{id}/actions/resume` → implemented
  - `POST /protocols/{id}/actions/cancel` → implemented
  - `POST /protocols/{id}/actions/run_next_step` → implemented
  - `POST /protocols/{id}/actions/retry_latest` → implemented
  - `POST /protocols/{id}/actions/open_pr` → implemented

### Steps
- Frontend `GET /steps/{id}/runs` → `tasksgodzilla/api/app.py` `GET /steps/{step_run_id}/runs`
- Frontend `GET /steps/{id}/policy/findings` → `tasksgodzilla/api/app.py` `GET /steps/{step_id}/policy/findings`
- Frontend actions:
  - `POST /steps/{id}/actions/run` → implemented
  - `POST /steps/{id}/actions/run_qa` → implemented
  - `POST /steps/{id}/actions/approve` → implemented

### Runs (Codex)
- Frontend `GET /codex/runs?...` → `tasksgodzilla/api/app.py` `GET /codex/runs`
- Frontend `GET /codex/runs/{runId}` → `tasksgodzilla/api/app.py` `GET /codex/runs/{run_id}`
- Frontend `GET /codex/runs/{runId}/logs` → `tasksgodzilla/api/app.py` `GET /codex/runs/{run_id}/logs`
- Frontend `GET /codex/runs/{runId}/artifacts` → `tasksgodzilla/api/app.py` `GET /codex/runs/{run_id}/artifacts`
- Frontend `GET /codex/runs/{runId}/artifacts/{artifactId}/content` → `tasksgodzilla/api/app.py` `GET /codex/runs/{run_id}/artifacts/{artifact_id}/content`
- Frontend expects streaming logs via SSE:
  - `GET /codex/runs/{runId}/logs/stream` → implemented in `tasksgodzilla/api/app.py`

### Policy packs
- Frontend `GET /policy_packs` → `tasksgodzilla/api/app.py` `GET /policy_packs`
- Frontend `POST /policy_packs` → `tasksgodzilla/api/app.py` `POST /policy_packs`

## Phase 2 gap to implement (requested)
Although the codex logs/artifacts endpoints already exist, they currently read from the local filesystem paths stored in DB.
To “wire to Windmill”, we need the API to be able to serve:
- run logs (`/codex/runs/{run_id}/logs`, `/logs/tail`, `/logs/stream`) by fetching from Windmill when a run’s log source is Windmill-backed
- artifact content (`/codex/runs/{run_id}/artifacts/{artifact_id}/content`) by fetching from Windmill when an artifact’s `path` references Windmill

The next step is to add a Windmill client + reference format (e.g. `windmill://job/<job_id>/logs`) and update the API handlers to proxy accordingly.

