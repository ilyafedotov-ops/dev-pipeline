#!/bin/bash
# Local development manager for DevGodzilla.
# Runs frontend + backend on the host and infra services in Docker.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.local.yml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}$*${NC}"; }
warn() { echo -e "${YELLOW}$*${NC}"; }
err() { echo -e "${RED}$*${NC}" 1>&2; }

die() {
  err "$*"
  exit 1
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

compose_cmd() {
  if command_exists docker && docker compose version >/dev/null 2>&1; then
    docker compose -f "$COMPOSE_FILE" "$@"
  elif command_exists docker-compose; then
    docker-compose -f "$COMPOSE_FILE" "$@"
  else
    die "docker compose not found. Install Docker Desktop or docker-compose."
  fi
}

ensure_docker() {
  command_exists docker || die "docker not found."
  docker info >/dev/null 2>&1 || die "docker is not running."
}

python_bin() {
  if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
    echo "$PROJECT_DIR/.venv/bin/python"
  elif command_exists python3; then
    echo "python3"
  elif command_exists python; then
    echo "python"
  else
    die "python not found. Create a venv with scripts/ci/bootstrap.sh."
  fi
}

export_env() {
  export DEVGODZILLA_DB_URL="${DEVGODZILLA_DB_URL:-postgresql://devgodzilla:changeme@localhost:5432/devgodzilla_db}"
  export DEVGODZILLA_LOG_LEVEL="${DEVGODZILLA_LOG_LEVEL:-DEBUG}"
  export DEVGODZILLA_WINDMILL_URL="${DEVGODZILLA_WINDMILL_URL:-http://localhost:8001}"
  export DEVGODZILLA_WINDMILL_WORKSPACE="${DEVGODZILLA_WINDMILL_WORKSPACE:-demo1}"
  export DEVGODZILLA_WINDMILL_ENV_FILE="${DEVGODZILLA_WINDMILL_ENV_FILE:-$PROJECT_DIR/windmill/apps/devgodzilla-react-app/.env.development}"
  export DEVGODZILLA_PROJECTS_ROOT="${DEVGODZILLA_PROJECTS_ROOT:-$PROJECT_DIR/projects}"
}

print_usage() {
  cat <<EOF
Usage: scripts/run-local-dev.sh <command>

Commands:
  up          Start Docker infra (db, redis, windmill, nginx, workers)
  down        Stop Docker infra
  clean       Stop Docker infra and remove volumes
  status      Show Docker infra status
  logs        Tail Docker infra logs
  backend     Run backend locally (uvicorn --reload)
  frontend    Run frontend locally (pnpm dev)
  dev         Start infra + run backend + frontend together
  import      Import Windmill assets into local Windmill
  env         Print local dev environment variables
  help        Show this help
EOF
}

infra_up() {
  ensure_docker
  compose_cmd up -d db redis windmill windmill_worker windmill_worker_native lsp nginx
  log "Infra started. Nginx: http://localhost:8080  Windmill: http://localhost:8001"
}

infra_down() {
  ensure_docker
  compose_cmd down
}

infra_clean() {
  ensure_docker
  compose_cmd down -v
}

infra_status() {
  ensure_docker
  compose_cmd ps
}

infra_logs() {
  ensure_docker
  compose_cmd logs -f --tail=200
}

run_backend() {
  export_env
  local py
  py="$(python_bin)"
  log "Starting backend (uvicorn) on :8000"
  "$py" -m uvicorn devgodzilla.api.app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --reload-dir "$PROJECT_DIR/devgodzilla"
}

run_frontend() {
  command_exists pnpm || die "pnpm not found. Install pnpm before running frontend."
  export NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://localhost:8080}"
  log "Starting frontend (Next.js) on :3000"
  (cd "$PROJECT_DIR/frontend" && pnpm dev)
}

windmill_import() {
  export_env
  local token_file="$DEVGODZILLA_WINDMILL_ENV_FILE"
  if [[ ! -f "$token_file" ]]; then
    warn "Token file not found: $token_file"
    warn "Set DEVGODZILLA_WINDMILL_ENV_FILE or export DEVGODZILLA_WINDMILL_TOKEN."
  fi
  local py
  py="$(python_bin)"
  "$py" windmill/import_to_windmill.py \
    --url "$DEVGODZILLA_WINDMILL_URL" \
    --workspace "$DEVGODZILLA_WINDMILL_WORKSPACE" \
    --token-file "$token_file"
}

print_env() {
  export_env
  cat <<EOF
DEVGODZILLA_DB_URL=$DEVGODZILLA_DB_URL
DEVGODZILLA_LOG_LEVEL=$DEVGODZILLA_LOG_LEVEL
DEVGODZILLA_WINDMILL_URL=$DEVGODZILLA_WINDMILL_URL
DEVGODZILLA_WINDMILL_WORKSPACE=$DEVGODZILLA_WINDMILL_WORKSPACE
DEVGODZILLA_WINDMILL_ENV_FILE=$DEVGODZILLA_WINDMILL_ENV_FILE
DEVGODZILLA_PROJECTS_ROOT=$DEVGODZILLA_PROJECTS_ROOT
NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL:-http://localhost:8080}
EOF
}

run_dev() {
  infra_up
  export_env
  local backend_pid=""
  local frontend_pid=""

  run_backend &
  backend_pid=$!

  run_frontend &
  frontend_pid=$!

  trap 'kill "$backend_pid" "$frontend_pid" 2>/dev/null || true' EXIT INT TERM
  wait -n "$backend_pid" "$frontend_pid"
}

main() {
  local cmd="${1:-help}"
  case "$cmd" in
    up) infra_up ;;
    down) infra_down ;;
    clean) infra_clean ;;
    status) infra_status ;;
    logs) infra_logs ;;
    backend) run_backend ;;
    frontend) run_frontend ;;
    dev) run_dev ;;
    import) windmill_import ;;
    env) print_env ;;
    help|-h|--help) print_usage ;;
    *) err "Unknown command: $cmd"; print_usage; exit 1 ;;
  esac
}

main "$@"
