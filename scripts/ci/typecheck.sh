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
PY_BIN="${PY_BIN:-${VENV_PATH}/bin/python}"

if [ ! -x "${PY_BIN}" ]; then
  echo "[ci] typecheck: python not found at ${PY_BIN}. Did bootstrap run?" >&2
  exit 1
fi

export PYTHONPATH="${PYTHONPATH:-.}"
export DEKSDENFLOW_DB_PATH="${DEKSDENFLOW_DB_PATH:-/tmp/deksdenflow-ci.sqlite}"
export DEKSDENFLOW_REDIS_URL="${DEKSDENFLOW_REDIS_URL:-fakeredis://}"

"${PY_BIN}" -m compileall -q deksdenflow scripts

"${PY_BIN}" - <<'PY'
import importlib
modules = [
    "deksdenflow.config",
    "deksdenflow.api.app",
    "scripts.api_server",
    "scripts.protocol_pipeline",
    "scripts.quality_orchestrator",
]
for mod in modules:
    importlib.import_module(mod)
print("[ci] typecheck: import smoke OK for", ", ".join(modules))
PY

report_status success
