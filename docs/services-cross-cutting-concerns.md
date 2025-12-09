# Cross-Cutting Concerns

This document describes cross-cutting concerns in the TasksGodzilla architecture and which services or modules own them.

## Overview

Cross-cutting concerns are aspects of the system that affect multiple services and layers. Rather than duplicating this logic across services, we centralize it in dedicated modules or services.

## Concern Ownership

| Concern | Owner | Location | Usage |
|---------|-------|----------|-------|
| Logging | Logging Module | `tasksgodzilla/logging.py` | All services |
| Error Handling | Errors Module | `tasksgodzilla/errors.py` | All services |
| Configuration | Config Module | `tasksgodzilla/config.py` | All services |
| Metrics | TelemetryService | `tasksgodzilla/services/platform/telemetry.py` | BudgetService, ExecutionService, QualityService |
| Database Access | BaseDatabase | `tasksgodzilla/storage.py` | Most services |
| Job Queue | QueueService | `tasksgodzilla/services/platform/queue.py` | OrchestratorService, API, CLI |
| Token Budgets | BudgetService | `tasksgodzilla/services/budget.py` | ExecutionService, QualityService |
| Git Operations | GitService | `tasksgodzilla/services/git.py` | ExecutionService, QualityService, OnboardingService |

## Detailed Ownership

### 1. Logging

**Owner**: `tasksgodzilla.logging` module  
**Not a service**: Logging is a module, not a service, because it's used everywhere and has no state.

**Responsibilities**:
- Structured logging with consistent format
- Log level configuration
- Context enrichment (job_id, protocol_run_id, step_run_id, project_id)
- Integration with external logging systems

**Usage Pattern**:
```python
from tasksgodzilla.logging import get_logger, log_extra

log = get_logger(__name__)

# Basic logging
log.info("Operation completed")

# Structured logging with context
log.info(
    "Step executed",
    extra=log_extra(
        job_id="job-123",
        protocol_run_id=456,
        step_run_id=789,
        project_id=1
    )
)
```

**Guidelines**:
- Every service should use `get_logger(__name__)` at module level
- Use structured logging with `extra=` for context
- Use `log_extra()` helper for consistent context keys
- Log at appropriate levels: DEBUG, INFO, WARNING, ERROR
- Include relevant IDs in log context for traceability

### 2. Error Handling

**Owner**: `tasksgodzilla.errors` module  
**Not a service**: Error handling is a module providing exception classes.

**Responsibilities**:
- Define custom exception types
- Provide error metadata structure
- Enable consistent error handling across services

**Exception Hierarchy**:
```
Exception
└── TasksGodzillaError (base)
    ├── BudgetExceededError
    ├── CodexCommandError
    ├── ValidationError
    └── ... (other domain-specific errors)
```

**Usage Pattern**:
```python
from tasksgodzilla.errors import BudgetExceededError

# Raise with metadata
raise BudgetExceededError(
    "Token budget exceeded",
    metadata={
        "protocol_run_id": 123,
        "estimated_tokens": 5000,
        "max_tokens": 3000
    }
)

# Catch and handle
try:
    # ... operation ...
except BudgetExceededError as exc:
    log.warning("Budget exceeded", extra=exc.metadata)
    # ... handle error ...
```

**Guidelines**:
- Use specific exception types for different error conditions
- Include metadata for debugging and error reporting
- Catch specific exceptions, not bare `Exception`
- Log errors with context before re-raising or handling
- Don't swallow exceptions silently

### 3. Configuration

**Owner**: `tasksgodzilla.config` module  
**Not a service**: Configuration is a module providing config loading.

**Responsibilities**:
- Load configuration from environment variables
- Provide default values
- Validate configuration
- Expose configuration as typed objects

**Configuration Sources** (in order of precedence):
1. Environment variables (`TASKSGODZILLA_*`)
2. Configuration files (`.env`, `config.yaml`)
3. Default values

**Usage Pattern**:
```python
from tasksgodzilla.config import load_config

config = load_config()

# Access configuration
redis_url = config.redis_url
max_tokens = config.max_tokens_per_protocol
budget_mode = config.token_budget_mode
```

**Key Configuration**:
- `redis_url`: Redis connection URL for job queue
- `db_url` / `db_path`: Database connection
- `max_tokens_per_protocol`: Protocol-level token budget
- `max_tokens_per_step`: Step-level token budget
- `token_budget_mode`: Budget enforcement mode (strict/warn/off)
- `exec_model`: Default execution model
- `qa_model`: Default QA model
- `auto_qa_after_exec`: Auto-enqueue QA after execution

**Guidelines**:
- Load config once at service initialization
- Don't reload config during execution (except for testing)
- Use environment variables for deployment-specific config
- Use defaults for development-friendly behavior
- Validate config early (at startup)

### 4. Metrics and Observability

**Owner**: `TelemetryService`  
**Location**: `tasksgodzilla/services/platform/telemetry.py`

**Responsibilities**:
- Record token usage metrics
- Track execution phases
- Provide observability for budget tracking
- Integration with metrics backends (Prometheus, etc.)

**Usage Pattern**:
```python
from tasksgodzilla.services.platform.telemetry import TelemetryService

telemetry = TelemetryService()
telemetry.observe_tokens("exec", "gpt-5.1-high", 5000)
```

**Metrics Collected**:
- Token usage by phase (planning, exec, qa, decompose)
- Token usage by model
- QA verdicts (pass/fail)
- Protocol/step status transitions

**Guidelines**:
- Record metrics at key decision points
- Include phase and model in token metrics
- Don't block on metrics failures
- Use metrics for monitoring, not business logic

### 5. Database Access

**Owner**: `BaseDatabase` interface  
**Location**: `tasksgodzilla/storage.py`

**Responsibilities**:
- Provide CRUD operations for domain entities
- Manage database connections
- Handle transactions
- Provide query interfaces

**Entities**:
- `Project`: Project metadata
- `ProtocolRun`: Protocol execution runs
- `StepRun`: Step execution runs
- `Event`: Audit log events

**Usage Pattern**:
```python
from tasksgodzilla.storage import BaseDatabase

db = BaseDatabase(db_url)

# Create
project = db.create_project(name="my-project", git_url="...", base_branch="main")

# Read
project = db.get_project(project_id)
run = db.get_protocol_run(protocol_run_id)
steps = db.list_step_runs(protocol_run_id)

# Update
db.update_protocol_status(protocol_run_id, "running")
db.update_step_status(step_run_id, "completed")

# Events
db.append_event(protocol_run_id, "step_completed", "Step finished", step_run_id=step_run_id)
```

**Guidelines**:
- Services should depend on `BaseDatabase`, not specific implementations
- Use transactions for multi-step operations
- Log database errors with context
- Use events for audit trail
- Don't bypass database layer to access storage directly

### 6. Job Queue Management

**Owner**: `QueueService`  
**Location**: `tasksgodzilla/services/platform/queue.py`

**Responsibilities**:
- Enqueue background jobs
- Provide job queue abstraction
- Support multiple queue backends (Redis/RQ, inline)

**Job Types**:
- `plan_protocol_job`: Plan a protocol
- `execute_step_job`: Execute a step
- `run_quality_job`: Run QA
- `project_setup_job`: Setup project
- `open_pr_job`: Open PR/MR

**Usage Pattern**:
```python
from tasksgodzilla.services.platform.queue import QueueService

queue = QueueService.from_redis_url("redis://localhost:6379/0")

# Enqueue jobs
job = queue.enqueue_plan_protocol(protocol_run_id=123)
job = queue.enqueue_execute_step(step_run_id=456)
```

**Guidelines**:
- Use QueueService for all job enqueueing
- Don't access queue backend directly
- Handle queue unavailability gracefully (inline fallback)
- Include job_id in logs for traceability

### 7. Token Budget Management

**Owner**: `BudgetService`  
**Location**: `tasksgodzilla/services/budget.py`

**Responsibilities**:
- Estimate token usage
- Enforce budget limits
- Track cumulative usage
- Record actual usage

**Budget Levels**:
- Protocol-level: Total tokens for entire protocol
- Step-level: Total tokens for single step
- Phase-level: Tokens for specific phase (exec, qa, etc.)

**Usage Pattern**:
```python
from tasksgodzilla.services.budget import BudgetService

budget_service = BudgetService()

# Check and track
estimated = budget_service.check_and_track(
    prompt_text="...",
    model="gpt-5.1-high",
    phase="exec",
    budget_mode="strict",
    max_tokens=10000
)

# Check protocol budget
budget_service.check_protocol_budget(
    protocol_run_id=123,
    estimated_tokens=5000,
    max_protocol_tokens=50000
)

# Record actual usage
budget_service.record_usage(
    protocol_run_id=123,
    step_run_id=456,
    phase="exec",
    model="gpt-5.1-high",
    prompt_tokens=1000,
    completion_tokens=500
)
```

**Guidelines**:
- Check budgets before execution
- Record actual usage after execution
- Use appropriate budget mode (strict for production, warn for dev)
- Include budget context in error messages

### 8. Git Operations

**Owner**: `GitService`  
**Location**: `tasksgodzilla/services/git.py`

**Responsibilities**:
- Repository management
- Worktree creation
- Branch operations
- PR/MR creation
- CI triggering

**Usage Pattern**:
```python
from tasksgodzilla.services.git import GitService

git_service = GitService(db)

# Ensure repo
repo_root = git_service.ensure_repo_or_block(project, run)

# Create worktree
worktree = git_service.ensure_worktree(repo_root, "feature-123", "main")

# Push and PR
pushed = git_service.push_and_open_pr(worktree, "feature-123", "main")

# Trigger CI
triggered = git_service.trigger_ci(repo_root, "feature-123", "github")
```

**Guidelines**:
- Use GitService for all git operations
- Don't call git commands directly
- Handle git failures gracefully
- Update protocol status on git failures

## Cross-Service Patterns

### Pattern: Structured Logging with Context

All services should use structured logging with consistent context:

```python
from tasksgodzilla.logging import get_logger, log_extra

log = get_logger(__name__)

class MyService:
    def my_method(self, protocol_run_id, step_run_id, job_id=None):
        log.info(
            "Operation started",
            extra=log_extra(
                job_id=job_id,
                protocol_run_id=protocol_run_id,
                step_run_id=step_run_id
            )
        )
        
        try:
            # ... operation ...
            log.info("Operation completed", extra=log_extra(...))
        except Exception as exc:
            log.error(
                "Operation failed",
                extra={
                    **log_extra(...),
                    "error": str(exc),
                    "error_type": exc.__class__.__name__
                }
            )
            raise
```

### Pattern: Error Handling with Metadata

Services should raise specific exceptions with metadata:

```python
from tasksgodzilla.errors import BudgetExceededError, ValidationError

class MyService:
    def my_method(self, protocol_run_id):
        if budget_exceeded:
            raise BudgetExceededError(
                "Budget exceeded",
                metadata={
                    "protocol_run_id": protocol_run_id,
                    "estimated": 5000,
                    "limit": 3000
                }
            )
        
        if validation_failed:
            raise ValidationError(
                "Validation failed",
                metadata={
                    "protocol_run_id": protocol_run_id,
                    "errors": validation_errors
                }
            )
```

### Pattern: Configuration-Aware Services

Services should load config once and use it consistently:

```python
from tasksgodzilla.config import load_config

class MyService:
    def __init__(self, db):
        self.db = db
        self.config = load_config()
    
    def my_method(self):
        # Use config
        max_tokens = self.config.max_tokens_per_step
        budget_mode = self.config.token_budget_mode
        # ...
```

### Pattern: Metrics Recording

Services should record metrics at key points:

```python
from tasksgodzilla.services.platform.telemetry import TelemetryService

class MyService:
    def __init__(self, db):
        self.db = db
        self.telemetry = TelemetryService()
    
    def my_method(self, tokens, model, phase):
        # Record metrics
        self.telemetry.observe_tokens(phase, model, tokens)
```

### Pattern: Database Event Logging

Services should log important events to the database:

```python
class MyService:
    def __init__(self, db):
        self.db = db
    
    def my_method(self, protocol_run_id, step_run_id):
        # Log event
        self.db.append_event(
            protocol_run_id,
            "operation_completed",
            "Operation completed successfully",
            step_run_id=step_run_id,
            metadata={"key": "value"}
        )
```

## Testing Cross-Cutting Concerns

### Mocking Logging

```python
from unittest.mock import patch

def test_my_service():
    with patch('tasksgodzilla.services.my_service.log') as mock_log:
        service = MyService(db)
        service.my_method()
        
        # Assert logging
        mock_log.info.assert_called_once()
```

### Mocking Configuration

```python
from unittest.mock import patch, MagicMock

def test_my_service():
    mock_config = MagicMock()
    mock_config.max_tokens_per_step = 1000
    
    with patch('tasksgodzilla.services.my_service.load_config', return_value=mock_config):
        service = MyService(db)
        # ... test ...
```

### Mocking Database

```python
from unittest.mock import MagicMock

def test_my_service():
    mock_db = MagicMock()
    mock_db.get_protocol_run.return_value = mock_run
    
    service = MyService(mock_db)
    # ... test ...
    
    # Assert database calls
    mock_db.append_event.assert_called_once()
```

## Guidelines Summary

1. **Logging**: Use structured logging with context everywhere
2. **Errors**: Raise specific exceptions with metadata
3. **Config**: Load once, use consistently
4. **Metrics**: Record at key decision points
5. **Database**: Use BaseDatabase interface, log events
6. **Queue**: Use QueueService for all job enqueueing
7. **Budget**: Check before execution, record after
8. **Git**: Use GitService for all git operations

## Anti-Patterns

### ❌ Don't: Duplicate cross-cutting logic

```python
# BAD - Duplicating logging logic
def my_method(self):
    print(f"[{datetime.now()}] Operation started")  # Don't do this!
```

```python
# GOOD - Use logging module
def my_method(self):
    log.info("Operation started")
```

### ❌ Don't: Access infrastructure directly

```python
# BAD - Direct git commands
def my_method(self):
    subprocess.run(["git", "push", "origin", "main"])  # Don't do this!
```

```python
# GOOD - Use GitService
def my_method(self):
    git_service = GitService(self.db)
    git_service.push_and_open_pr(worktree, protocol_name, base_branch)
```

### ❌ Don't: Swallow exceptions silently

```python
# BAD - Silent failure
def my_method(self):
    try:
        # ... operation ...
    except Exception:
        pass  # Don't do this!
```

```python
# GOOD - Log and handle appropriately
def my_method(self):
    try:
        # ... operation ...
    except Exception as exc:
        log.error("Operation failed", extra={"error": str(exc)})
        raise  # or handle appropriately
```

### ❌ Don't: Mix concerns in services

```python
# BAD - Service doing logging, metrics, and business logic all mixed
def my_method(self):
    print("Starting")  # Don't mix print and log
    # ... business logic ...
    metrics.inc("counter")  # Don't access metrics directly
    # ... more business logic ...
```

```python
# GOOD - Separate concerns clearly
def my_method(self):
    log.info("Operation started")
    
    # Business logic
    result = self._do_work()
    
    # Record metrics
    self.telemetry.observe_tokens("exec", "model", tokens)
    
    log.info("Operation completed")
    return result
```
