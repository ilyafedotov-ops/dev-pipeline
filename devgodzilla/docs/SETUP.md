# DevGodzilla Setup Guide

## Prerequisites

- **Python 3.12+**
- **PostgreSQL 15+** (for production) or SQLite (for development)
- **Git**

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourorg/dev-pipeline.git
cd dev-pipeline
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Database Setup

#### SQLite (Development)

DevGodzilla uses SQLite by default for development:

```bash
# Set environment variable
export DEVGODZILLA_DB_PATH=./devgodzilla.db

# Initialize database
python -c "from pathlib import Path; from devgodzilla.db.database import SQLiteDatabase; SQLiteDatabase(Path('devgodzilla.db')).init_schema()"
```

#### PostgreSQL (Production)

For production, use PostgreSQL:

```bash
# Set connection string
export DEVGODZILLA_DB_URL=postgresql://user:password@localhost:5432/devgodzilla

# Run Alembic migrations
cd devgodzilla
alembic upgrade head
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEVGODZILLA_DB_PATH` | SQLite database file path | `.devgodzilla.sqlite` |
| `DEVGODZILLA_DB_URL` | PostgreSQL connection string | None |
| `DEVGODZILLA_LOG_LEVEL` | Logging level | `INFO` |
| `DEVGODZILLA_API_HOST` | API host | `0.0.0.0` |
| `DEVGODZILLA_API_PORT` | API port | `8000` |
| `DEVGODZILLA_DEFAULT_ENGINE_ID` | Default engine ID for headless workflows | `opencode` |
| `DEVGODZILLA_OPENCODE_MODEL` | Default model for the `opencode` engine | `zai-coding-plan/glm-4.6` |
| `DEVGODZILLA_AUTO_GENERATE_PROTOCOL` | Auto-generate `.protocols/<name>/step-*.md` when missing | `true` |
| `DEVGODZILLA_DISCOVERY_TIMEOUT_SECONDS` | Timeout for headless repo discovery | `900` |
| `DEVGODZILLA_PROTOCOL_GENERATE_TIMEOUT_SECONDS` | Timeout for headless protocol generation | `900` |
| `DEVGODZILLA_WINDMILL_URL` | Windmill base URL (no `/api` suffix) | `http://localhost:8000` |
| `DEVGODZILLA_WINDMILL_TOKEN` | Windmill token (do not commit) | None |
| `DEVGODZILLA_WINDMILL_WORKSPACE` | Windmill workspace | `devgodzilla` |
| `DEVGODZILLA_WINDMILL_ENV_FILE` | Optional env file to source token/workspace/url | Auto-detected |

## Verify Installation

```bash
# Check CLI entrypoint
python -m devgodzilla.cli.main --help
```

## Running the API

```bash
# Development mode
python -m devgodzilla.api.app

# Or with uvicorn
uvicorn devgodzilla.api.app:app --reload --host 0.0.0.0 --port 8000
```

## Running Tests

### Quick Start

```bash
# Run all tests (unit + real agent E2E)
./scripts/ci/test.sh
```

### Unit Tests

Unit tests use stubbed engines and run quickly (~5 seconds):

```bash
# All unit tests
pytest tests/test_devgodzilla_*.py -k "not integration" -v

# Specific test file
pytest tests/test_devgodzilla_speckit.py -v

# With coverage
pytest tests/test_devgodzilla_*.py --cov=devgodzilla --cov-report=html
```

### E2E Tests (Real Repository)

E2E tests clone a real public GitHub repo for realistic testing:

```bash
# E2E tests with stubbed engine
DEVGODZILLA_RUN_E2E=1 scripts/ci/test_e2e_real_repo.sh
```

### Real Agent E2E Tests

Tests that use actual AI engines (requires `opencode` installed):

```bash
# Run with real opencode engine
DEVGODZILLA_RUN_E2E_REAL_AGENT=1 scripts/ci/test_e2e_real_agent.sh

# Or via main test.sh (auto-detects opencode)
./scripts/ci/test.sh
```

**Note:** Real agent tests take significantly longer (~10 minutes) due to actual AI processing.

### Test Timeouts

Real agent operations have the following default timeouts:

| Operation | Default Timeout | Environment Variable |
|-----------|-----------------|---------------------|
| Discovery (4 stages) | 900s | `DEVGODZILLA_DISCOVERY_TIMEOUT_SECONDS` |
| Protocol generation | 900s | `DEVGODZILLA_PROTOCOL_GENERATE_TIMEOUT_SECONDS` |
| Step execution | 600s | (configured in ExecutionService) |

### Step Status Values

Steps can have the following statuses:

| Status | Description |
|--------|-------------|
| `pending` | Not yet started |
| `running` | Currently executing |
| `needs_qa` | Execution complete, awaiting QA |
| `completed` | Successfully completed |
| `failed` | Execution failed |
| `timeout` | Execution timed out |
| `cancelled` | Manually cancelled |
| `blocked` | Blocked by dependencies or errors |

### Testing SpecKit Integration

Test the full SpecKit workflow:

```bash
# Initialize SpecKit
python -m devgodzilla.cli.main spec init /path/to/repo --project-id 1

# Generate spec
python -m devgodzilla.cli.main spec specify "Add feature X" --directory /path/to/repo --name feature-x

# Generate plan
python -m devgodzilla.cli.main spec plan /path/to/repo/.specify/specs/001-feature-x/feature-spec.md

# Generate tasks
python -m devgodzilla.cli.main spec tasks /path/to/repo/.specify/specs/001-feature-x/plan.md

# Check status
python -m devgodzilla.cli.main spec status /path/to/repo
```

### Testing Discovery Agent

Test the discovery pipeline with real AI:

```bash
# Create project
python -m devgodzilla.cli.main project create "test" --repo https://github.com/user/repo --local-path /path

# Run discovery
python -m devgodzilla.cli.main project discover 1 --agent --pipeline --engine opencode

# Verify outputs in tasksgodzilla/
ls /path/to/repo/tasksgodzilla/
# Expected: DISCOVERY.md, DISCOVERY_SUMMARY.json, ARCHITECTURE.md, API_REFERENCE.md, CI_NOTES.md
```

### Testing Protocol Generation

Test protocol generation with real AI:

```bash
# Create protocol
python -m devgodzilla.cli.main protocol create 1 "my-protocol" --description "Description"

# Setup worktree
python -m devgodzilla.cli.main protocol worktree 1

# Generate steps
python -m devgodzilla.cli.main protocol generate 1 --steps 3 --engine opencode

# Verify outputs
ls /path/to/repo/worktrees/devgodzilla-worktree/.protocols/my-protocol/
# Expected: plan.md, step-01-*.md, step-02-*.md, step-03-*.md
```

## Windmill Integration

For full workflow orchestration, configure Windmill:

```bash
# Option A: set env vars explicitly
export DEVGODZILLA_WINDMILL_URL=http://localhost:8000
export DEVGODZILLA_WINDMILL_WORKSPACE=devgodzilla
export DEVGODZILLA_WINDMILL_TOKEN=your_token_here

# Option B (local dev): keep token in an env file and let DevGodzilla auto-load it
# (defaults to `windmill/apps/devgodzilla-react-app/.env.development` if present)
export DEVGODZILLA_WINDMILL_ENV_FILE=windmill/apps/devgodzilla-react-app/.env.development
```

## Next Steps

1. Initialize SpecKit: `python -m devgodzilla.cli.main spec init .`
2. Generate spec/plan/tasks: `python -m devgodzilla.cli.main spec specify "Your feature"`
3. Create protocol: `python -m devgodzilla.cli.main protocol create <project_id> <name>`
