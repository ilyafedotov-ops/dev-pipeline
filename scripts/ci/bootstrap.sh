#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
report_status() {
  if [ -x "${SCRIPT_DIR}/report.sh" ]; then
    "${SCRIPT_DIR}/report.sh" "$1" || true
  fi
}
trap 'report_status failure' ERR

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_PATH="${VENV_PATH:-.venv}"
REQ_FILE="${REQ_FILE:-requirements-orchestrator.txt}"

if [ ! -x "${VENV_PATH}/bin/python" ]; then
  "${PYTHON_BIN}" -m venv "${VENV_PATH}"
fi

"${VENV_PATH}/bin/python" -m pip install --upgrade pip
"${VENV_PATH}/bin/pip" install -r "${REQ_FILE}" ruff

export DEKSDENFLOW_DB_PATH="${DEKSDENFLOW_DB_PATH:-/tmp/deksdenflow-ci.sqlite}"
export DEKSDENFLOW_REDIS_URL="${DEKSDENFLOW_REDIS_URL:-fakeredis://}"

echo "[ci] bootstrap: ready (venv=${VENV_PATH}, db=${DEKSDENFLOW_DB_PATH}, redis=${DEKSDENFLOW_REDIS_URL})"

report_status success
