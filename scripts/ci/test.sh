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
# Keep unit tests deterministic; many tests provision temporary SQLite DBs.
export DEVGODZILLA_DB_URL=""
export DEVGODZILLA_DB_PATH="${DEVGODZILLA_DB_PATH:-.pytest-devgodzilla.sqlite}"
export DEVGODZILLA_API_TOKEN=""

# Run unit tests (fast, deterministic - uses stub opencode)
ci_info "running unit tests" "scope=unit"
"${PYTEST_BIN}" -q --disable-warnings --maxfail=1 tests/test_devgodzilla_*.py -k "not integration"

# Optional real E2E tests with actual opencode CLI (disabled in standard CI)
if [ "${DEVGODZILLA_RUN_E2E_REAL_AGENT:-}" = "1" ]; then
  if ! command -v opencode >/dev/null 2>&1; then
    ci_error "test opencode missing" "hint=install_opencode_and_authenticate"
    exit 1
  fi
  ci_info "running real agent E2E tests" "scope=e2e engine=opencode"
  "${PYTEST_BIN}" -q --disable-warnings --maxfail=1 \
    tests/e2e/test_devgodzilla_cli_real_agent.py \
    tests/test_devgodzilla_project_speckit_integration.py
  ci_info "all tests completed" "result=pass unit=pass e2e=pass"
else
  ci_warn "real-agent e2e skipped" "reason=missing_env DEVGODZILLA_RUN_E2E_REAL_AGENT=1"
  ci_info "all tests completed" "result=pass unit=pass e2e=skipped"
fi

report_status success
