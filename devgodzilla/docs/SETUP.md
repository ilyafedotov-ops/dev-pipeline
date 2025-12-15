# DevGodzilla Setup Guide

## Prerequisites

- **Python 3.11+** 
- **PostgreSQL 14+** (for production) or SQLite (for development)
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
pip install -e .
```

### 4. Database Setup

#### SQLite (Development)

DevGodzilla uses SQLite by default for development:

```bash
# Set environment variable
export DEVGODZILLA_DB_PATH=sqlite:///./devgodzilla.db

# Initialize database
python -c "from devgodzilla.db.database import Database; Database().initialize()"
```

#### PostgreSQL (Production)

For production, use PostgreSQL:

```bash
# Set connection string
export DEVGODZILLA_DATABASE_URL=postgresql://user:password@localhost:5432/devgodzilla

# Run Alembic migrations
cd devgodzilla
alembic upgrade head
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEVGODZILLA_DB_PATH` | SQLite database path | `sqlite:///./devgodzilla.db` |
| `DEVGODZILLA_DATABASE_URL` | PostgreSQL connection string | None |
| `DEVGODZILLA_LOG_LEVEL` | Logging level | `INFO` |
| `DEVGODZILLA_API_HOST` | API host | `0.0.0.0` |
| `DEVGODZILLA_API_PORT` | API port | `8000` |

## Verify Installation

```bash
# Check CLI is available
devgodzilla --help

# Check version
devgodzilla version

# Show banner
devgodzilla banner
```

## Running the API

```bash
# Development mode
python -m devgodzilla.api.app

# Or with uvicorn
uvicorn devgodzilla.api.app:app --reload --host 0.0.0.0 --port 8000
```

## Running Tests

```bash
# All DevGodzilla tests
pytest tests/test_devgodzilla_*.py -v

# Specific test file
pytest tests/test_devgodzilla_speckit.py -v

# With coverage
pytest tests/test_devgodzilla_*.py --cov=devgodzilla --cov-report=html
```

## Windmill Integration

For full workflow orchestration, configure Windmill:

```bash
# Set Windmill URL
export WINDMILL_BASE_URL=http://localhost:8000

# Set Windmill token
export WINDMILL_TOKEN=your_token_here
```

## Next Steps

1. Initialize SpecKit in your project: `devgodzilla spec init .`
2. Create your first specification: `devgodzilla spec specify "Your feature"`
3. Run a protocol: `devgodzilla protocol create <project_id> <name>`
