# DeksdenFlow CLI (interactive)

The CLI provides a terminal-first way to work with the orchestrator API without opening the web console. Run it with no arguments to open the interactive menu:

```bash
python -m deksdenflow.cli.main
# or
./scripts/deksdenflow_cli.py
```

Defaults:
- API base: `DEKSDENFLOW_API_BASE` (fallback `http://localhost:8010`)
- API token: `DEKSDENFLOW_API_TOKEN`
- Project token: `DEKSDENFLOW_PROJECT_TOKEN`

## Interactive menu (default)

When launched without subcommands, the CLI shows a menu to:
- List/select projects and create a new project.
- List protocols for the selected project, create + start a protocol.
- Run the next step, list steps, run QA on the latest step, approve the latest step.
- View recent events, show queue stats.
- Import a CodeMachine workspace (inline or enqueued).

## Subcommands (scriptable)

All commands accept `--api-base`, `--token`, `--project-token`, and `--json` for raw output.

Projects:
```bash
./scripts/deksdenflow_cli.py projects list
./scripts/deksdenflow_cli.py projects create --name demo --git-url /path/to/repo --base-branch main
./scripts/deksdenflow_cli.py projects show 1
```

Protocols:
```bash
./scripts/deksdenflow_cli.py protocols list --project 1
./scripts/deksdenflow_cli.py protocols create-and-start --project 1 --name 0001-demo --description "demo task"
./scripts/deksdenflow_cli.py protocols run-next 2
./scripts/deksdenflow_cli.py protocols retry-latest 2
```

Steps:
```bash
./scripts/deksdenflow_cli.py steps list --protocol 2
./scripts/deksdenflow_cli.py steps run 5
./scripts/deksdenflow_cli.py steps run-qa 5
./scripts/deksdenflow_cli.py steps approve 5
```

Events & queues:
```bash
./scripts/deksdenflow_cli.py events recent --project 1 --limit 20
./scripts/deksdenflow_cli.py events watch --protocol 2
./scripts/deksdenflow_cli.py queues stats
./scripts/deksdenflow_cli.py queues jobs --status queued
```

CodeMachine import:
```bash
./scripts/deksdenflow_cli.py codemachine import \
  --project 1 \
  --protocol-name 0002-cm \
  --workspace-path /path/to/workspace \
  --enqueue
```

## Textual TUI (dashboard)

A panel-based dashboard closer to the CodeMachine CLI feel, with live refresh and keybindings.

Run:
```bash
python -m deksdenflow.cli.tui
# or
./scripts/deksdenflow_tui.py
./scripts/tui                  # simple launcher (prefers .venv)
```

Note: the TUI requires an interactive terminal (TTY). If running in a non-interactive environment, use the argparse CLI instead.
The right-hand panel shows engine/model info plus loop/trigger policy and runtime state for the selected step.

Keybindings:
- `r`: refresh
- `n`: run next step
- `t`: retry latest step
- `y`: run QA on latest step
- `a`: approve latest step
- `o`: open PR
- `i`: import CodeMachine workspace (opens a modal)
- `q`: quit

Columns show projects/protocols/steps/events; selections drive the actions above.

## Quick setup & URLs

Start the API locally (SQLite + fakeredis):
```bash
make orchestrator-setup
DEKSDENFLOW_REDIS_URL=fakeredis:// .venv/bin/python scripts/api_server.py
# Console at http://localhost:8010/console (token from DEKSDENFLOW_API_TOKEN if set)
```

Run the CLI (interactive menu) pointing at the local API:
```bash
DEKSDENFLOW_API_BASE=http://localhost:8010 .venv/bin/python -m deksdenflow.cli.main
```

Run the TUI dashboard:
```bash
DEKSDENFLOW_API_BASE=http://localhost:8010 .venv/bin/python -m deksdenflow.cli.tui
```

Environment variables:
- `DEKSDENFLOW_API_BASE` (default `http://localhost:8010`)
- `DEKSDENFLOW_API_TOKEN` (Bearer token; optional)
- `DEKSDENFLOW_PROJECT_TOKEN` (optional per-project token)
