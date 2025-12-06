#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
report_status() {
  if [ -x "${SCRIPT_DIR}/report.sh" ]; then
    "${SCRIPT_DIR}/report.sh" "$1" || true
  fi
}
trap 'report_status failure' ERR

VENV_PATH="${VENV_PATH:-.venv}"
RUFF_BIN="${RUFF_BIN:-${VENV_PATH}/bin/ruff}"

if [ ! -x "${RUFF_BIN}" ]; then
  echo "[ci] lint: ruff not found at ${RUFF_BIN}. Did bootstrap run?" >&2
  exit 1
fi

export PYTHONPATH="${PYTHONPATH:-.}"

# Focus on runtime-breaking issues (syntax/undefined names).
"${RUFF_BIN}" check deksdenflow scripts tests --select E9,F63,F7,F82
echo "[ci] lint: ruff error checks (E9,F63,F7,F82) passed."

report_status success
