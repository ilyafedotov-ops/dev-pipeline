#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONSOLE_DIR="${ROOT_DIR}/web/console"
OUT_DIR="${ROOT_DIR}/tasksgodzilla/api/frontend_dist"

if [ ! -d "${CONSOLE_DIR}" ]; then
  echo "Console workspace not found at ${CONSOLE_DIR}" >&2
  exit 1
fi

echo "Building web console…"
(cd "${CONSOLE_DIR}" && npm install && npm run build)

echo "Publishing to ${OUT_DIR}…"
rm -rf "${OUT_DIR}"
mkdir -p "${OUT_DIR}"
cp -R "${CONSOLE_DIR}/dist/." "${OUT_DIR}/"

echo "Done. Serve at /console (restart API)."

