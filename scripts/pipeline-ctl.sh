#!/usr/bin/env bash
# pipeline-ctl: unified manager + monitor for the dev-pipeline stack.
#
# Commands:
#   status, health, watch, logs, start, stop, restart, down, fix, env, help
#
# See `pipeline-ctl.sh help` for detailed usage.

set -euo pipefail

PIPELINE_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_PROJECT_DIR="$(cd "$PIPELINE_SCRIPT_DIR/.." && pwd)"
PIPELINE_COMPOSE_FILE="${PIPELINE_COMPOSE_FILE:-$PIPELINE_PROJECT_DIR/docker-compose.yml}"

export PIPELINE_SCRIPT_DIR PIPELINE_PROJECT_DIR PIPELINE_COMPOSE_FILE

# shellcheck source=lib/pipeline_colours.sh
source "$PIPELINE_SCRIPT_DIR/lib/pipeline_colours.sh"
# shellcheck source=lib/pipeline_services.sh
source "$PIPELINE_SCRIPT_DIR/lib/pipeline_services.sh"
# shellcheck source=lib/pipeline_logs.sh
source "$PIPELINE_SCRIPT_DIR/lib/pipeline_logs.sh"

LOCAL_DEV_SCRIPT="$PIPELINE_SCRIPT_DIR/run-local-dev.sh"

info()  { printf '%s%s%s\n' "$PC_GREEN" "$*" "$PC_RESET"; }
warn()  { printf '%s%s%s\n' "$PC_YELLOW" "$*" "$PC_RESET" >&2; }
err()   { printf '%s%s%s\n' "$PC_RED" "$*" "$PC_RESET" >&2; }
die()   { err "$*"; exit 1; }

require_docker() {
  command -v docker >/dev/null 2>&1 || die "docker not found"
  docker info >/dev/null 2>&1 || die "docker is not running"
}

usage() {
  cat <<EOF
pipeline-ctl - manage and monitor the dev-pipeline stack

Usage: scripts/pipeline-ctl.sh <command> [args]

Commands:
  status                          One-shot table of service state + health
  health [--exit-code]            Probe every service. With --exit-code the
                                  process exits non-zero if any service is
                                  unhealthy/down (useful in CI).
  watch [--interval N]            Refreshing view of status/health (default 3s)
  logs [service ...] [flags]      Aggregated colour-prefixed log tail
       --save                     Also write to runs/pipeline-logs/pipeline-YYYYMMDD.log
       --grep PATTERN             Regex filter (applied to '[svc] line')
       --level LEVEL              Filter by log level (JSON or bare token)
       --since DURATION           Pass-through to docker compose (e.g. 10m)
  start                           docker compose up -d --build
  stop                            docker compose stop
  restart [service]               Restart whole stack or a single service
  down [--volumes]                docker compose down [-v]
  fix <action>                    Quick-fix runbooks:
                                    rebuild-api
                                    reseed-db
                                    clear-windmill-cache
                                    import-windmill
  env                             Print resolved env (via run-local-dev.sh)
  help                            This message

Services: ${PIPELINE_SERVICES[*]}
EOF
}

# -----------------------------------------------------------------------------
# status / health / watch
# -----------------------------------------------------------------------------

_print_row() {
  # name state health port url uptime
  local name="$1" state="$2" health="$3" port="$4" url="$5" uptime="$6"
  local kind="${PIPELINE_SVC_KIND[$name]:-}"
  local display="${PIPELINE_SVC_DISPLAY[$name]:-$name}"
  local state_col health_col
  state_col="$(pc_status_colour "$state")"
  health_col="$(pc_status_colour "$health")"
  printf '  %-22s %-10s %b%-10s%b %b%-10s%b %-6s %-35s %s\n' \
    "$display" "$kind" \
    "$state_col" "$state" "$PC_RESET" \
    "$health_col" "$health" "$PC_RESET" \
    "$port" "$url" "$uptime"
}

_print_header() {
  printf '  %b%-22s %-10s %-10s %-10s %-6s %-35s %s%b\n' "$PC_BOLD" \
    "SERVICE" "KIND" "STATE" "HEALTH" "PORT" "URL" "UPTIME" "$PC_RESET"
}

cmd_status() {
  require_docker
  _print_header
  local name row state health port url uptime
  for name in "${PIPELINE_SERVICES[@]}"; do
    row="$(pipeline_probe_service "$name")"
    IFS='|' read -r state health port url uptime <<<"$row"
    _print_row "$name" "$state" "$health" "$port" "$url" "$uptime"
  done
}

cmd_health() {
  local exit_code=0 require_exit=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --exit-code) require_exit=1 ;;
      -h|--help) usage; return 0 ;;
      *) die "unknown flag for health: $1" ;;
    esac
    shift
  done

  require_docker
  _print_header
  local name row state health port url uptime unhealthy=0
  for name in "${PIPELINE_SERVICES[@]}"; do
    row="$(pipeline_probe_service "$name")"
    IFS='|' read -r state health port url uptime <<<"$row"
    _print_row "$name" "$state" "$health" "$port" "$url" "$uptime"
    case "$health" in
      ok|-) ;;
      *) unhealthy=$((unhealthy + 1)) ;;
    esac
  done

  if (( unhealthy > 0 )); then
    printf '\n%b%d service(s) unhealthy%b\n' "$PC_RED" "$unhealthy" "$PC_RESET"
    (( require_exit )) && exit_code=1
  else
    printf '\n%ball services ok%b\n' "$PC_GREEN" "$PC_RESET"
  fi
  return "$exit_code"
}

cmd_watch() {
  local interval=3
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --interval) interval="$2"; shift 2 ;;
      --interval=*) interval="${1#*=}"; shift ;;
      -h|--help) usage; return 0 ;;
      *) die "unknown flag for watch: $1" ;;
    esac
  done
  [[ "$interval" =~ ^[0-9]+$ ]] || die "interval must be a positive integer"

  require_docker
  trap 'printf "\n"; exit 0' INT
  while true; do
    # Clear screen + home.
    printf '\033[2J\033[H'
    printf '%bpipeline-ctl watch%b  (every %ss)  %s\n\n' "$PC_BOLD" "$PC_RESET" "$interval" "$(date '+%Y-%m-%d %H:%M:%S')"
    cmd_status
    sleep "$interval"
  done
}

# -----------------------------------------------------------------------------
# logs
# -----------------------------------------------------------------------------

cmd_logs() {
  local save=0 pattern="" level="" since=""
  local services=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --save) save=1; shift ;;
      --grep) pattern="$2"; shift 2 ;;
      --grep=*) pattern="${1#*=}"; shift ;;
      --level) level="$2"; shift 2 ;;
      --level=*) level="${1#*=}"; shift ;;
      --since) since="$2"; shift 2 ;;
      --since=*) since="${1#*=}"; shift ;;
      -h|--help) usage; return 0 ;;
      --*) die "unknown flag for logs: $1" ;;
      *) services+=("$1"); shift ;;
    esac
  done

  require_docker
  pipeline_stream_logs "$save" "$pattern" "$level" "$since" -- "${services[@]}"
}

# -----------------------------------------------------------------------------
# start / stop / restart / down
# -----------------------------------------------------------------------------

cmd_start() {
  require_docker
  info "Starting full stack (docker compose up -d --build)"
  pipeline_compose up -d --build
  info "Stack started. App: http://localhost:8080/console  Windmill: http://localhost:8080"
}

cmd_stop() {
  require_docker
  info "Stopping stack"
  pipeline_compose stop
}

cmd_down() {
  require_docker
  local extra=()
  [[ "${1:-}" == "--volumes" || "${1:-}" == "-v" ]] && extra+=(-v)
  pipeline_compose down "${extra[@]}"
}

_wait_for_healthy() {
  local name="$1" timeout="${2:-60}"
  local deadline=$(( $(date +%s) + timeout ))
  local row health state
  while (( $(date +%s) < deadline )); do
    row="$(pipeline_probe_service "$name")"
    state="$(printf '%s' "$row" | awk -F'|' '{print $1}')"
    health="$(printf '%s' "$row" | awk -F'|' '{print $2}')"
    if [[ "$health" == "ok" ]]; then
      info "$name is healthy (state=$state)"
      return 0
    fi
    sleep 1
  done
  err "$name did not become healthy within ${timeout}s"
  return 1
}

cmd_restart() {
  require_docker
  local target="${1:-}"
  if [[ -z "$target" ]]; then
    info "Restarting full stack"
    pipeline_compose restart
    return 0
  fi
  pipeline_is_known_service "$target" || die "unknown service: $target"
  local kind="${PIPELINE_SVC_KIND[$target]:-}"
  if [[ "$kind" == "container" ]]; then
    local compose_name="${PIPELINE_SVC_COMPOSE[$target]}"
    info "Restarting $target (compose: $compose_name)"
    pipeline_compose restart "$compose_name"
    _wait_for_healthy "$target" 90
  elif [[ "$kind" == "host" ]]; then
    case "$target" in
      backend-host) "$LOCAL_DEV_SCRIPT" backend restart ;;
      frontend-host) "$LOCAL_DEV_SCRIPT" frontend restart ;;
      *) die "no host restart handler for $target" ;;
    esac
  else
    die "unknown kind '$kind' for $target"
  fi
}

# -----------------------------------------------------------------------------
# fix runbooks
# -----------------------------------------------------------------------------

cmd_fix() {
  require_docker
  local action="${1:-}"
  [[ -z "$action" ]] && die "fix requires an action: rebuild-api | reseed-db | clear-windmill-cache | import-windmill"

  case "$action" in
    rebuild-api)
      info "Rebuilding devgodzilla-api image"
      pipeline_compose build devgodzilla-api
      pipeline_compose up -d devgodzilla-api
      _wait_for_healthy devgodzilla-api 120
      ;;
    reseed-db)
      warn "This will DESTROY Postgres data (volume: pgdata). Continue? [y/N]"
      read -r reply
      [[ "$reply" =~ ^[Yy]$ ]] || { info "aborted"; return 0; }
      pipeline_compose stop db
      pipeline_compose rm -f db
      docker volume rm "$(basename "$PIPELINE_PROJECT_DIR")_pgdata" 2>/dev/null || \
        docker volume rm dev-pipeline_pgdata 2>/dev/null || true
      pipeline_compose up -d db
      _wait_for_healthy db 60
      ;;
    clear-windmill-cache)
      info "Clearing Windmill worker caches"
      pipeline_compose stop windmill_worker windmill_worker_native
      docker volume rm "$(basename "$PIPELINE_PROJECT_DIR")_windmill_cache" 2>/dev/null || \
        docker volume rm dev-pipeline_windmill_cache 2>/dev/null || true
      pipeline_compose up -d windmill_worker windmill_worker_native
      ;;
    import-windmill)
      "$LOCAL_DEV_SCRIPT" import
      ;;
    *)
      die "unknown fix action: $action"
      ;;
  esac
}

# -----------------------------------------------------------------------------
# env (delegate)
# -----------------------------------------------------------------------------

cmd_env() {
  "$LOCAL_DEV_SCRIPT" env
}

# -----------------------------------------------------------------------------
# main dispatch
# -----------------------------------------------------------------------------

main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    status)   cmd_status "$@" ;;
    health)   cmd_health "$@" ;;
    watch)    cmd_watch "$@" ;;
    logs)     cmd_logs "$@" ;;
    start|up) cmd_start "$@" ;;
    stop)     cmd_stop "$@" ;;
    restart)  cmd_restart "$@" ;;
    down)     cmd_down "$@" ;;
    fix)      cmd_fix "$@" ;;
    env)      cmd_env "$@" ;;
    help|-h|--help) usage ;;
    *) err "unknown command: $cmd"; usage; exit 1 ;;
  esac
}

main "$@"
