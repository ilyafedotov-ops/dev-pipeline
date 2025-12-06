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
PYTEST_BIN="${PYTEST_BIN:-${VENV_PATH}/bin/pytest}"

if [ ! -x "${PYTEST_BIN}" ]; then
  echo "[ci] test: pytest not found at ${PYTEST_BIN}. Did bootstrap run?" >&2
  exit 1
fi

export PYTHONPATH="${PYTHONPATH:-.}"
export DEKSDENFLOW_DB_PATH="${DEKSDENFLOW_DB_PATH:-/tmp/deksdenflow-test.sqlite}"
export DEKSDENFLOW_REDIS_URL="${DEKSDENFLOW_REDIS_URL:-fakeredis://}"

"${PYTEST_BIN}" -q --disable-warnings --maxfail=1

report_status success
