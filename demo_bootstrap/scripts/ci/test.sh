#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/logging.sh"
report_status() {
  if [ -x "${SCRIPT_DIR}/report.sh" ]; then
    "${SCRIPT_DIR}/report.sh" "$1" || true
  fi
}
trap 'report_status failure' ERR

VENV_PATH="${VENV_PATH:-.venv}"
PYTEST_BIN="${PYTEST_BIN:-${VENV_PATH}/bin/pytest}"

if [ ! -x "${PYTEST_BIN}" ]; then
  ci_error "test pytest missing" "pytest_bin=${PYTEST_BIN} hint=run_bootstrap"
  exit 1
fi

export PYTHONPATH="${PYTHONPATH:-.}"
export TASKSGODZILLA_DB_PATH="${TASKSGODZILLA_DB_PATH:-/tmp/tasksgodzilla-test.sqlite}"
export TASKSGODZILLA_REDIS_URL="${TASKSGODZILLA_REDIS_URL:-redis://localhost:6379/15}"
export TASKSGODZILLA_AUTO_CLONE="${TASKSGODZILLA_AUTO_CLONE:-false}"

"${PYTEST_BIN}" -q --disable-warnings --maxfail=1

ci_info "tests completed" "result=pass"
report_status success
