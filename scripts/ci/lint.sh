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
RUFF_BIN="${RUFF_BIN:-${VENV_PATH}/bin/ruff}"

if [ ! -x "${RUFF_BIN}" ]; then
  ci_error "lint ruff missing" "ruff_bin=${RUFF_BIN} hint=run_bootstrap"
  exit 1
fi

export PYTHONPATH="${PYTHONPATH:-.}"

# Focus on runtime-breaking issues (syntax/undefined names).
"${RUFF_BIN}" check tasksgodzilla scripts tests --select E9,F63,F7,F82
ci_info "lint passed" "checks=E9,F63,F7,F82"

report_status success
