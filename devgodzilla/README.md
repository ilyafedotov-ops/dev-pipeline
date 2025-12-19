# DevGodzilla

> **SpecKit + Windmill + Multi-Agent AI Development Pipeline**
>
> An open-source, specification-driven, AI-powered development platform.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Overview

DevGodzilla is an integrated AI development platform that combines:

| Component | Purpose |
|-----------|---------|
| **SpecKit** | Specification-driven development workflow |
| **Windmill** | Industrial-grade workflow orchestration |
| **Multi-Agent Execution** | 18+ AI coding agents (Codex, Claude, OpenCode, etc.) |

## Headless SWE-Agent Workflow (TasksGodzilla-style)

DevGodzilla’s main workflow is **agent-driven**: it runs a headless SWE-agent (default engine `opencode`, default model `zai-coding-plan/glm-4.6`) using prompts under `prompts/`, writes artifacts into the repo/worktree, and DevGodzilla only validates/records those outputs.

**Key artifact locations:**
- Repo discovery outputs (agent-written): `tasksgodzilla/DISCOVERY.md`, `tasksgodzilla/DISCOVERY_SUMMARY.json`, `tasksgodzilla/ARCHITECTURE.md`, `tasksgodzilla/API_REFERENCE.md`, `tasksgodzilla/CI_NOTES.md`
- Protocol definition (agent-written, per worktree): `.protocols/<protocol_name>/plan.md` + `.protocols/<protocol_name>/step-*.md`
- Execution “git report” artifacts (DevGodzilla-written): `.protocols/<protocol_name>/.devgodzilla/steps/<step_run_id>/artifacts/*`

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourorg/dev-pipeline.git
cd dev-pipeline

# Install DevGodzilla
pip install -e .
```

### Initialize SpecKit

```bash
# Initialize .specify directory in your project
devgodzilla spec init .

# Create a feature specification
devgodzilla spec specify "Add user authentication with OAuth2"

# Generate implementation plan
devgodzilla spec plan specs/001-add-user-authentication/spec.md

# Generate tasks
devgodzilla spec tasks specs/001-add-user-authentication/plan.md
```

### Create and Run a Protocol (agent-driven, git/worktree-first)

Defaults (recommended for deterministic E2E):

```bash
export DEVGODZILLA_DEFAULT_ENGINE_ID=opencode
export DEVGODZILLA_OPENCODE_MODEL=zai-coding-plan/glm-4.6
```

1) Create a project and clone it (or point at an existing clone via `--local-path`):

```bash
# Create a project
devgodzilla project create my-project --repo https://github.com/yourorg/repo.git
```

2) Run headless repo discovery (writes `tasksgodzilla/*` inside the repo):

```bash
devgodzilla project discover 1 --agent --pipeline --engine opencode --model zai-coding-plan/glm-4.6
```

3) Create a protocol:

```bash
# Create a protocol
devgodzilla protocol create 1 "implement-auth" --description "Add OAuth2 authentication"
```

4) Ensure the protocol worktree exists, then plan it:

```bash
devgodzilla protocol worktree 1
devgodzilla protocol plan 1
```

If `.protocols/<protocol_name>/step-*.md` are missing, planning auto-generates them via the headless agent (controlled by `DEVGODZILLA_AUTO_GENERATE_PROTOCOL`, default `true`).

5) Execute steps (local execution without Windmill):

```bash
# Select the next runnable step (selection-only)
curl -sS -X POST http://localhost:8000/protocols/1/actions/run_next_step

# Execute + QA the returned step_run_id
devgodzilla step execute <step_run_id> --engine opencode --model zai-coding-plan/glm-4.6
devgodzilla step qa <step_run_id>
```

For fully orchestrated runs, use the REST API + Windmill flows (see `docs/DevGodzilla/WINDMILL-WORKFLOWS.md`).

## CLI Commands

| Command Group | Description |
|---------------|-------------|
| `devgodzilla spec` | SpecKit commands (init, specify, plan, tasks) |
| `devgodzilla protocol` | Protocol management (create, start, status, pause) |
| `devgodzilla project` | Project CRUD operations |
| `devgodzilla agent` | Agent management and health checks |
| `devgodzilla clarify` | Handle clarification questions |
| `devgodzilla step` | Step execution and QA |
| `devgodzilla qa` | Quality assurance gates |

See [docs/CLI.md](docs/CLI.md) for full command reference.

## API

DevGodzilla provides a FastAPI-based REST API:

```bash
# Start the API server
python -m devgodzilla.api.app

# API available at http://localhost:8000
# OpenAPI docs at http://localhost:8000/docs
```

### Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /projects` | Create a new project |
| `POST /speckit/init` | Initialize SpecKit |
| `POST /speckit/specify` | Generate specification |
| `POST /protocols` | Create protocol |
| `POST /protocols/{id}/actions/start` | Start protocol |

See [docs/API.md](docs/API.md) for complete API reference.

## Architecture

```
devgodzilla/
├── api/           # FastAPI REST API
├── cli/           # Click-based CLI
├── services/      # Core business logic
│   ├── specification.py   # SpecKit integration
│   ├── orchestrator.py    # Windmill orchestration
│   ├── execution.py       # Agent execution
│   └── quality.py         # QA gates
├── engines/       # AI agent integrations
├── qa/            # Quality assurance gates
├── db/            # Database schema
├── windmill/      # Windmill integration
└── alembic/       # Database migrations
```

## Documentation

- [Setup Guide](docs/SETUP.md) - Installation and configuration
- [CLI Reference](docs/CLI.md) - All CLI commands
- [API Reference](docs/API.md) - REST API endpoints
- [Architecture](../docs/DevGodzilla/ARCHITECTURE.md) - Full architecture design

## Testing

```bash
# Run DevGodzilla tests
pytest tests/test_devgodzilla_*.py -v

# Run specific test module
pytest tests/test_devgodzilla_speckit.py -v
```

### E2E workflow tests (real public repo; validates agent outputs)

E2E tests are opt-in (they clone a real public GitHub repo):

```bash
DEVGODZILLA_RUN_E2E=1 scripts/ci/test_e2e_real_repo.sh
```

To run with a real `opencode` installation (no stub), use:

```bash
DEVGODZILLA_RUN_E2E_REAL_AGENT=1 scripts/ci/test_e2e_real_agent.sh
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `pytest tests/`
4. Submit a pull request

## License

MIT License - see [LICENSE](../LICENSE) for details.
