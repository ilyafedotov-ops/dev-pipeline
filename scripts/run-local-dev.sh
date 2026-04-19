#!/bin/bash
# Local development manager for DevGodzilla.
# Runs frontend + backend on the host and infra services in Docker.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"

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
  export WINDMILL_SUPERADMIN_SECRET="${WINDMILL_SUPERADMIN_SECRET:-devgodzilla-local-superadmin}"
  export DEVGODZILLA_WINDMILL_TOKEN="${DEVGODZILLA_WINDMILL_TOKEN:-$WINDMILL_SUPERADMIN_SECRET}"
  export DEVGODZILLA_WINDMILL_WORKSPACE="${DEVGODZILLA_WINDMILL_WORKSPACE:-demo1}"
  export DEVGODZILLA_WINDMILL_ENV_FILE="${DEVGODZILLA_WINDMILL_ENV_FILE:-$PROJECT_DIR/windmill/apps/devgodzilla-react-app/.env.development}"
  export DEVGODZILLA_WINDMILL_ONBOARD_SCRIPT_PATH="${DEVGODZILLA_WINDMILL_ONBOARD_SCRIPT_PATH:-u/devgodzilla/project_onboard_api}"
  export DEVGODZILLA_WINDMILL_IMPORT_ROOT="${DEVGODZILLA_WINDMILL_IMPORT_ROOT:-$PROJECT_DIR/windmill}"
  export WINDMILL_JOB_TIMEOUT_SECONDS="${WINDMILL_JOB_TIMEOUT_SECONDS:-3600}"
  export DEVGODZILLA_PROJECTS_ROOT="${DEVGODZILLA_PROJECTS_ROOT:-$PROJECT_DIR/projects}"

  if [[ -n "${DEVGODZILLA_DB_URL:-}" && -n "${DEVGODZILLA_DB_PATH:-}" ]]; then
    die "Configure exactly one database backend: set either DEVGODZILLA_DB_URL or DEVGODZILLA_DB_PATH."
  fi
}

RUN_DIR="$PROJECT_DIR/runs/local-dev"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
FRONTEND_HOSTNAME="${FRONTEND_HOSTNAME:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"

ensure_run_dir() {
  mkdir -p "$RUN_DIR"
}

pid_is_alive() {
  local pid="$1"
  kill -0 "$pid" >/dev/null 2>&1
}

bash_supports_wait_n() {
  # `wait -n` was added in Bash 4.3. macOS ships Bash 3.2 by default.
  local major="${BASH_VERSINFO[0]:-0}"
  local minor="${BASH_VERSINFO[1]:-0}"
  if ((major > 4)); then
    return 0
  fi
  if ((major == 4 && minor >= 3)); then
    return 0
  fi
  return 1
}

wait_any_pid() {
  # Wait until *any* of the given child PIDs exits, and return that PID's exit status.
  # Uses `wait -n` when available; otherwise falls back to a small polling loop
  # for compatibility with older Bash (notably macOS /bin/bash 3.2).
  local pids=("$@")
  if [[ "${#pids[@]}" -eq 0 ]]; then
    return 0
  fi

  if bash_supports_wait_n; then
    wait -n "${pids[@]}"
    return $?
  fi

  while true; do
    local pid=""
    for pid in "${pids[@]}"; do
      if ! kill -0 "$pid" >/dev/null 2>&1; then
        local status=0
        wait "$pid" || status=$?
        return "$status"
      fi
    done
    sleep 0.2
  done
}

pid_cwd() {
  local pid="$1"
  if [[ -e "/proc/$pid/cwd" ]]; then
    readlink "/proc/$pid/cwd" 2>/dev/null || true
    return 0
  fi

  # macOS fallback (no /proc): use lsof to read cwd.
  if command_exists lsof; then
    lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1 || true
  fi
}

pid_cmdline() {
  local pid="$1"
  if [[ -r "/proc/$pid/cmdline" ]]; then
    tr '\0' ' ' <"/proc/$pid/cmdline"
    return 0
  fi

  # macOS fallback (no /proc): `ps` provides the full command.
  if command_exists ps; then
    ps -o command= -p "$pid" 2>/dev/null | head -n 1 || true
    return 0
  fi

  return 1
}

pid_ppid() {
  local pid="$1"
  if [[ -r "/proc/$pid/status" ]]; then
    awk '/^PPid:/{print $2}' "/proc/$pid/status" 2>/dev/null || true
    return 0
  fi

  # macOS fallback (no /proc): use ps.
  if command_exists ps; then
    ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ' | head -n 1 || true
    return 0
  fi

  return 0
}

find_pids_listening_on_port() {
  local port="$1"
  if command_exists ss; then
    ss -lptn "sport = :$port" 2>/dev/null | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true
    return 0
  fi

  if command_exists lsof; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | sort -u || true
    return 0
  fi

  return 0
}

find_pid_listening_on_port() {
  local port="$1"
  find_pids_listening_on_port "$port" | head -n 1 || true
}

stop_pid_gracefully() {
  local pid="$1"
  local name="$2"

  if ! pid_is_alive "$pid"; then
    return 0
  fi

  log "Stopping ${name} (pid=${pid})"
  kill "$pid" 2>/dev/null || true

  local i
  for i in {1..40}; do
    if ! pid_is_alive "$pid"; then
      return 0
    fi
    sleep 0.1
  done

  warn "${name} did not stop in time; sending SIGKILL (pid=${pid})"
  kill -9 "$pid" 2>/dev/null || true
}

frontend_lock_file() {
  echo "$PROJECT_DIR/frontend/.next/dev/lock"
}

clear_frontend_lock_if_safe() {
  local lock_file
  lock_file="$(frontend_lock_file)"
  [[ -f "$lock_file" ]] || return 0

  local pid=""
  for pid in $(find_pids_listening_on_port "$FRONTEND_PORT"); do
    if [[ -n "$pid" ]] && pid_is_alive "$pid"; then
      return 0
    fi
  done

  warn "Removing stale Next.js dev lock: $lock_file"
  rm -f "$lock_file"
}

frontend_pid_matches_project() {
  local pid="$1"
  local cwd
  cwd="$(pid_cwd "$pid")"
  [[ -n "$cwd" ]] || return 1
  [[ "$cwd" == "$PROJECT_DIR/frontend"* ]] || return 1
  return 0
}

backend_pid_matches_project() {
  local pid="$1"
  local cwd
  cwd="$(pid_cwd "$pid")"
  [[ -n "$cwd" ]] || return 1
  [[ "$cwd" == "$PROJECT_DIR"* ]] || return 1

  local cmdline=""
  cmdline="$(pid_cmdline "$pid" 2>/dev/null || true)"
  [[ "$cmdline" == *"uvicorn"* ]] || return 1
  [[ "$cmdline" == *"devgodzilla.api.app:app"* ]] || return 1
  return 0
}

resolve_backend_controller_pid_from_pid() {
  local pid="$1"
  local depth=0

  while [[ -n "$pid" && "$pid" != "0" && "$pid" != "1" && "$depth" -lt 12 ]]; do
    if pid_is_alive "$pid" && backend_pid_matches_project "$pid"; then
      echo "$pid"
      return 0
    fi

    pid="$(pid_ppid "$pid")"
    depth=$((depth + 1))
  done

  return 0
}

frontend_status() {
  local pid=""
  pid="$(find_pid_listening_on_port "$FRONTEND_PORT")"
  if [[ -z "$pid" ]] || ! pid_is_alive "$pid"; then
    echo "frontend: stopped (port $FRONTEND_PORT)"
    return 0
  fi

  local cwd
  cwd="$(pid_cwd "$pid")"
  echo "frontend: running (pid $pid, port $FRONTEND_PORT, cwd $cwd)"
}

backend_status() {
  local pid=""
  local controller_pid=""

  for pid in $(find_pids_listening_on_port "$BACKEND_PORT"); do
    controller_pid="$(resolve_backend_controller_pid_from_pid "$pid")"
    if [[ -n "$controller_pid" ]]; then
      break
    fi
  done

  if [[ -z "$controller_pid" ]] || ! pid_is_alive "$controller_pid"; then
    echo "backend: stopped (port $BACKEND_PORT)"
    return 0
  fi

  local cwd
  cwd="$(pid_cwd "$controller_pid")"
  echo "backend: running (pid $controller_pid, port $BACKEND_PORT, cwd $cwd)"
}

print_usage() {
  cat <<EOF
Usage: scripts/run-local-dev.sh <command>

Commands:
  up          Build and start full stack (infra + api + frontend)
  down        Stop Docker infra
  clean       Stop Docker infra and remove volumes
  status      Show Docker infra status
  logs        Tail Docker infra logs
  backend     Manage backend locally (start|stop|restart|status)
  frontend    Manage frontend locally (start|stop|restart|status)
  dev         Start infra + run backend + frontend together
  import      Import Windmill assets into local Windmill
  env         Print local dev environment variables
  help        Show this help

Notes:
  - Default backend port: 8000 (override with BACKEND_PORT)
  - Default frontend port: 3000 (override with FRONTEND_PORT)
  - Default frontend hostname: 0.0.0.0 (override with FRONTEND_HOSTNAME)
EOF
}

infra_up() {
  ensure_docker
  compose_cmd up -d --build
  log "Stack started. App: http://localhost:8080/console  Windmill: http://localhost:8080"
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

backend_stop() {
  ensure_run_dir

  local pid=""
  local controller_pid=""
  if [[ -f "$BACKEND_PID_FILE" ]]; then
    pid="$(cat "$BACKEND_PID_FILE" 2>/dev/null || true)"
    controller_pid="$(resolve_backend_controller_pid_from_pid "$pid")"
    if [[ -n "$controller_pid" ]] && pid_is_alive "$controller_pid"; then
      stop_pid_gracefully "$controller_pid" "backend"
      rm -f "$BACKEND_PID_FILE"
      return 0
    fi
    rm -f "$BACKEND_PID_FILE"
  fi

  local found_any="false"
  for pid in $(find_pids_listening_on_port "$BACKEND_PORT"); do
    found_any="true"
    controller_pid="$(resolve_backend_controller_pid_from_pid "$pid")"
    if [[ -n "$controller_pid" ]] && pid_is_alive "$controller_pid"; then
      stop_pid_gracefully "$controller_pid" "backend"
      return 0
    fi
  done

  if [[ "$found_any" == "false" ]]; then
    return 0
  fi

  die "Refusing to stop backend on port $BACKEND_PORT: port is in use but no DevGodzilla uvicorn controller process was found."
}

run_backend_foreground() {
  export_env
  local py
  py="$(python_bin)"
  log "Starting backend (uvicorn) on :$BACKEND_PORT"
  "$py" -m uvicorn devgodzilla.api.app:app \
    --host 0.0.0.0 \
    --port "$BACKEND_PORT" \
    --reload \
    --reload-dir "$PROJECT_DIR/devgodzilla"
}

frontend_stop() {
  ensure_run_dir

  local server_pid=""
  server_pid="$(find_pid_listening_on_port "$FRONTEND_PORT")"
  if [[ -n "$server_pid" ]] && pid_is_alive "$server_pid"; then
    if ! frontend_pid_matches_project "$server_pid"; then
      local cwd
      cwd="$(pid_cwd "$server_pid")"
      die "Refusing to stop frontend on port $FRONTEND_PORT (pid $server_pid, cwd $cwd): not recognized as this project's Next dev server."
    fi
    stop_pid_gracefully "$server_pid" "frontend"
  fi

  local wrapper_pid=""
  if [[ -f "$FRONTEND_PID_FILE" ]]; then
    wrapper_pid="$(cat "$FRONTEND_PID_FILE" 2>/dev/null || true)"
    if [[ -n "$wrapper_pid" ]] && pid_is_alive "$wrapper_pid" && frontend_pid_matches_project "$wrapper_pid"; then
      stop_pid_gracefully "$wrapper_pid" "frontend wrapper"
    fi
    rm -f "$FRONTEND_PID_FILE"
  fi

  clear_frontend_lock_if_safe
}

run_frontend_foreground() {
  command_exists pnpm || die "pnpm not found. Install pnpm before running frontend."
  export NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://localhost:8080}"
  log "Starting frontend (Next.js) on :$FRONTEND_PORT"
  (cd "$PROJECT_DIR/frontend" && pnpm exec next dev --hostname "$FRONTEND_HOSTNAME" --port "$FRONTEND_PORT")
}

windmill_import() {
  export_env
  local token_file="$DEVGODZILLA_WINDMILL_ENV_FILE"
  local has_env_token="0"
  if [[ -n "${DEVGODZILLA_WINDMILL_TOKEN:-}" || -n "${WINDMILL_TOKEN:-}" ]]; then
    has_env_token="1"
  fi
  if [[ ! -f "$token_file" && "$has_env_token" != "1" ]]; then
    warn "Token file not found: $token_file"
    warn "Set DEVGODZILLA_WINDMILL_ENV_FILE or export DEVGODZILLA_WINDMILL_TOKEN."
  fi
  local py
  py="$(python_bin)"
  local import_args=(
    windmill/import_to_windmill.py
    --url "$DEVGODZILLA_WINDMILL_URL"
    --workspace "$DEVGODZILLA_WINDMILL_WORKSPACE"
    --root "$DEVGODZILLA_WINDMILL_IMPORT_ROOT"
  )
  if [[ -f "$token_file" ]]; then
    import_args+=(--token-file "$token_file")
  fi
  "$py" "${import_args[@]}"

  local timeout_seconds="$WINDMILL_JOB_TIMEOUT_SECONDS"
  if [[ "$timeout_seconds" =~ ^[0-9]+$ ]]; then
    compose_cmd exec -T db psql -U postgres -d windmill_db -c \
      "INSERT INTO global_settings (name, value) VALUES ('job_default_timeout', to_jsonb(${timeout_seconds}::int)) ON CONFLICT (name) DO UPDATE SET value = EXCLUDED.value, updated_at = now();"
    log "Windmill job_default_timeout set to ${timeout_seconds}s"
  else
    warn "Skipping Windmill job_default_timeout update: WINDMILL_JOB_TIMEOUT_SECONDS is not numeric (${timeout_seconds})"
  fi
}

print_env() {
  export_env
  cat <<EOF
DEVGODZILLA_DB_URL=$DEVGODZILLA_DB_URL
DEVGODZILLA_LOG_LEVEL=$DEVGODZILLA_LOG_LEVEL
DEVGODZILLA_WINDMILL_URL=$DEVGODZILLA_WINDMILL_URL
DEVGODZILLA_WINDMILL_WORKSPACE=$DEVGODZILLA_WINDMILL_WORKSPACE
DEVGODZILLA_WINDMILL_ENV_FILE=$DEVGODZILLA_WINDMILL_ENV_FILE
DEVGODZILLA_WINDMILL_ONBOARD_SCRIPT_PATH=$DEVGODZILLA_WINDMILL_ONBOARD_SCRIPT_PATH
DEVGODZILLA_WINDMILL_IMPORT_ROOT=$DEVGODZILLA_WINDMILL_IMPORT_ROOT
WINDMILL_JOB_TIMEOUT_SECONDS=$WINDMILL_JOB_TIMEOUT_SECONDS
DEVGODZILLA_PROJECTS_ROOT=$DEVGODZILLA_PROJECTS_ROOT
NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL:-http://localhost:8080}
EOF
}

backend_cmd() {
  local action="${1:-restart}"
  case "$action" in
    start)
      local pid=""
      local controller_pid=""
      local found_any="false"

      for pid in $(find_pids_listening_on_port "$BACKEND_PORT"); do
        found_any="true"
        controller_pid="$(resolve_backend_controller_pid_from_pid "$pid")"
        if [[ -n "$controller_pid" ]] && pid_is_alive "$controller_pid"; then
          log "Backend already running (pid=$controller_pid, port=$BACKEND_PORT)"
          return 0
        fi
      done

      if [[ "$found_any" == "true" ]]; then
        die "Backend port $BACKEND_PORT is in use. Use BACKEND_PORT=... or stop the other process."
      fi

      run_backend_foreground
      ;;
    stop) backend_stop ;;
    restart) backend_stop || true; run_backend_foreground ;;
    status) backend_status ;;
    *) die "Unknown backend action: $action (expected start|stop|restart|status)" ;;
  esac
}

frontend_cmd() {
  local action="${1:-restart}"
  case "$action" in
    start)
      local pid=""
      pid="$(find_pid_listening_on_port "$FRONTEND_PORT")"
      if [[ -n "$pid" ]] && pid_is_alive "$pid"; then
        if frontend_pid_matches_project "$pid"; then
          log "Frontend already running (pid=$pid, port=$FRONTEND_PORT)"
          return 0
        fi
        local cwd
        cwd="$(pid_cwd "$pid")"
        die "Frontend port $FRONTEND_PORT is in use (pid $pid, cwd $cwd). Use FRONTEND_PORT=... or stop the other process."
      fi
      clear_frontend_lock_if_safe
      run_frontend_foreground
      ;;
    stop) frontend_stop ;;
    restart) frontend_stop || true; run_frontend_foreground ;;
    status) frontend_status ;;
    *) die "Unknown frontend action: $action (expected start|stop|restart|status)" ;;
  esac
}

run_dev() {
  infra_up
  export_env
  local backend_pid=""
  local frontend_pid=""

  # Ensure we don't end up with multiple host dev servers.
  frontend_stop || true
  backend_stop || true

  run_backend_foreground &
  backend_pid=$!
  echo "$backend_pid" >"$BACKEND_PID_FILE"

  clear_frontend_lock_if_safe
  (cd "$PROJECT_DIR/frontend" && pnpm exec next dev --hostname "$FRONTEND_HOSTNAME" --port "$FRONTEND_PORT") &
  frontend_pid=$!

  local server_pid=""
  local i
  for i in {1..50}; do
    server_pid="$(find_pid_listening_on_port "$FRONTEND_PORT")"
    if [[ -n "$server_pid" ]] && pid_is_alive "$server_pid"; then
      break
    fi
    sleep 0.1
  done
  echo "${server_pid:-$frontend_pid}" >"$FRONTEND_PID_FILE"

  trap '
    kill "$backend_pid" "$frontend_pid" 2>/dev/null || true

    if [[ -f "$FRONTEND_PID_FILE" ]]; then
      pid="$(cat "$FRONTEND_PID_FILE" 2>/dev/null || true)"
      if [[ -n "$pid" ]] && pid_is_alive "$pid" && frontend_pid_matches_project "$pid"; then
        kill "$pid" 2>/dev/null || true
      fi
      rm -f "$FRONTEND_PID_FILE" || true
    fi

    if [[ -f "$BACKEND_PID_FILE" ]]; then
      pid="$(cat "$BACKEND_PID_FILE" 2>/dev/null || true)"
      if [[ -n "$pid" ]] && pid_is_alive "$pid" && backend_pid_matches_project "$pid"; then
        kill "$pid" 2>/dev/null || true
      fi
      rm -f "$BACKEND_PID_FILE" || true
    fi
  ' EXIT INT TERM
  wait_any_pid "$backend_pid" "$frontend_pid"
}

main() {
  local cmd="${1:-help}"
  case "$cmd" in
    up) infra_up ;;
    down) infra_down ;;
    clean) infra_clean ;;
    status) infra_status ;;
    logs) infra_logs ;;
    backend) backend_cmd "${2:-restart}" ;;
    frontend) frontend_cmd "${2:-restart}" ;;
    dev) run_dev ;;
    import) windmill_import ;;
    env) print_env ;;
    help|-h|--help) print_usage ;;
    *) err "Unknown command: $cmd"; print_usage; exit 1 ;;
  esac
}

main "$@"
