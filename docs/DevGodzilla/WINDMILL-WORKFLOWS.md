# DevGodzilla Windmill Workflows

> Status: Active
> Scope: Current Windmill integration model and exported assets
> Source of truth: `windmill/flows/devgodzilla/`, `windmill/scripts/devgodzilla/`, `windmill/resources/devgodzilla/`, `windmill/import_to_windmill.py`, `docker-compose*.yml`
> Last updated: 2026-04-19

## Summary

Windmill is used as the workflow runtime and operator-facing companion UI. In this repository, Windmill scripts are primarily thin API adapters that call the DevGodzilla backend rather than importing backend internals directly into Windmill workers.

## Repository Locations

- Scripts: `windmill/scripts/devgodzilla/`
- Flows: `windmill/flows/devgodzilla/`
- Apps: `windmill/apps/devgodzilla/`
- React app env/example assets: `windmill/apps/devgodzilla-react-app/`
- Resources: `windmill/resources/devgodzilla/`
- Import entrypoint: `windmill/import_to_windmill.py`

## Local Development Patterns

### Full Docker stack

```bash
docker compose up --build -d
scripts/run-local-dev.sh import
```

This uses `docker-compose.yml` and routes nginx through `nginx.devgodzilla.conf` to containerized backend/frontend services.

`docker-compose.local.yml` is an alternate full-stack variant that uses pre-built Windmill images but preserves the same routing model.

### Host-backed Windmill + Docker infra

```bash
docker compose -f docker-compose.devgodzilla.yml up -d
scripts/run-local-dev.sh backend start
scripts/run-local-dev.sh frontend start
scripts/run-local-dev.sh import
```

This uses `nginx.local.conf` so Docker nginx proxies API and console traffic to host services.

Important implementation detail:

- `scripts/run-local-dev.sh up` does not use `docker-compose.devgodzilla.yml`; it uses the default `docker-compose.yml`.
- The explicit host-proxy topology must be selected directly with `docker compose -f docker-compose.devgodzilla.yml ...`.

## Local Agent Runtime

Two supported patterns exist for local agent execution:

- Host backend: recommended for day-to-day debugging and hot reload. Agent binaries come from your host `PATH`.
- Docker backend: the container image can include agent CLIs for end-to-end brownfield or task-cycle flows.

If you want a lighter Docker backend image and do not need in-container agent execution:

```bash
export INSTALL_AGENT_CLIS=0
docker compose -f docker-compose.local.yml up -d --build devgodzilla-api
```

For `opencode`, authenticate in the runtime you expect to execute it from.

## Supported Integration Model

Preferred pattern:

- Windmill scripts call DevGodzilla API via helpers in `windmill/scripts/devgodzilla/_api.py`

Avoid as the default approach:

- importing and executing `devgodzilla` package internals directly inside Windmill workers

## Current Script Inventory

Core orchestration and execution wrappers:

- `project_onboard_api.py`
- `onboard_to_tasks_api.py`
- `protocol_from_spec_api.py`
- `protocol_plan_and_wait.py`
- `protocol_select_next_step.py`
- `step_execute_api.py`
- `step_run_qa_api.py`
- `sync_tasks_api.py`
- `sprint_from_protocol_api.py`
- `complete_sprint_api.py`
- `open_pr.py`
- `handle_feedback.py`

SpecKit-oriented wrappers:

- `speckit_specify_api.py`
- `speckit_plan_api.py`
- `speckit_tasks_api.py`
- `speckit_clarify_api.py`
- `speckit_checklist_api.py`
- `speckit_analyze_api.py`
- `speckit_implement_api.py`

Bootstrap and utility scripts:

- `project_setup.py`
- `generate_spec.py`
- `generate_plan.py`
- `generate_tasks.py`
- `list_projects.py`
- `list_protocols.py`
- `get_project.py`
- `get_protocol.py`
- `get_protocol_details.py`
- `get_task_cycle_api.py`

## Current Flow Inventory

Current exported flows under `windmill/flows/devgodzilla/`:

- `brownfield_feature.flow.json`
- `complete_sprint.flow.json`
- `execute_protocol.flow.json`
- `onboard_to_tasks.flow.json`
- `project_onboarding.flow.json`
- `protocol_start.flow.json`
- `run_next_step.flow.json`
- `spec_to_protocol.flow.json`
- `spec_to_tasks.flow.json`
- `sprint_from_protocol.flow.json`
- `step_execute_with_qa.flow.json`
- `sync_tasks_to_sprint.flow.json`

Useful baseline flows in a local workspace:

- `f/devgodzilla/onboard_to_tasks`
- `f/devgodzilla/protocol_start`
- `f/devgodzilla/step_execute_with_qa`
- `f/devgodzilla/run_next_step`

## Current Apps and Resources

Current app exports:

- `windmill/apps/devgodzilla/devgodzilla_dashboard.app.json`
- `windmill/apps/devgodzilla/devgodzilla_project_detail.app.json`
- `windmill/apps/devgodzilla/devgodzilla_projects.app.json`
- `windmill/apps/devgodzilla/devgodzilla_protocol_detail.app.json`
- `windmill/apps/devgodzilla/devgodzilla_protocols.app.json`

Current resource exports:

- `windmill/resources/devgodzilla/database.resource.yaml`
- `windmill/resources/devgodzilla/agents.resource.yaml`

## Import Notes

Default local import command:

```bash
scripts/run-local-dev.sh import
```

That helper wraps `windmill/import_to_windmill.py` and also updates Windmill `global_settings.job_default_timeout` when `WINDMILL_JOB_TIMEOUT_SECONDS` is numeric.

The default token-file path for local imports is:

- `windmill/apps/devgodzilla-react-app/.env.development`

## Related Docs

- Runtime truth: `docs/DevGodzilla/CURRENT_STATE.md`
- API architecture: `docs/DevGodzilla/API-ARCHITECTURE.md`
- System architecture: `docs/DevGodzilla/ARCHITECTURE.md`
- CI notes: `docs/ci.md`
