# End-to-End Testing Guide

## Overview

Complete end-to-end test that starts real services (API + Worker) and validates the entire TasksGodzilla workflow.

## Quick Start

```bash
# Just run it - everything is automated
./scripts/test_e2e_real.sh
```

**Duration:** ~30 seconds
**Requirements:** Python venv, Redis

## What Gets Tested

The E2E test validates the complete real application stack:

### Services Started
1. **FastAPI Server** (port 8010)
   - Health endpoint
   - Metrics endpoint
   - REST API (projects, protocols, steps, events)
   - Queue management

2. **RQ Worker**
   - Job processing from Redis queue
   - Background task execution

3. **SQLite Database**
   - Schema initialization
   - CRUD operations
   - Status transitions

### Workflow Tested

The test executes a complete workflow:

```
1. Start Services → 2. Create Project → 3. Create Protocol → 4. Create Steps → 5. Verify All
```

#### Detailed Test Steps

**Step 1-4: Service Startup**
- ✓ Check prerequisites (Python, Redis)
- ✓ Initialize database with schema
- ✓ Start API server on port 8010
- ✓ Start RQ worker for job processing

**Step 5: API Endpoints**
- ✓ Health check (`/health`)
- ✓ Metrics endpoint (`/metrics`)

**Step 6-7: Project Operations**
- ✓ Create project via `POST /projects`
- ✓ Retrieve project via `GET /projects/{id}`
- ✓ Verify project details

**Step 8-9: Protocol Operations**
- ✓ Create protocol via `POST /projects/{id}/protocols`
- ✓ Retrieve protocol via `GET /protocols/{id}`
- ✓ Verify protocol status

**Step 10-11: List Endpoints**
- ✓ List all projects (`GET /projects`)
- ✓ List protocols for project (`GET /projects/{id}/protocols`)

**Step 12: Step Creation**
- ✓ Create step run via database
- ✓ Verify step exists

**Step 13-14: Additional Endpoints**
- ✓ Events API (`GET /protocols/{id}/events`)
- ✓ Queues endpoint (`GET /queues`)

**Step 15: Database Operations**
- ✓ Update protocol status
- ✓ Create events
- ✓ List events

**Step 16: Services Layer**
- ✓ OrchestratorService integration
- ✓ Create protocol via service
- ✓ Verify service operations

**Step 17-19: Verification**
- ✓ Worker still processing
- ✓ API still responding
- ✓ Final state verification

## Test Output

### Success Output

```
==========================================
TasksGodzilla End-to-End Test
==========================================

✓ Prerequisites OK
✓ Database initialized
✓ API server running at http://localhost:8010
✓ Worker running (PID 12345)
✓ Health endpoint OK
✓ Metrics endpoint OK
✓ Project created via API
✓ Project details retrieved
✓ Protocol created via API
✓ Protocol status retrieved
✓ List projects endpoint OK
✓ List protocols endpoint OK
✓ Test step created
✓ Events API OK
✓ Queues endpoint OK
✓ Database operations OK
✓ Services layer OK
✓ API server still running
✓ Worker still running
✓ Final verification passed

==========================================
End-to-End Test: SUCCESS
==========================================

Created Resources:
  Project ID: 1
  Protocol ID: 2
  Total Projects: 1
  Total Protocols: 3
```

### Cleanup

The test automatically cleans up:
- ✓ Stops API server
- ✓ Stops RQ worker
- ✓ Removes test database
- ✓ All happens via `trap` on EXIT

## Logs

During test execution, logs are written to:
- **API Server:** `/tmp/api-server.log`
- **RQ Worker:** `/tmp/rq-worker.log`

View logs if test fails:
```bash
tail -f /tmp/api-server.log
tail -f /tmp/rq-worker.log
```

## Prerequisites

### Required

1. **Python Virtual Environment**
   ```bash
   make deps
   ```

2. **Redis Server**
   ```bash
   # Check if running
   ps aux | grep redis

   # Start if needed
   redis-server --port 6379 &

   # Or with Docker
   docker run -d -p 6379:6379 redis:alpine
   ```

### Optional

- **Custom Redis URL:** Set `TASKSGODZILLA_REDIS_URL`
  ```bash
  export TASKSGODZILLA_REDIS_URL=redis://localhost:6379/14
  ./scripts/test_e2e_real.sh
  ```

## Comparison with Other Tests

### vs Simple Workflow Test

| Feature | Simple Test | E2E Test |
|---------|------------|----------|
| Services | None (direct DB) | API + Worker |
| Duration | ~10 seconds | ~30 seconds |
| Dependencies | SQLite only | SQLite + Redis |
| Network | No | Yes (localhost) |
| Jobs | No | Yes (background) |
| Realism | Low | High |

### vs Harness Tests

| Feature | Harness | E2E Test |
|---------|---------|----------|
| Purpose | Test framework | Test application |
| Scope | Harness infra | Real workflow |
| Mock | Heavy | Minimal |
| External deps | Many | Few |

### vs Unit Tests

| Feature | Unit Tests | E2E Test |
|---------|-----------|----------|
| Scope | Single function | Full stack |
| Speed | Very fast | Moderate |
| Isolation | High | Low |
| Integration | No | Yes |

## Use Cases

### 1. Pre-Commit Validation

```bash
# Quick check before committing
./scripts/test_e2e_real.sh
```

### 2. CI Integration

```yaml
# .github/workflows/ci.yml
jobs:
  e2e-test:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v3
      - name: Run E2E Test
        env:
          TASKSGODZILLA_REDIS_URL: redis://localhost:6379/14
        run: ./scripts/test_e2e_real.sh
```

### 3. Release Validation

```bash
# Before releasing
scripts/ci/test.sh              # Unit tests
./scripts/test_workflow_simple.sh  # Workflow tests
./scripts/test_e2e_real.sh         # E2E test
```

### 4. Development Verification

```bash
# After making changes to API or services
./scripts/test_e2e_real.sh
```

## Troubleshooting

### Test Fails at Prerequisites

**Issue:** Redis not accessible

**Solution:**
```bash
# Check Redis
ps aux | grep redis
redis-cli ping

# Start Redis
redis-server --port 6379 &

# Verify
redis-cli -p 6379 ping  # Should return PONG
```

### Test Fails at API Startup

**Issue:** Port 8010 already in use

**Solution:**
```bash
# Find process using port
lsof -i :8010

# Kill it
kill <PID>

# Or use different port
# Edit scripts/test_e2e_real.sh: API_PORT=8011
```

### Test Fails at Worker Startup

**Issue:** Worker logs show errors

**Solution:**
```bash
# Check worker logs
cat /tmp/rq-worker.log

# Common issues:
# - Redis connection: Check TASKSGODZILLA_REDIS_URL
# - Database: Check TASKSGODZILLA_DB_PATH permissions
```

### API Endpoints Fail

**Issue:** 404 or 500 errors

**Solution:**
```bash
# Check API logs
cat /tmp/api-server.log

# Test manually
curl http://localhost:8010/health
curl http://localhost:8010/projects
```

### Database Errors

**Issue:** Permission denied or locked

**Solution:**
```bash
# Remove any stale database
rm -f /tmp/tasksgodzilla-e2e-*.sqlite

# Check permissions
ls -la /tmp/

# Run test again
./scripts/test_e2e_real.sh
```

## Advanced Usage

### Debug Mode

```bash
# Run with bash debugging
bash -x ./scripts/test_e2e_real.sh 2>&1 | tee debug.log
```

### Keep Services Running

Edit `scripts/test_e2e_real.sh` and comment out cleanup:

```bash
# trap cleanup EXIT INT TERM  # Comment this out
```

Then manually test:
```bash
./scripts/test_e2e_real.sh

# Services keep running, test manually:
curl http://localhost:8010/projects
curl http://localhost:8010/health

# Cleanup manually when done
pkill -f api_server.py
pkill -f rq_worker.py
```

### Custom Test Data

Modify project/protocol creation in the script:

```bash
# Edit Step 6 in test_e2e_real.sh
PROJECT_RESPONSE=$(curl -s -X POST "${API_BASE}/projects" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "my-custom-project",
        "git_url": "https://github.com/myorg/myrepo.git",
        "base_branch": "develop"
    }')
```

### Run Multiple Times

```bash
# Stress test
for i in {1..10}; do
    echo "Run $i"
    ./scripts/test_e2e_real.sh || break
done
```

## Integration with Development Workflow

### Recommended Testing Order

1. **During Development:**
   ```bash
   pytest tests/test_specific_feature.py -v
   ```

2. **Before Commit:**
   ```bash
   ./scripts/test_workflow_simple.sh
   ```

3. **Before Push:**
   ```bash
   scripts/ci/test.sh
   ./scripts/test_e2e_real.sh
   ```

4. **Before Release:**
   ```bash
   scripts/ci/lint.sh
   scripts/ci/typecheck.sh
   scripts/ci/test.sh
   ./scripts/test_workflow_simple.sh
   ./scripts/test_e2e_real.sh
   python scripts/cli_workflow_harness.py --mode full
   ```

## Performance

Typical execution times:

| Component | Time |
|-----------|------|
| Prerequisites | 1s |
| DB Init | 1s |
| API Startup | 3s |
| Worker Startup | 2s |
| API Tests | 5s |
| DB Tests | 2s |
| Services Tests | 3s |
| Verification | 2s |
| Cleanup | 2s |
| **Total** | **~20-30s** |

## What's NOT Tested

The E2E test does NOT cover:

- ❌ Codex CLI integration (requires Codex installed)
- ❌ Real git repository operations (uses mock URLs)
- ❌ Protocol execution (would require Codex)
- ❌ Quality validation (would require Codex)
- ❌ CI webhooks (requires external CI)
- ❌ TUI interface (terminal UI)
- ❌ Long-running jobs (test is quick)

For these, see:
- **Codex integration:** `docs/manual-workflow-testing.md`
- **Full workflow:** `scripts/cli_workflow_harness.py`

## Success Criteria

Test passes when:
- ✅ All 19 steps complete successfully
- ✅ Services start and stay running
- ✅ All API endpoints return expected data
- ✅ Database operations succeed
- ✅ No errors in logs
- ✅ Cleanup completes successfully

## Summary

The E2E test provides:
- ✅ Real service integration testing
- ✅ Automated setup and teardown
- ✅ Fast execution (~30 seconds)
- ✅ Minimal dependencies
- ✅ Clear pass/fail output
- ✅ Comprehensive coverage
- ✅ CI-ready

Run it before every commit to ensure the real app works!
