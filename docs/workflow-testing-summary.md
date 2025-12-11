# Workflow Testing Summary

## Overview

We've created comprehensive testing infrastructure to validate the TasksGodzilla application's real workflow (not just harness tests).

## Testing Scripts Created

### 1. Simple Workflow Test (`scripts/test_workflow_simple.sh`)

**Purpose:** Fast, self-contained test that validates core functionality without external dependencies.

**What it tests:**
- Database initialization and schema
- Project creation and retrieval
- Protocol run lifecycle
- Step run management
- Status updates (pending → running → completed)
- Event logging and retrieval
- OrchestratorService operations
- BudgetService initialization
- GitService initialization
- CLI tools (if API server is available)

**How to run:**
```bash
./scripts/test_workflow_simple.sh
```

**Duration:** ~10 seconds
**Requirements:** Python venv, SQLite (no Redis, no external repos needed)

**Test Results:**
```
✓ Database initialization
✓ Project creation
✓ Protocol run creation
✓ Step run creation
✓ Status updates
✓ Event logging
✓ OrchestratorService
✓ BudgetService
✓ GitService
```

### 2. Full Workflow Test (`scripts/test_real_workflow.sh`)

**Purpose:** Comprehensive end-to-end test including real repository cloning and service integrations.

**What it tests:**
- All of the above, plus:
- Project onboarding with real GitHub repos
- Repository cloning and discovery
- API server integration (if running)
- Worker job processing (if running)
- Git operations on real repos

**How to run:**
```bash
# Requires Redis running
./scripts/test_real_workflow.sh
```

**Duration:** ~2-3 minutes (includes git clone)
**Requirements:** Python venv, Redis, network access

### 3. Manual Testing Guide (`docs/manual-workflow-testing.md`)

**Purpose:** Step-by-step guide for manually testing the complete workflow.

**Covers:**
- Starting API server and workers
- Onboarding projects
- Creating protocols with Codex
- Executing steps
- Running quality validation
- Verifying via CLI/TUI/API

## Quick Start

### Run Simple Test (No external dependencies)

```bash
# Just need Python venv
make deps
./scripts/test_workflow_simple.sh
```

### Test with Real Services

**Terminal 1 - API Server:**
```bash
export TASKSGODZILLA_DB_PATH=/tmp/test.sqlite
export TASKSGODZILLA_REDIS_URL=redis://localhost:6379/0
export TASKSGODZILLA_INLINE_RQ_WORKER=true
.venv/bin/python scripts/api_server.py
```

**Terminal 2 - Run Tests:**
```bash
export TASKSGODZILLA_DB_PATH=/tmp/test.sqlite
curl http://localhost:8010/health
curl http://localhost:8010/projects
```

### Manual Workflow Testing

Follow `docs/manual-workflow-testing.md` for complete step-by-step testing.

## Test Coverage

### What is Tested

**Storage Layer:**
- Database initialization and migrations
- CRUD operations for projects, protocols, steps
- Event logging and querying
- Status transitions

**Services Layer:**
- OrchestratorService (protocol lifecycle)
- BudgetService (token tracking)
- GitService (repository operations)
- OnboardingService (via onboard_repo.py)

**CLI Tools:**
- Project listing and details
- Protocol management
- API integration

### What Requires Manual Testing

**Codex Integration:**
- Protocol planning (requires Codex CLI)
- Protocol execution (requires Codex CLI)
- Quality validation (requires Codex CLI)

**Worker Jobs:**
- Background job processing (requires RQ worker running)
- Queue management
- Job retries and failures

**API Endpoints:**
- Full REST API (requires API server running)
- Webhooks (requires CI integration)
- Real-time events

**TUI:**
- Textual interface (requires terminal)
- Dashboard navigation
- Real-time updates

## Comparison with Harness Tests

### Harness Tests (`tests/harness/*`)
- **Purpose:** Validate workflow harness framework
- **Scope:** Test harness infrastructure itself
- **Speed:** Moderate (tests the test framework)
- **Dependencies:** pytest, test fixtures

### Workflow Tests (These scripts)
- **Purpose:** Validate actual application workflow
- **Scope:** Test real app functionality
- **Speed:** Fast (simple) to slow (full)
- **Dependencies:** Minimal (SQLite) to full (Redis, Codex, Git)

## Integration with Existing Tests

### Test Hierarchy

```
Unit Tests (tests/test_*.py)
  ↓
Service Integration Tests (tests/test_integration_*.py)
  ↓
Workflow Tests (scripts/test_workflow_simple.sh)
  ↓
Harness Tests (scripts/cli_workflow_harness.py)
  ↓
Manual E2E Tests (docs/manual-workflow-testing.md)
```

### When to Use Each

**Unit Tests:** Developing individual functions/classes
```bash
pytest tests/test_storage.py -v
```

**Service Integration Tests:** Testing service interactions
```bash
pytest tests/test_integration_service_flows.py -v
```

**Simple Workflow Test:** Quick validation before commits
```bash
./scripts/test_workflow_simple.sh
```

**Full Workflow Test:** Pre-release validation
```bash
./scripts/test_real_workflow.sh
```

**Harness Tests:** Validating harness framework
```bash
python scripts/cli_workflow_harness.py --mode smoke
```

**Manual E2E:** Complex scenarios with Codex
```
Follow docs/manual-workflow-testing.md
```

## CI Integration

Add to your CI pipeline:

```yaml
# .github/workflows/ci.yml
- name: Run workflow tests
  run: |
    make deps
    ./scripts/test_workflow_simple.sh

# Optional: Full workflow test if Redis available
- name: Run full workflow test
  if: ${{ env.REDIS_AVAILABLE }}
  run: ./scripts/test_real_workflow.sh
```

## Troubleshooting

### Simple test fails

```bash
# Check venv
ls -la .venv/bin/python

# Run with debug
bash -x ./scripts/test_workflow_simple.sh
```

### Full test fails on Redis

```bash
# Check Redis
ps aux | grep redis
redis-cli ping

# Update Redis URL
export TASKSGODZILLA_REDIS_URL=redis://localhost:6379/0
```

### CLI tests fail

```bash
# CLI requires API server running
TASKSGODZILLA_DB_PATH=/tmp/test.sqlite \
.venv/bin/python scripts/api_server.py &

# Wait for server to start
sleep 2
curl http://localhost:8010/health
```

## Next Steps

### Immediate

1. Run simple workflow test after any code changes
2. Use as pre-commit validation
3. Include in CI pipeline

### Short Term

1. Add protocol execution tests (with Codex mocking)
2. Add worker job processing tests
3. Add API endpoint integration tests

### Long Term

1. Add performance benchmarks
2. Add load testing for API
3. Add chaos testing for resilience

## Files Created

- `scripts/test_workflow_simple.sh` - Fast workflow test
- `scripts/test_real_workflow.sh` - Full workflow test
- `docs/manual-workflow-testing.md` - Manual testing guide
- `docs/workflow-testing-summary.md` - This document

## Success Criteria

All workflow tests should:
- ✅ Complete in < 60 seconds (simple) or < 5 minutes (full)
- ✅ Require minimal external dependencies
- ✅ Provide clear pass/fail output
- ✅ Clean up test data automatically
- ✅ Work in CI environments
- ✅ Cover critical user paths
