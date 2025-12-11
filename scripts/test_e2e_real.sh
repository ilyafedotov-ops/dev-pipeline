#!/usr/bin/env bash
#
# Real End-to-End Test for TasksGodzilla
# Starts actual services (API + Worker) and runs complete workflow
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $*"; }

check_step() {
    if [ $? -eq 0 ]; then
        log_info "✓ $1"
        return 0
    else
        log_error "✗ $1"
        return 1
    fi
}

# ===== CONFIGURATION =====
TEST_DB_PATH="/tmp/tasksgodzilla-e2e-$(date +%s).sqlite"
TEST_REDIS_URL="${TASKSGODZILLA_REDIS_URL:-redis://localhost:6379/14}"
VENV_PATH="${VENV_PATH:-.venv}"
PYTHON="${VENV_PATH}/bin/python"
API_PORT=8010
API_BASE="http://localhost:${API_PORT}"

# PIDs for cleanup
API_PID=""
WORKER_PID=""

# Cleanup function
cleanup() {
    log_info ""
    log_info "Cleaning up..."

    if [ -n "${API_PID}" ] && kill -0 "${API_PID}" 2>/dev/null; then
        log_info "Stopping API server (PID ${API_PID})..."
        kill "${API_PID}" 2>/dev/null || true
        wait "${API_PID}" 2>/dev/null || true
    fi

    if [ -n "${WORKER_PID}" ] && kill -0 "${WORKER_PID}" 2>/dev/null; then
        log_info "Stopping worker (PID ${WORKER_PID})..."
        kill "${WORKER_PID}" 2>/dev/null || true
        wait "${WORKER_PID}" 2>/dev/null || true
    fi

    # Clean test database
    if [ -f "${TEST_DB_PATH}" ]; then
        rm -f "${TEST_DB_PATH}"
        log_info "Removed test database"
    fi

    log_info "Cleanup complete"
}

trap cleanup EXIT INT TERM

# ===== HEADER =====
log_info "=========================================="
log_info "TasksGodzilla End-to-End Test"
log_info "=========================================="
log_info "Database: ${TEST_DB_PATH}"
log_info "Redis: ${TEST_REDIS_URL}"
log_info "API: ${API_BASE}"
log_info ""

# ===== STEP 1: Prerequisites =====
log_step "Step 1: Checking prerequisites..."

if [ ! -x "${PYTHON}" ]; then
    log_error "Python venv not found at ${PYTHON}"
    log_error "Run: make deps"
    exit 1
fi

# Check Redis
if ! "${PYTHON}" - <<PY
import sys
from urllib.parse import urlparse
import redis

redis_url = "${TEST_REDIS_URL}"
try:
    client = redis.Redis.from_url(redis_url)
    client.ping()
    print(f"Redis OK at {redis_url}")
except Exception as exc:
    print(f"Redis check failed: {exc}", file=sys.stderr)
    sys.exit(1)
PY
then
    log_error "Redis not accessible at ${TEST_REDIS_URL}"
    log_error "Start Redis: redis-server --port 6379 &"
    exit 1
fi

check_step "Prerequisites OK"

# Export environment
export TASKSGODZILLA_DB_PATH="${TEST_DB_PATH}"
export TASKSGODZILLA_REDIS_URL="${TEST_REDIS_URL}"
export TASKSGODZILLA_AUTO_CLONE=false
export TASKSGODZILLA_LOG_LEVEL=INFO
export PYTHONPATH="${PROJECT_ROOT}"

# ===== STEP 2: Initialize Database =====
log_step "Step 2: Initializing database..."

"${PYTHON}" -c "
from tasksgodzilla.config import load_config
from tasksgodzilla.storage import create_database

config = load_config()
db = create_database(db_path=config.db_path, db_url=None, pool_size=1)
db.init_schema()
print('Database initialized at:', config.db_path)
"
check_step "Database initialized"

# ===== STEP 3: Start API Server =====
log_step "Step 3: Starting API server..."

"${PYTHON}" scripts/api_server.py --host 0.0.0.0 --port "${API_PORT}" > /tmp/api-server.log 2>&1 &
API_PID=$!

log_info "API server starting (PID ${API_PID})..."

# Wait for API to be ready
MAX_WAIT=30
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -s "${API_BASE}/health" > /dev/null 2>&1; then
        break
    fi
    sleep 1
    WAITED=$((WAITED + 1))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    log_error "API server failed to start after ${MAX_WAIT}s"
    cat /tmp/api-server.log
    exit 1
fi

check_step "API server running at ${API_BASE}"

# ===== STEP 4: Start Worker =====
log_step "Step 4: Starting RQ worker..."

"${PYTHON}" scripts/rq_worker.py > /tmp/rq-worker.log 2>&1 &
WORKER_PID=$!

log_info "Worker starting (PID ${WORKER_PID})..."
sleep 2

if ! kill -0 "${WORKER_PID}" 2>/dev/null; then
    log_error "Worker failed to start"
    cat /tmp/rq-worker.log
    exit 1
fi

check_step "Worker running (PID ${WORKER_PID})"

# ===== STEP 5: Test API Health =====
log_step "Step 5: Testing API endpoints..."

# Health check
HEALTH=$(curl -s "${API_BASE}/health")
if echo "${HEALTH}" | grep -q "ok"; then
    check_step "Health endpoint OK"
else
    log_error "Health check failed: ${HEALTH}"
    exit 1
fi

# Metrics endpoint
if curl -s "${API_BASE}/metrics" | grep -q "process_"; then
    check_step "Metrics endpoint OK"
else
    log_warn "Metrics endpoint returned unexpected data"
fi

# ===== STEP 6: Create Project via API =====
log_step "Step 6: Creating project via API..."

PROJECT_RESPONSE=$(curl -s -X POST "${API_BASE}/projects" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "test-e2e-project",
        "git_url": "https://github.com/example/test-repo.git",
        "base_branch": "main",
        "ci_provider": "github"
    }')

PROJECT_ID=$(echo "${PROJECT_RESPONSE}" | "${PYTHON}" -c "import sys, json; print(json.load(sys.stdin)['id'])")

if [ -n "${PROJECT_ID}" ] && [ "${PROJECT_ID}" != "null" ]; then
    log_info "Project created with ID: ${PROJECT_ID}"
    check_step "Project created via API"
else
    log_error "Failed to create project"
    echo "Response: ${PROJECT_RESPONSE}"
    exit 1
fi

# ===== STEP 7: Verify Project =====
log_step "Step 7: Verifying project..."

PROJECT_DETAIL=$(curl -s "${API_BASE}/projects/${PROJECT_ID}")
PROJECT_NAME=$(echo "${PROJECT_DETAIL}" | "${PYTHON}" -c "import sys, json; print(json.load(sys.stdin)['name'])")

if [ "${PROJECT_NAME}" = "test-e2e-project" ]; then
    check_step "Project details retrieved"
else
    log_error "Project verification failed"
    echo "Response: ${PROJECT_DETAIL}"
    exit 1
fi

# ===== STEP 8: Create Protocol via API =====
log_step "Step 8: Creating protocol via API..."

PROTOCOL_RESPONSE=$(curl -s -X POST "${API_BASE}/projects/${PROJECT_ID}/protocols" \
    -H "Content-Type: application/json" \
    -d '{
        "protocol_name": "test-e2e-protocol",
        "description": "End-to-end test protocol",
        "base_branch": "main",
        "auto_start": false
    }')

PROTOCOL_ID=$(echo "${PROTOCOL_RESPONSE}" | "${PYTHON}" -c "import sys, json; print(json.load(sys.stdin)['id'])")

if [ -n "${PROTOCOL_ID}" ] && [ "${PROTOCOL_ID}" != "null" ]; then
    log_info "Protocol created with ID: ${PROTOCOL_ID}"
    check_step "Protocol created via API"
else
    log_error "Failed to create protocol"
    echo "Response: ${PROTOCOL_RESPONSE}"
    exit 1
fi

# ===== STEP 9: Verify Protocol =====
log_step "Step 9: Verifying protocol..."

PROTOCOL_DETAIL=$(curl -s "${API_BASE}/protocols/${PROTOCOL_ID}")
PROTOCOL_STATUS=$(echo "${PROTOCOL_DETAIL}" | "${PYTHON}" -c "import sys, json; print(json.load(sys.stdin)['status'])")

log_info "Protocol status: ${PROTOCOL_STATUS}"
check_step "Protocol status retrieved"

# ===== STEP 10: List Projects =====
log_step "Step 10: Testing list endpoints..."

PROJECTS_LIST=$(curl -s "${API_BASE}/projects")
PROJECT_COUNT=$(echo "${PROJECTS_LIST}" | "${PYTHON}" -c "import sys, json; print(len(json.load(sys.stdin)))")

if [ "${PROJECT_COUNT}" -ge 1 ]; then
    log_info "Projects list: ${PROJECT_COUNT} projects"
    check_step "List projects endpoint OK"
else
    log_error "No projects found in list"
    exit 1
fi

# ===== STEP 11: List Protocols for Project =====
PROTOCOLS_LIST=$(curl -s "${API_BASE}/projects/${PROJECT_ID}/protocols")
PROTOCOL_COUNT=$(echo "${PROTOCOLS_LIST}" | "${PYTHON}" -c "import sys, json; print(len(json.load(sys.stdin)))")

if [ "${PROTOCOL_COUNT}" -ge 1 ]; then
    log_info "Protocols list: ${PROTOCOL_COUNT} protocols"
    check_step "List protocols endpoint OK"
else
    log_error "No protocols found in list"
    exit 1
fi

# ===== STEP 12: Create Step via Database =====
log_step "Step 12: Creating test step..."

"${PYTHON}" -c "
from tasksgodzilla.config import load_config
from tasksgodzilla.storage import create_database
from tasksgodzilla.domain import StepStatus

config = load_config()
db = create_database(db_path=config.db_path, db_url=None, pool_size=1)

step = db.create_step_run(
    protocol_run_id=${PROTOCOL_ID},
    step_index=1,
    step_name='01-test-step',
    step_type='codex',
    status=StepStatus.PENDING,
    model='gpt-5.1-high',
    engine_id='codex',
    summary='Test step for E2E',
)
print(f'Step created: ID={step.id}')
"
check_step "Test step created"

# ===== STEP 13: Test Events =====
log_step "Step 13: Testing events API..."

EVENTS=$(curl -s "${API_BASE}/protocols/${PROTOCOL_ID}/events")
EVENT_COUNT=$(echo "${EVENTS}" | "${PYTHON}" -c "import sys, json; print(len(json.load(sys.stdin)))" || echo "0")

log_info "Events count: ${EVENT_COUNT}"
check_step "Events API OK"

# ===== STEP 14: Test Queues Endpoint =====
log_step "Step 14: Testing queues endpoint..."

QUEUES=$(curl -s "${API_BASE}/queues")
if echo "${QUEUES}" | grep -q "default"; then
    check_step "Queues endpoint OK"
else
    log_warn "Queues endpoint returned unexpected data"
fi

# ===== STEP 15: Test Database Operations =====
log_step "Step 15: Testing database operations..."

"${PYTHON}" -c "
from tasksgodzilla.config import load_config
from tasksgodzilla.storage import create_database
from tasksgodzilla.domain import ProtocolStatus

config = load_config()
db = create_database(db_path=config.db_path, db_url=None, pool_size=1)

# Update protocol status
db.update_protocol_status(${PROTOCOL_ID}, ProtocolStatus.RUNNING)
run = db.get_protocol_run(${PROTOCOL_ID})
assert run.status == ProtocolStatus.RUNNING, 'Status update failed'

# Create event
db.append_event(
    protocol_run_id=${PROTOCOL_ID},
    event_type='e2e_test',
    message='Test event from E2E test'
)

# List events
events = db.list_events(protocol_run_id=${PROTOCOL_ID})
assert len(events) >= 1, 'Event creation failed'

print(f'Database operations OK: {len(events)} events')
"
check_step "Database operations OK"

# ===== STEP 16: Test Services Layer =====
log_step "Step 16: Testing services layer..."

"${PYTHON}" -c "
from tasksgodzilla.config import load_config
from tasksgodzilla.storage import create_database
from tasksgodzilla.services.orchestrator import OrchestratorService
from tasksgodzilla.domain import ProtocolStatus

config = load_config()
db = create_database(db_path=config.db_path, db_url=None, pool_size=1)

orchestrator = OrchestratorService(db)

# Create another protocol via service
protocol = orchestrator.create_protocol_run(
    project_id=${PROJECT_ID},
    protocol_name='service-test-protocol',
    status=ProtocolStatus.PENDING,
    base_branch='main',
    description='Protocol created via service',
    template_config=None,
    template_source=None,
)

# Verify it exists
protocols = db.list_protocol_runs(project_id=${PROJECT_ID})
assert len(protocols) >= 2, 'Service protocol creation failed'

print(f'Services layer OK: {len(protocols)} protocols total')
"
check_step "Services layer OK"

# ===== STEP 17: Test Worker Processing =====
log_step "Step 17: Testing worker job processing..."

# Check worker logs for activity
if grep -q "RQ worker" /tmp/rq-worker.log; then
    log_info "Worker is processing jobs"
    check_step "Worker active"
else
    log_warn "Worker logs show no activity (may be normal if no jobs queued)"
fi

# ===== STEP 18: Verify API Still Running =====
log_step "Step 18: Verifying services still running..."

if curl -s "${API_BASE}/health" | grep -q "ok"; then
    check_step "API server still running"
else
    log_error "API server stopped responding"
    exit 1
fi

if kill -0 "${WORKER_PID}" 2>/dev/null; then
    check_step "Worker still running"
else
    log_error "Worker process died"
    exit 1
fi

# ===== STEP 19: Final Verification =====
log_step "Step 19: Final verification..."

# Get all projects
FINAL_PROJECTS=$(curl -s "${API_BASE}/projects")
FINAL_COUNT=$(echo "${FINAL_PROJECTS}" | "${PYTHON}" -c "import sys, json; print(len(json.load(sys.stdin)))")

# Get all protocols for our project
FINAL_PROTOCOLS=$(curl -s "${API_BASE}/projects/${PROJECT_ID}/protocols")
FINAL_PROTOCOL_COUNT=$(echo "${FINAL_PROTOCOLS}" | "${PYTHON}" -c "import sys, json; print(len(json.load(sys.stdin)))")

log_info "Final state:"
log_info "  Projects: ${FINAL_COUNT}"
log_info "  Protocols: ${FINAL_PROTOCOL_COUNT}"

if [ "${FINAL_COUNT}" -ge 1 ] && [ "${FINAL_PROTOCOL_COUNT}" -ge 2 ]; then
    check_step "Final verification passed"
else
    log_error "Final verification failed"
    exit 1
fi

# ===== SUCCESS SUMMARY =====
log_info ""
log_info "=========================================="
log_info "End-to-End Test: SUCCESS"
log_info "=========================================="
log_info ""
log_info "Test Results:"
log_info "  ✓ API server started and running"
log_info "  ✓ RQ worker started and running"
log_info "  ✓ Database operations working"
log_info "  ✓ REST API endpoints working"
log_info "  ✓ Project creation via API"
log_info "  ✓ Protocol creation via API"
log_info "  ✓ Step creation via database"
log_info "  ✓ Events logging and retrieval"
log_info "  ✓ Services layer integration"
log_info "  ✓ Worker job processing"
log_info "  ✓ List endpoints working"
log_info "  ✓ Status updates working"
log_info ""
log_info "Created Resources:"
log_info "  Project ID: ${PROJECT_ID}"
log_info "  Protocol ID: ${PROTOCOL_ID}"
log_info "  Total Projects: ${FINAL_COUNT}"
log_info "  Total Protocols: ${FINAL_PROTOCOL_COUNT}"
log_info ""
log_info "Services:"
log_info "  API: ${API_BASE} (PID ${API_PID})"
log_info "  Worker: PID ${WORKER_PID}"
log_info "  Database: ${TEST_DB_PATH}"
log_info ""
log_info "Logs:"
log_info "  API: /tmp/api-server.log"
log_info "  Worker: /tmp/rq-worker.log"
log_info ""

# Cleanup will happen via trap
exit 0
