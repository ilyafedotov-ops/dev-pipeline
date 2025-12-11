# Manual Workflow Testing Guide

Complete guide for manually testing the TasksGodzilla workflow end-to-end using real CLI tools.

## Quick Test (Automated)

```bash
# Run automated workflow test
./scripts/test_real_workflow.sh
```

This script tests: onboarding, database operations, services layer, CLI tools, and git utilities.

## Full Manual Workflow Test

### Prerequisites

```bash
# 1. Ensure dependencies are installed
make deps

# 2. Start Redis
redis-server --port 6379 &

# 3. Verify Redis is accessible
redis-cli -p 6379 ping  # Should return PONG

# 4. Set environment variables
export TASKSGODZILLA_DB_PATH=/tmp/tasksgodzilla-manual-test.sqlite
export TASKSGODZILLA_REDIS_URL=redis://localhost:6379/15
export TASKSGODZILLA_AUTO_CLONE=true
```

### Workflow Steps

#### Step 1: Start Services (Optional - for API/worker testing)

**Terminal 1 - API Server:**
```bash
TASKSGODZILLA_DB_PATH=/tmp/tasksgodzilla-manual-test.sqlite \
TASKSGODZILLA_REDIS_URL=redis://localhost:6379/15 \
TASKSGODZILLA_INLINE_RQ_WORKER=false \
.venv/bin/python scripts/api_server.py

# API available at: http://localhost:8010
# Console at: http://localhost:8010/console
```

**Terminal 2 - RQ Worker:**
```bash
TASKSGODZILLA_DB_PATH=/tmp/tasksgodzilla-manual-test.sqlite \
TASKSGODZILLA_REDIS_URL=redis://localhost:6379/15 \
.venv/bin/python scripts/rq_worker.py

# Worker will process jobs from Redis queue
```

#### Step 2: Initialize Database

```bash
.venv/bin/python -c "
from tasksgodzilla.config import load_config
from tasksgodzilla.storage import create_database

config = load_config()
db = create_database(db_path=config.db_path, db_url=config.db_url, pool_size=1)
db.init_schema()
print('Database initialized at:', config.db_path)
"
```

**Expected output:** `Database initialized at: /tmp/tasksgodzilla-manual-test.sqlite`

#### Step 3: Onboard a Project

```bash
# Option A: Onboard a real GitHub repo
python scripts/onboard_repo.py \
  --git-url https://github.com/anthropics/anthropic-sdk-python.git \
  --name test-anthropic-sdk \
  --base-branch main \
  --skip-discovery

# Option B: Onboard a local repo
python scripts/onboard_repo.py \
  --git-url /path/to/local/repo \
  --name my-local-project \
  --base-branch main \
  --skip-discovery
```

**Expected output:**
```
Project 1 onboarded at projects/1/test-anthropic-sdk.
Setup run: setup-1 (status=completed, spec=skipped)
```

**Note the Project ID** (e.g., `1`) for subsequent steps.

#### Step 4: Verify Project via CLI

```bash
# List all projects
python scripts/tasksgodzilla_cli.py projects list

# List projects as JSON
python scripts/tasksgodzilla_cli.py projects list --json | jq .

# Get specific project details
python scripts/tasksgodzilla_cli.py projects show 1
```

#### Step 5: Verify Project via API (if API server is running)

```bash
# Health check
curl http://localhost:8010/health

# List projects
curl http://localhost:8010/projects | jq .

# Get specific project
curl http://localhost:8010/projects/1 | jq .

# List protocol runs for project
curl http://localhost:8010/projects/1/protocols | jq .
```

#### Step 6: Create a Protocol (requires Codex CLI)

**Note:** This step requires the Codex CLI to be installed and configured.

```bash
# Navigate to the project directory
cd projects/1/test-anthropic-sdk

# Run protocol pipeline
python ../../../scripts/protocol_pipeline.py \
  --base-branch main \
  --short-name "add-logging" \
  --description "Add structured logging to the SDK client"

# Optional: Auto-open PR
python ../../../scripts/protocol_pipeline.py \
  --base-branch main \
  --short-name "add-logging" \
  --description "Add structured logging to the SDK client" \
  --pr-platform github
```

**Expected output:**
```
Protocol 0001-add-logging created
Worktree: ../worktrees/0001-add-logging
Plan: .protocols/0001-add-logging/plan.md
Steps:
  - 01-implement-logger.md
  - 02-add-tests.md
  - 03-update-docs.md
```

#### Step 7: Execute a Protocol Step (requires Codex CLI)

```bash
# Navigate to the worktree
cd ../worktrees/0001-add-logging

# Execute with Codex
codex --model codex-5.1-max-xhigh \
  --sandbox workspace-write \
  --ask-for-approval on-request \
  "Follow .protocols/0001-add-logging/plan.md and implement step 01-implement-logger.md"
```

#### Step 8: Run Quality Validation (requires Codex CLI)

```bash
python scripts/quality_orchestrator.py \
  --protocol-root ../worktrees/0001-add-logging/.protocols/0001-add-logging \
  --step-file 01-implement-logger.md \
  --model codex-5.1-max
```

**Expected output:**
```
Quality report written to: .protocols/0001-add-logging/quality-report.md
Verdict: PASS
```

#### Step 9: Test Services Layer Directly

```bash
.venv/bin/python -c "
from tasksgodzilla.config import load_config
from tasksgodzilla.storage import create_database
from tasksgodzilla.services.orchestrator import OrchestratorService
from tasksgodzilla.services.git import GitService
from tasksgodzilla.services.onboarding import OnboardingService

config = load_config()
db = create_database(db_path=config.db_path, db_url=config.db_url, pool_size=1)

# Test OrchestratorService
orchestrator = OrchestratorService(db)
protocols = orchestrator.list_protocol_runs(project_id=1)
print(f'Protocols for project 1: {len(protocols)}')
for p in protocols:
    print(f'  - {p.protocol_name} (status={p.status.value})')

# Test GitService
git_service = GitService(db)
project = db.get_project(1)
if project and project.local_path:
    from pathlib import Path
    info = git_service.get_repo_info(Path(project.local_path))
    print(f'Repo info: branch={info[\"current_branch\"]}, remote={info[\"remote_url\"]}')
"
```

#### Step 10: Test Worker Jobs (if API + worker are running)

**Via API (POST to create a protocol):**
```bash
curl -X POST http://localhost:8010/projects/1/protocols \
  -H "Content-Type: application/json" \
  -d '{
    "protocol_name": "test-worker-protocol",
    "description": "Test protocol via API",
    "base_branch": "main",
    "auto_start": true
  }' | jq .
```

**Check worker logs** in Terminal 2 to see job processing.

**Check protocol status:**
```bash
curl http://localhost:8010/projects/1/protocols | jq '.[] | select(.protocol_name == "test-worker-protocol")'
```

#### Step 11: Test TUI (if available)

```bash
# Launch Textual TUI
python -m tasksgodzilla.cli.tui

# Or use launcher
./tui
```

**In TUI:**
- Navigate with arrow keys
- View projects, protocols, steps, events
- Monitor real-time updates

### Verification Checklist

After running the workflow, verify:

- [ ] Database file created at specified path
- [ ] Project registered with correct name and git URL
- [ ] Project directory cloned (if using remote URL)
- [ ] CLI can list and show projects
- [ ] API endpoints return valid JSON (if server running)
- [ ] Services layer operations succeed
- [ ] Git utilities can detect repo info
- [ ] Protocol created with plan and steps (if Codex available)
- [ ] Worker processes jobs (if worker running)
- [ ] Events are logged in database

### Common Issues and Solutions

**Issue: Redis connection refused**
```bash
# Check Redis is running
redis-cli -p 6379 ping

# Start Redis if needed
redis-server --port 6379 &
```

**Issue: Database locked**
```bash
# If using SQLite, ensure no other processes are accessing it
lsof /tmp/tasksgodzilla-manual-test.sqlite

# Or use a new database path
export TASKSGODZILLA_DB_PATH=/tmp/tasksgodzilla-test-$(date +%s).sqlite
```

**Issue: Project directory not created**
```bash
# Check TASKSGODZILLA_AUTO_CLONE setting
echo $TASKSGODZILLA_AUTO_CLONE  # Should be "true"

# Or manually clone the repo
git clone <repo-url> projects/manual-test-repo
python scripts/onboard_repo.py --git-url projects/manual-test-repo --name test-project
```

**Issue: Worker not processing jobs**
```bash
# Check Redis connection
redis-cli -u $TASKSGODZILLA_REDIS_URL ping

# Check worker logs for errors
tail -f /tmp/rq-worker.log

# Verify queue has jobs
redis-cli -u $TASKSGODZILLA_REDIS_URL llen rq:queue:default
```

**Issue: Codex not found**
```bash
# Check Codex installation
which codex

# Or skip Codex-dependent steps
# - Use --skip-discovery when onboarding
# - Skip protocol creation and execution steps
# - Focus on testing storage, services, API, and CLI
```

### Cleanup

```bash
# Stop services
pkill -f api_server.py
pkill -f rq_worker.py

# Remove test database
rm /tmp/tasksgodzilla-manual-test.sqlite

# Remove cloned repos (optional)
rm -rf projects/1/

# Stop Redis (if you started it for testing)
redis-cli shutdown
```

## Partial Workflow Tests

### Test Only Storage + Services (No Codex Required)

```bash
# Run automated test script (skips Codex-dependent steps)
./scripts/test_real_workflow.sh
```

### Test Only API Endpoints (Requires API Server)

```bash
# Start API server in one terminal
TASKSGODZILLA_DB_PATH=/tmp/test.sqlite \
TASKSGODZILLA_REDIS_URL=redis://localhost:6379/15 \
.venv/bin/python scripts/api_server.py

# Test in another terminal
curl http://localhost:8010/health
curl http://localhost:8010/projects
curl http://localhost:8010/metrics
```

### Test Only CLI Tools

```bash
# Test CLI without API server
export TASKSGODZILLA_DB_PATH=/tmp/test.sqlite
export TASKSGODZILLA_REDIS_URL=redis://localhost:6379/15

python scripts/tasksgodzilla_cli.py projects list
python scripts/tasksgodzilla_cli.py --help
```

## Performance Testing

Monitor performance during workflow execution:

```bash
# Monitor Redis queue size
watch -n 1 'redis-cli -u $TASKSGODZILLA_REDIS_URL llen rq:queue:default'

# Monitor database size
watch -n 1 'ls -lh /tmp/tasksgodzilla-manual-test.sqlite'

# Monitor API metrics
curl http://localhost:8010/metrics
```

## Integration with CI

Test the same workflow that CI runs:

```bash
# Run bootstrap
scripts/ci/bootstrap.sh

# Run tests
scripts/ci/test.sh

# Run lint
scripts/ci/lint.sh

# Run typecheck
scripts/ci/typecheck.sh
```
