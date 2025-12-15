# DevGodzilla

> **SpecKit + Windmill + Multi-Agent AI Development Pipeline**
>
> An open-source, specification-driven, AI-powered development platform.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Overview

DevGodzilla is an integrated AI development platform that combines:

| Component | Purpose |
|-----------|---------|
| **SpecKit** | Specification-driven development workflow |
| **Windmill** | Industrial-grade workflow orchestration |
| **Multi-Agent Execution** | 18+ AI coding agents (Codex, Claude, OpenCode, etc.) |

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
devgodzilla spec plan .specify/specs/001-add-user-authentication/spec.md

# Generate tasks
devgodzilla spec tasks .specify/specs/001-add-user-authentication/plan.md
```

### Create and Run a Protocol

```bash
# Create a project
devgodzilla project create my-project --repo https://github.com/yourorg/repo.git

# Create a protocol
devgodzilla protocol create 1 "implement-auth" --description "Add OAuth2 authentication"

# Start execution
devgodzilla protocol start 1
```

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

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `pytest tests/`
4. Submit a pull request

## License

MIT License - see [LICENSE](../LICENSE) for details.
