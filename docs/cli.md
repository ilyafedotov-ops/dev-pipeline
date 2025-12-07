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

Multi-page Textual app that mirrors the orchestrator API (projects, protocols, steps, events, queues, branches, specs) with live refresh.

Run:
```bash
python -m tasksgodzilla.cli.tui
# or
./scripts/tasksgodzilla_tui.py
./scripts/tui                  # simple launcher (prefers .venv)
./tui                          # root-level shortcut
```

Note: the TUI requires an interactive terminal (TTY). If running in a non-interactive environment, use the argparse CLI instead.

Pages:
- Dashboard: quick triage across projects/protocols/steps with policy/runtime and events.
- Projects: create/select projects, view onboarding summary, list/delete branches.
- Protocols: create/start/pause/resume/cancel runs, view spec hash/validation, enqueue spec audit, import CodeMachine.
- Steps: run/QA/approve individual steps with policy/runtime and step events.
- Events: protocol-scoped and recent events with metadata.
- Queues: queue stats plus jobs (cycle filter queued/started/failed/finished).
- Settings: update API base/token, toggle auto-refresh.

Keybindings:
- Global: `1`–`6` switch pages, `r` refresh, `?` bindings, `tab/shift+tab` cycle panes, `c` configure API/token, `q` quit, `i` CodeMachine import.
- Steps/Protocols: `enter` step action menu; `n` run next; `t` retry latest; `y` run QA; `a` approve; `o` open PR; `f` cycle step filter (all/pending/running/needs_qa/failed).

Events panes surface onboarding `setup_clarifications` payloads with recommended CI/model/branch/git settings; use them to adjust project/env settings, then rerun setup if needed.
If the API is down or widgets are missing, errors are logged to the status bar; start the API first. The API base defaults to `http://localhost:8011` (compose) and can be updated via the `c` modal; use 8010 when running locally without compose.
If using Docker Compose, point it at `http://localhost:8011`.

## Rust TUI (beta with actions)

Rust/ratatui port focused on fast navigation and stability (projects/protocols/steps/events/queues plus protocol/step actions). Startup flow: login screen (API base + optional tokens) → centered main menu → tabbed dashboard.
New welcome screen: on launch, pick **Start TasksGodzilla** (auto-login jumps straight into the dashboard if env tokens are set), **Settings** (API/token modal), **Help**, or **Version**.

Run (requires Rust toolchain/cargo):
```bash
./scripts/tui-rs           # builds in release mode
```

Env:
- `TASKSGODZILLA_API_BASE` (default `http://localhost:8011`)
- `TASKSGODZILLA_API_TOKEN`, `TASKSGODZILLA_PROJECT_TOKEN`
- `TASKSGODZILLA_TUI_REFRESH_SECS` (default 4)
- `TASKSGODZILLA_TUI_AUTOLOGIN` (default `1`); set to `0`/`false` to force showing the login + menu every launch.

Keys: `q` quit, `m` main menu, `enter` quick action palette, `r` refresh, `tab`/`shift+tab`/`←`/`→` cycle pages, `1-7` direct page select, arrows or `j/k` move selection, `[`/`]` cycle branches, `J` cycle queue job filter, `f` cycle step filter.
Actions: `n` run next, `t` retry latest, `y` run QA latest, `a` approve latest, `o` open PR, `s` start, `p` pause, `e` resume, `x` cancel protocol.
Modals: `g` new project, `R` new protocol, `i` import CodeMachine, `A` spec audit, `c` configure API/token, `b` reload branches, `d` delete selected branch, `h`/`?` show key help in status.

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
