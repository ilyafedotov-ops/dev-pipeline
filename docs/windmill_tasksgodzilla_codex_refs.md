# Windmill → TasksGodzilla: Codex Run Refs (Logs + Result)

This repo supports displaying Windmill job logs/results in the TasksGodzilla web UI by storing special references in:
- `codex_runs.log_path`
- `run_artifacts.path`

References use the URI form:
- `windmill://job/<job_id>/logs`
- `windmill://job/<job_id>/result`
- `windmill://job/<job_id>/error`

The TasksGodzilla API proxies these to Windmill when you open:
- `GET /codex/runs/{run_id}/logs`
- `GET /codex/runs/{run_id}/logs/tail`
- `GET /codex/runs/{run_id}/logs/stream` (SSE)
- `GET /codex/runs/{run_id}/artifacts/{artifact_id}/content`

## Windmill script: emit refs
Windmill script: `windmill/scripts/devgodzilla/emit_tasksgodzilla_codex_refs.py`

It reads the current Windmill job ID from `WM_JOB_ID` and calls the TasksGodzilla API to:
1) upsert a codex run via `POST /codex/runs/start` with `log_path=windmill://job/<WM_JOB_ID>/logs`
2) upsert three artifacts (optional): `windmill.logs`, `windmill.result`, `windmill.error`

## Windmill flow wiring
The following flows have a `tgz_emit_refs` module inserted as the first step:
- `windmill/flows/devgodzilla/execute_protocol.flow.json`
- `windmill/flows/devgodzilla/step_execute_with_qa.flow.json`
- `windmill/flows/devgodzilla/full_protocol.flow.json`
- `windmill/flows/devgodzilla/project_onboarding.flow.json`
- `windmill/flows/devgodzilla/protocol_start.flow.json`
- `windmill/flows/devgodzilla/run_next_step.flow.json`
- `windmill/flows/devgodzilla/spec_to_tasks.flow.json`

Each flow accepts optional inputs:
- `tgz_run_id`: use an existing TasksGodzilla `codex_runs.run_id` (otherwise defaults to `WM_JOB_ID`)
- `tgz_params`: store in `codex_runs.params`
- `tgz_attach_default_artifacts`: defaults `true`
- some flows also accept `project_id` and/or `protocol_run_id` and/or `step_run_id` for best-effort association

## Windmill scripts (direct execution)
If you run DevGodzilla actions via scripts (not flows), the following scripts also emit TasksGodzilla Codex refs at the start (best-effort, only when `WM_JOB_ID` is set):
- `windmill/scripts/devgodzilla/protocol_plan_and_wait.py`
- `windmill/scripts/devgodzilla/protocol_select_next_step.py`
- `windmill/scripts/devgodzilla/step_execute_api.py`
- `windmill/scripts/devgodzilla/step_run_qa_api.py`

## Required configuration (Windmill runtime env)
Windmill jobs need to be able to call the TasksGodzilla API.

Set environment variables for the Windmill worker/runtime:
- `TASKSGODZILLA_API_URL` (example: `http://tasksgodzilla-api:8011` or `http://host.docker.internal:8011`)
- `TASKSGODZILLA_API_TOKEN` (optional; must match `TASKSGODZILLA_API_TOKEN` on the API if auth is enabled)

## TasksGodzilla API: artifact upsert
The API exposes an internal-friendly endpoint for Windmill to register references:
- `POST /codex/runs/{run_id}/artifacts/upsert` (body: `{name, kind, path, sha256?, bytes?}`)
