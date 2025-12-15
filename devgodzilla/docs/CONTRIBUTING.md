# Contributing to DevGodzilla

Thank you for your interest in contributing to DevGodzilla!

---

## Development Setup

### 1. Clone and Install

```bash
git clone https://github.com/yourorg/dev-pipeline.git
cd dev-pipeline

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"
```

### 2. Run Tests

```bash
# All tests
pytest tests/

# DevGodzilla tests only
pytest tests/test_devgodzilla_*.py -v

# With coverage
pytest tests/test_devgodzilla_*.py --cov=devgodzilla --cov-report=html
```

### 3. Code Style

We use:
- **ruff** for linting
- **black** for formatting
- **mypy** for type checking

```bash
# Format code
black devgodzilla/

# Lint
ruff check devgodzilla/

# Type check
mypy devgodzilla/
```

---

## Project Structure

```
devgodzilla/
├── api/              # FastAPI routes
│   └── routes/       # Endpoint implementations
├── cli/              # Click CLI commands
├── services/         # Business logic
├── engines/          # AI agent adapters
├── qa/               # Quality assurance
│   └── gates/        # QA gate implementations
├── db/               # Database layer
├── windmill/         # Windmill integration
├── models/           # Pydantic models
└── config/           # Configuration files
```

---

## Contribution Guidelines

### Code Style

- Use type hints everywhere
- Document public functions with docstrings
- Keep functions focused and small
- Prefer composition over inheritance

### Testing

- Write tests for all new features
- Maintain test coverage above 80%
- Use pytest fixtures for shared setup
- Mock external dependencies

### Commits

Use conventional commits:

```
feat: add new QA gate for security scanning
fix: correct spec file path in list_specs
docs: update CLI reference
test: add tests for AgentConfigService
refactor: extract common gate logic
```

### Pull Requests

1. Create a feature branch: `git checkout -b feat/my-feature`
2. Make your changes
3. Run tests: `pytest tests/`
4. Push and create PR
5. Fill out the PR template
6. Wait for review

---

## Adding a New Engine

1. Create adapter in `devgodzilla/engines/`:

```python
from devgodzilla.engines.interface import EngineInterface, EngineMetadata, EngineResult

class MyEngine(EngineInterface):
    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            engine_id="my-engine",
            name="My Engine",
            capabilities=[...],
        )
    
    def execute(self, request) -> EngineResult:
        # Implement execution
        pass
```

2. Add to `config/agents.yaml`
3. Register in `engines/__init__.py`
4. Add tests

---

## Adding a New QA Gate

1. Create gate in `devgodzilla/qa/gates/`:

```python
from devgodzilla.qa.gates.interface import Gate, GateResult

class MyGate(Gate):
    NAME = "my-gate"
    
    def evaluate(self, workspace, step_name, context) -> GateResult:
        # Run checks
        return GateResult(
            gate_name=self.NAME,
            passed=True,
            message="All checks passed",
        )
```

2. Add to default gates in `services/quality.py`
3. Add tests

---

## Questions?

- Open an issue for bugs or features
- Start a discussion for questions
- Check existing issues before creating new ones
