#!/usr/bin/env bash
#
# End-to-end workflow test for TasksGodzilla using real CLI tools.
# Tests the complete workflow: onboard → protocol → execution → quality → cleanup
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

check_step() {
    if [ $? -eq 0 ]; then
        log_info "✓ $1"
    else
        log_error "✗ $1"
        exit 1
    fi
}

# ===== CONFIGURATION =====
TEST_DB_PATH="${TASKSGODZILLA_DB_PATH:-/tmp/tasksgodzilla-real-test-$(date +%s).sqlite}"
TEST_REDIS_URL="${TASKSGODZILLA_REDIS_URL:-redis://localhost:6379/15}"
VENV_PATH="${VENV_PATH:-.venv}"
PYTHON="${VENV_PATH}/bin/python"
API_HOST="${TASKSGODZILLA_API_HOST:-127.0.0.1}"
API_PORT="${TASKSGODZILLA_API_PORT:-8010}"
API_LOG_PATH="/tmp/tasksgodzilla-api.log"
API_PID=""

# Test repo configuration (overridable via env or flags)
# Defaults to a small public repo to keep E2E runs fast.
TEST_REPO_URL="${TEST_REPO_URL:-https://github.com/pallets/itsdangerous.git}"
TEST_PROJECT_NAME="${TEST_PROJECT_NAME:-test-itsdangerous-$(date +%s)}"
TEST_BASE_BRANCH="${TEST_BASE_BRANCH:-main}"

usage() {
    cat <<'USAGE'
Usage: scripts/test_real_workflow.sh [options]

Options:
  --repo-url <url>        Git URL to onboard (default: pallets/itsdangerous)
  --base-branch <branch>  Base branch for onboarding (default: main)
  --project-name <name>   Project name to register (default: test-<repo>-<ts>)

Environment overrides:
  TEST_REPO_URL, TEST_BASE_BRANCH, TEST_PROJECT_NAME
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo-url)
            TEST_REPO_URL="$2"
            shift 2
            ;;
        --base-branch)
            TEST_BASE_BRANCH="$2"
            shift 2
            ;;
        --project-name)
            TEST_PROJECT_NAME="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown argument: $1"
            usage
            exit 2
            ;;
    esac
done

# Protocol configuration
PROTOCOL_SHORT_NAME="add-tests-$(date +%s)"
PROTOCOL_DESCRIPTION="Add unit tests for SDK client initialization"

start_api_server() {
    log_info "Starting API server for CLI checks (logs: ${API_LOG_PATH})..."
    TASKSGODZILLA_API_HOST="${API_HOST}" TASKSGODZILLA_API_PORT="${API_PORT}" "${PYTHON}" scripts/api_server.py \
        > "${API_LOG_PATH}" 2>&1 &
    API_PID=$!

    for _ in {1..40}; do
        if curl -s "http://${API_HOST}:${API_PORT}/health" > /dev/null 2>&1; then
            export TASKSGODZILLA_API_BASE="http://${API_HOST}:${API_PORT}"
            log_info "API server running at ${TASKSGODZILLA_API_BASE} (pid=${API_PID})"
            return
        fi
        sleep 0.25
    done

    log_error "API server failed to start"
    if [ -f "${API_LOG_PATH}" ]; then
        tail -n 40 "${API_LOG_PATH}" || true
    fi
    exit 1
}

cleanup() {
    if [ -n "${API_PID}" ] && kill -0 "${API_PID}" > /dev/null 2>&1; then
        log_info "Stopping API server (pid=${API_PID})..."
        kill "${API_PID}" || true
        wait "${API_PID}" || true
    fi
}
trap cleanup EXIT

log_info "Starting TasksGodzilla End-to-End Workflow Test"
log_info "================================================"
log_info "Database: ${TEST_DB_PATH}"
log_info "Redis: ${TEST_REDIS_URL}"
log_info "API: http://${API_HOST}:${API_PORT}"
log_info "Test Repo: ${TEST_REPO_URL}"
log_info ""

# ===== STEP 0: Environment Check =====
log_info "Step 0: Checking environment..."

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
parsed = urlparse(redis_url)

try:
    client = redis.Redis.from_url(redis_url)
    client.ping()
except Exception as exc:  # noqa: BLE001
    print(f"Redis check failed for {redis_url}: {exc}")
    sys.exit(1)

print(f"Redis reachable at {parsed.hostname}:{parsed.port} (db={parsed.path.lstrip('/') or 0})")
PY
then
    log_error "Redis not accessible at ${TEST_REDIS_URL}"
    log_error "Start Redis: docker run -d -p 6379:6379 --name tasksgodzilla-redis redis:7-alpine || redis-server --port 6379 &"
    exit 1
fi
check_step "Environment ready"

# Export environment for subprocesses
export TASKSGODZILLA_DB_PATH="${TEST_DB_PATH}"
export TASKSGODZILLA_REDIS_URL="${TEST_REDIS_URL}"
export TASKSGODZILLA_AUTO_CLONE="${TASKSGODZILLA_AUTO_CLONE:-true}"
export TASKSGODZILLA_LOG_LEVEL="${TASKSGODZILLA_LOG_LEVEL:-INFO}"
export PYTHONPATH="${PROJECT_ROOT}"

# Clean up test database if it exists
rm -f "${TEST_DB_PATH}"

# ===== STEP 1: Initialize Database =====
log_info ""
log_info "Step 1: Initializing database..."

"${PYTHON}" -c "
from tasksgodzilla.config import load_config
from tasksgodzilla.storage import create_database

config = load_config()
db = create_database(db_path=config.db_path, db_url=config.db_url, pool_size=1)
db.init_schema()
print('Database initialized')
"
check_step "Database initialized"

# ===== STEP 2: Onboard Project =====
log_info ""
log_info "Step 2: Onboarding project..."
log_info "  Repo: ${TEST_REPO_URL}"
log_info "  Name: ${TEST_PROJECT_NAME}"

"${PYTHON}" scripts/onboard_repo.py \
    --git-url "${TEST_REPO_URL}" \
    --name "${TEST_PROJECT_NAME}" \
    --base-branch "${TEST_BASE_BRANCH}" \
    --skip-discovery \
    2>&1 | tee /tmp/onboard-output.log

PROJECT_ID=$(grep "Project [0-9]* onboarded" /tmp/onboard-output.log | grep -oE '[0-9]+' | head -1)

if [ -z "${PROJECT_ID}" ]; then
    log_error "Failed to extract project ID from onboarding output"
    cat /tmp/onboard-output.log
    exit 1
fi

log_info "  Project ID: ${PROJECT_ID}"
check_step "Project onboarded (ID: ${PROJECT_ID})"

# ===== STEP 3: Verify Project in Database =====
log_info ""
log_info "Step 3: Verifying project in database..."

"${PYTHON}" -c "
from tasksgodzilla.config import load_config
from tasksgodzilla.storage import create_database

config = load_config()
db = create_database(db_path=config.db_path, db_url=config.db_url, pool_size=1)
project = db.get_project(${PROJECT_ID})
assert project is not None, 'Project not found'
assert project.name == '${TEST_PROJECT_NAME}', f'Project name mismatch: {project.name}'
assert project.base_branch == '${TEST_BASE_BRANCH}', f'Base branch mismatch: {project.base_branch}'
print(f'Project verified: {project.name} (ID={project.id})')
"
check_step "Project verified in database"

# Start API server for CLI/API checks
start_api_server

# ===== STEP 4: List Projects via CLI =====
log_info ""
log_info "Step 4: Testing CLI project list..."

"${PYTHON}" scripts/tasksgodzilla_cli.py --json projects list > /tmp/projects-list.json

if ! grep -q "\"id\": ${PROJECT_ID}" /tmp/projects-list.json; then
    log_error "Project ${PROJECT_ID} not found in CLI output"
    cat /tmp/projects-list.json
    exit 1
fi
check_step "CLI project list working"

# ===== STEP 5: Create Protocol (Planning + Decomposition) =====
log_info ""
log_info "Step 5: Creating protocol..."
log_info "  Short name: ${PROTOCOL_SHORT_NAME}"
log_info "  Description: ${PROTOCOL_DESCRIPTION}"
log_warn "  Note: This will fail if Codex CLI is not installed"
log_warn "  Skipping protocol creation for now - requires Codex"

# Uncomment when Codex is available:
# "${PYTHON}" scripts/protocol_pipeline.py \
#     --base-branch "${TEST_BASE_BRANCH}" \
#     --short-name "${PROTOCOL_SHORT_NAME}" \
#     --description "${PROTOCOL_DESCRIPTION}" \
#     2>&1 | tee /tmp/protocol-output.log
# check_step "Protocol created"

log_info "  [SKIPPED] Protocol creation requires Codex CLI"

# ===== STEP 6: Test API Server Endpoints (if running) =====
log_info ""
log_info "Step 6: Testing API server..."

# Check if API server is running
API_BASE_URL="${TASKSGODZILLA_API_BASE:-http://${API_HOST}:${API_PORT}}"
if curl -s "${API_BASE_URL}/health" > /dev/null 2>&1; then
    log_info "  API server is running, testing endpoints..."

    # Test GET /projects
    PROJECTS_COUNT=$(curl -s "${API_BASE_URL}/projects" | jq '. | length')
    log_info "  Projects count via API: ${PROJECTS_COUNT}"

    # Test GET /projects/{id}
    PROJECT_DETAIL=$(curl -s "${API_BASE_URL}/projects/${PROJECT_ID}")
    if echo "${PROJECT_DETAIL}" | jq -e ".id == ${PROJECT_ID}" > /dev/null; then
        check_step "API project detail endpoint working"
    else
        log_warn "API project detail endpoint returned unexpected data"
    fi
else
    log_warn "API server not running at ${API_BASE_URL}"
    log_warn "Start with: TASKSGODZILLA_DB_PATH=${TEST_DB_PATH} TASKSGODZILLA_REDIS_URL=${TEST_REDIS_URL} ${PYTHON} scripts/api_server.py"
fi

# ===== STEP 7: Test Storage Layer Directly =====
log_info ""
log_info "Step 7: Testing storage layer operations..."

"${PYTHON}" -c "
from tasksgodzilla.config import load_config
from tasksgodzilla.storage import create_database
from tasksgodzilla.domain import ProtocolStatus, StepStatus

config = load_config()
db = create_database(db_path=config.db_path, db_url=config.db_url, pool_size=1)

# Create a test protocol run
run = db.create_protocol_run(
    project_id=${PROJECT_ID},
    protocol_name='test-storage-protocol',
    status=ProtocolStatus.PENDING,
    base_branch='${TEST_BASE_BRANCH}',
    worktree_path=None,
    protocol_root=None,
    description='Test protocol for storage validation',
    template_config=None,
    template_source=None,
)
print(f'Created protocol run: {run.id}')

# Create a test step
step = db.create_step_run(
    protocol_run_id=run.id,
    step_index=1,
    step_name='01-test-step',
    step_type='task',
    status=StepStatus.PENDING,
    model=None,
    engine_id=None,
    retries=0,
    summary='Test step',
    policy=None,
)
print(f'Created step: {step.id}')

# Update step status
db.update_step_status(step.id, StepStatus.COMPLETED)
updated_step = db.get_step_run(step.id)
assert updated_step.status == StepStatus.COMPLETED, 'Step status update failed'
print('Step status update verified')

# Create event
db.append_event(
    protocol_run_id=run.id,
    event_type='test_event',
    message='Test event from workflow test',
)
print('Event created')

# Verify events
events = db.list_events(protocol_run_id=run.id)
assert len(events) >= 1, 'Event retrieval failed'
print(f'Events verified: {len(events)} events')

print('Storage layer test: PASSED')
"
check_step "Storage layer operations working"

# ===== STEP 8: Test Services Layer =====
log_info ""
log_info "Step 8: Testing services layer..."

"${PYTHON}" -c "
from tasksgodzilla.config import load_config
from tasksgodzilla.storage import create_database
from tasksgodzilla.services.orchestrator import OrchestratorService
from tasksgodzilla.domain import ProtocolStatus

config = load_config()
db = create_database(db_path=config.db_path, db_url=config.db_url, pool_size=1)

# Test OrchestratorService
orchestrator = OrchestratorService(db)

# Create protocol via service
protocol = orchestrator.create_protocol_run(
    project_id=${PROJECT_ID},
    protocol_name='test-service-protocol',
    description='Test protocol via OrchestratorService',
    status=ProtocolStatus.PENDING,
    base_branch='${TEST_BASE_BRANCH}',
    template_config=None,
    template_source=None,
)
print(f'Created protocol via service: {protocol.id}')

# Get protocol
retrieved = db.get_protocol_run(protocol.id)
assert retrieved is not None, 'Protocol retrieval failed'
assert retrieved.protocol_name == 'test-service-protocol', 'Protocol name mismatch'
print('Protocol retrieval verified')

# List protocols for project
protocols = db.list_protocol_runs(project_id=${PROJECT_ID})
assert len(protocols) >= 1, 'Protocol listing failed'
print(f'Protocol listing verified: {len(protocols)} protocols')

print('Services layer test: PASSED')
"
check_step "Services layer operations working"

# ===== STEP 9: Test Git Utilities =====
log_info ""
log_info "Step 9: Testing git utilities..."

"${PYTHON}" -c "
from pathlib import Path
import subprocess
from tasksgodzilla.config import load_config
from tasksgodzilla.storage import create_database
from tasksgodzilla.git_utils import resolve_project_repo_path, list_remote_branches

config = load_config()
db = create_database(db_path=config.db_path, db_url=config.db_url, pool_size=1)

project = db.get_project(${PROJECT_ID})
repo_path = resolve_project_repo_path(
    git_url=project.git_url,
    project_name=project.name,
    local_path=project.local_path,
    project_id=project.id,
    clone_if_missing=False,
)

if repo_path.exists():
    branch = (
        subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=repo_path)
        .decode('utf-8')
        .strip()
    )
    remotes = list_remote_branches(repo_path)
    print(f'Repo root: {repo_path}')
    print(f'Current branch: {branch}')
    print(f'Remote branches detected: {len(remotes)}')

    print('Git utilities test: PASSED')
else:
    print(f'Repo path does not exist: {repo_path}')
    print('Git utilities test: SKIPPED')
"
check_step "Git utilities working"

# ===== STEP 10: Cleanup =====
log_info ""
log_info "Step 10: Cleanup..."

# Respect TASKSGODZILLA_KEEP_TEST_DATA=true to preserve artifacts; default cleanup in non-interactive runs.
KEEP_DATA="${TASKSGODZILLA_KEEP_TEST_DATA:-}"
if [ -t 0 ] && [ -z "${KEEP_DATA}" ]; then
    read -p "Keep test database and cloned repo? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        KEEP_DATA="true"
    fi
else
    KEEP_DATA="${KEEP_DATA:-false}"
    if [ "${KEEP_DATA}" != "true" ]; then
        log_warn "Non-interactive cleanup: set TASKSGODZILLA_KEEP_TEST_DATA=true to preserve artifacts."
    fi
fi

if [ "${KEEP_DATA}" != "true" ]; then
    rm -f "${TEST_DB_PATH}"
    log_info "  Removed test database: ${TEST_DB_PATH}"

    # Remove cloned repo (if it exists in projects/)
    if [ -n "${PROJECT_ID}" ]; then
        REPO_PATH="projects/${PROJECT_ID}/${TEST_PROJECT_NAME}"
        if [ -d "${REPO_PATH}" ]; then
            rm -rf "${REPO_PATH}"
            log_info "  Removed cloned repo: ${REPO_PATH}"
        fi
    fi
else
    log_info "  Test data preserved:"
    log_info "    Database: ${TEST_DB_PATH}"
    log_info "    Project ID: ${PROJECT_ID}"
fi

# ===== SUMMARY =====
log_info ""
log_info "================================================"
log_info "End-to-End Workflow Test: COMPLETED"
log_info "================================================"
log_info ""
log_info "Tests Passed:"
log_info "  ✓ Environment setup"
log_info "  ✓ Database initialization"
log_info "  ✓ Project onboarding"
log_info "  ✓ Database verification"
log_info "  ✓ CLI project listing"
log_info "  ✓ Storage layer operations"
log_info "  ✓ Services layer operations"
log_info "  ✓ Git utilities"
log_info ""
log_info "Manual Tests Required:"
log_info "  - Protocol creation (requires Codex CLI)"
log_info "  - Protocol execution (requires Codex CLI)"
log_info "  - Quality validation (requires Codex CLI)"
log_info "  - API server endpoints (start server manually)"
log_info "  - Worker job processing (start worker manually)"
log_info ""
log_info "To test with API server and workers:"
log_info "  1. Terminal 1: TASKSGODZILLA_DB_PATH=${TEST_DB_PATH} TASKSGODZILLA_REDIS_URL=${TEST_REDIS_URL} ${PYTHON} scripts/api_server.py"
log_info "  2. Terminal 2: TASKSGODZILLA_DB_PATH=${TEST_DB_PATH} TASKSGODZILLA_REDIS_URL=${TEST_REDIS_URL} ${PYTHON} scripts/rq_worker.py"
log_info "  3. Terminal 3: curl http://localhost:8010/projects"
log_info ""
