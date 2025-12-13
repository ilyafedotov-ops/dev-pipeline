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
PY_BIN="${PY_BIN:-${VENV_PATH}/bin/python}"

if [ ! -x "${PY_BIN}" ]; then
  ci_error "typecheck python missing" "py_bin=${PY_BIN} hint=run_bootstrap"
  exit 1
fi

export PYTHONPATH="${PYTHONPATH:-.}"
export TASKSGODZILLA_DB_PATH="${TASKSGODZILLA_DB_PATH:-/tmp/tasksgodzilla-ci.sqlite}"
export TASKSGODZILLA_REDIS_URL="${TASKSGODZILLA_REDIS_URL:-redis://localhost:6380/15}"

"${PY_BIN}" -m compileall -q tasksgodzilla scripts

"${PY_BIN}" - <<'PY'
import importlib
modules = [
    "tasksgodzilla.config",
    "tasksgodzilla.api.app",
    "scripts.api_server",
    "scripts.protocol_pipeline",
    "scripts.quality_orchestrator",
]
for mod in modules:
    importlib.import_module(mod)
print("[ci] typecheck: import smoke OK for", ", ".join(modules))
PY

ci_info "typecheck import smoke OK"
report_status success
