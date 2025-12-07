# TasksGodzilla CLI (interactive)

The CLI provides a terminal-first way to work with the orchestrator API without opening the web console. Run it with no arguments to open the interactive menu:

```bash
python -m tasksgodzilla.cli.main
# or
./scripts/tasksgodzilla_cli.py
```

Defaults:
- API base: `TASKSGODZILLA_API_BASE` (fallback `http://localhost:8011`; use 8010 when running the API directly)
- API token: `TASKSGODZILLA_API_TOKEN`
- Project token: `TASKSGODZILLA_PROJECT_TOKEN`

## Interactive menu (default)

When launched without subcommands, the CLI shows a menu to:
- List/select projects and create a new project.
- List protocols for the selected project, create + start a protocol.
- Run the next step, list steps, run QA on the latest step, approve the latest step.
- View recent events (including `setup_clarifications` from onboarding with recommended CI/model/branch settings), show queue stats.
- Import a CodeMachine workspace (inline or enqueued).

## Subcommands (scriptable)

All commands accept `--api-base`, `--token`, `--project-token`, and `--json` for raw output.

Projects:
```bash
./scripts/tasksgodzilla_cli.py projects list
./scripts/tasksgodzilla_cli.py projects create --name demo --git-url /path/to/repo --base-branch main
./scripts/tasksgodzilla_cli.py projects show 1
```

Protocols:
```bash
./scripts/tasksgodzilla_cli.py protocols list --project 1
./scripts/tasksgodzilla_cli.py protocols create-and-start --project 1 --name 0001-demo --description "demo task"
./scripts/tasksgodzilla_cli.py protocols run-next 2
./scripts/tasksgodzilla_cli.py protocols retry-latest 2
```

Steps:
```bash
./scripts/tasksgodzilla_cli.py steps list --protocol 2
./scripts/tasksgodzilla_cli.py steps run 5
./scripts/tasksgodzilla_cli.py steps run-qa 5
./scripts/tasksgodzilla_cli.py steps approve 5
```

Events & queues:
```bash
./scripts/tasksgodzilla_cli.py events recent --project 1 --limit 20
./scripts/tasksgodzilla_cli.py events watch --protocol 2
./scripts/tasksgodzilla_cli.py queues stats
./scripts/tasksgodzilla_cli.py queues jobs --status queued
```

CodeMachine import:
```bash
./scripts/tasksgodzilla_cli.py codemachine import \
  --project 1 \
  --protocol-name 0002-cm \
  --workspace-path /path/to/workspace \
  --enqueue
```

## Textual TUI (dashboard)

A panel-based dashboard closer to the CodeMachine CLI feel, with live refresh and keybindings.

Run:
```bash
python -m tasksgodzilla.cli.tui
# or
./scripts/tasksgodzilla_tui.py
./scripts/tui                  # simple launcher (prefers .venv)
```

Note: the TUI requires an interactive terminal (TTY). If running in a non-interactive environment, use the argparse CLI instead.
The right-hand panel shows engine/model info plus loop/trigger policy and runtime state for the selected step.

Keybindings:
- Global: `r` refresh, `?` bindings, `tab/shift+tab` cycle panes, `c` configure API/token, `q` quit.
- Steps: `enter` action menu; `n` run next; `t` retry latest; `y` run QA; `a` approve; `o` open PR; `f` cycle step filter (all/pending/running/needs_qa/failed).
- CodeMachine: `i` import workspace (modal with path + enqueue option).
- Events pane: shows onboarding `setup_clarifications` payloads with recommended CI/model/branch/git settings; use them to adjust project/env settings, then rerun setup if needed (no inline “acknowledge” UI yet).
- Branch management is API-only today; use `GET /projects/{id}/branches` and `POST /projects/{id}/branches/{branch}/delete` (body `{"confirm": true}`) to list/delete remote branches until a TUI action is added.

Columns show projects/protocols/steps/events; selections drive the actions above.
If the API is down or widgets are missing, errors are logged to the status bar; start the API first. The API base defaults to `http://localhost:8011` (compose) and can be updated via the `c` modal; use 8010 when running locally without compose.
If using Docker Compose, point it at `http://localhost:8011`.

## Quick setup & URLs

Start the API locally (SQLite + fakeredis):
```bash
make orchestrator-setup
TASKSGODZILLA_REDIS_URL=fakeredis:// .venv/bin/python scripts/api_server.py
# Console at http://localhost:8010/console (use 8011 if running via docker compose; token from TASKSGODZILLA_API_TOKEN if set)
```

Start the API locally but backed by compose-managed Postgres/Redis:
```bash
make compose-deps  # starts Postgres on 5433 and Redis on 6380
TASKSGODZILLA_DB_URL=postgresql://tasksgodzilla:tasksgodzilla@localhost:5433/tasksgodzilla \
TASKSGODZILLA_REDIS_URL=redis://localhost:6380/0 \
.venv/bin/python scripts/api_server.py
```

Run the CLI (interactive menu) pointing at the local API:
```bash
TASKSGODZILLA_API_BASE=http://localhost:8010 .venv/bin/python -m tasksgodzilla.cli.main
# or for docker compose: TASKSGODZILLA_API_BASE=http://localhost:8011 .venv/bin/python -m tasksgodzilla.cli.main
```

Run the TUI dashboard:
```bash
TASKSGODZILLA_API_BASE=http://localhost:8010 .venv/bin/python -m tasksgodzilla.cli.tui
# or for docker compose: TASKSGODZILLA_API_BASE=http://localhost:8011 .venv/bin/python -m tasksgodzilla.cli.tui
```

Environment variables:
- `TASKSGODZILLA_API_BASE` (default `http://localhost:8011`; use 8010 for direct local runs)
- `TASKSGODZILLA_API_TOKEN` (Bearer token; optional)
- `TASKSGODZILLA_PROJECT_TOKEN` (optional per-project token)
