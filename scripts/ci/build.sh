#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
report_status() {
  if [ -x "${SCRIPT_DIR}/report.sh" ]; then
    "${SCRIPT_DIR}/report.sh" "$1" || true
  fi
}
trap 'report_status failure' ERR

if command -v docker >/dev/null 2>&1; then
  DOCKER_BUILDKIT=1 docker build --pull -t deksdenflow-ci .
  echo "[ci] build: docker image built (tag=deksdenflow-ci)."
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose config -q
  echo "[ci] build: docker not available; validated docker-compose config instead."
else
  echo "[ci] build: docker/docker-compose not available; skipping build."
fi

report_status success
