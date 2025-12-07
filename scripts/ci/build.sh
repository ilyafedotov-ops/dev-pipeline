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

if command -v docker >/dev/null 2>&1; then
  DOCKER_BUILDKIT=1 docker build --pull -t tasksgodzilla-ci .
  ci_info "build docker image" "tag=tasksgodzilla-ci"
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose config -q
  ci_warn "build skipped docker" "reason=docker_missing action=validate_compose"
else
  ci_warn "build skipped" "reason=docker_and_compose_missing"
fi

report_status success
