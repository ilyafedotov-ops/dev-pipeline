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

if ! command -v opencode >/dev/null 2>&1; then
  ci_error "test opencode missing" "hint=install_opencode_and_authenticate"
  exit 1
fi

# Run unit tests (fast, deterministic - uses stub opencode)
ci_info "running unit tests" "scope=unit"
"${PYTEST_BIN}" -q --disable-warnings --maxfail=1 tests/test_devgodzilla_*.py -k "not integration"

# Run real E2E tests with actual opencode CLI
ci_info "running real agent E2E tests" "scope=e2e engine=opencode"
export DEVGODZILLA_RUN_E2E_REAL_AGENT=1
"${PYTEST_BIN}" -q --disable-warnings --maxfail=1 tests/e2e/test_devgodzilla_cli_real_agent.py

ci_info "all tests completed" "result=pass unit=pass e2e=pass"
report_status success
