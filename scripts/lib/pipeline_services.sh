#!/usr/bin/env bash
# Service registry + health probe dispatcher for scripts/pipeline-ctl.sh.
# Requires bash 4+ (associative arrays).

if [[ -n "${_PIPELINE_SERVICES_LOADED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
_PIPELINE_SERVICES_LOADED=1

: "${PIPELINE_SCRIPT_DIR:?PIPELINE_SCRIPT_DIR must be set by caller}"
: "${PIPELINE_PROJECT_DIR:?PIPELINE_PROJECT_DIR must be set by caller}"
: "${PIPELINE_COMPOSE_FILE:?PIPELINE_COMPOSE_FILE must be set by caller}"

# Ordered list of services (used for display order).
PIPELINE_SERVICES=(
  nginx
  db
  redis
  windmill
  windmill_worker
  windmill_worker_native
  devgodzilla-api
  frontend
  lsp
  backend-host
  frontend-host
)

declare -A PIPELINE_SVC_KIND=()
declare -A PIPELINE_SVC_COMPOSE=()
declare -A PIPELINE_SVC_PROBE=()
declare -A PIPELINE_SVC_URL=()
declare -A PIPELINE_SVC_PORT=()
declare -A PIPELINE_SVC_HOST=()
declare -A PIPELINE_SVC_DISPLAY=()

# kind:     container | host
# compose:  docker-compose service name (empty for host processes)
# probe:    http | http_any | tcp | pg | redis | container | host_http | host_http_any
# url:      target URL (http*/host_http*); port: tcp/host port; host: tcp host

_svc() {
  # _svc <name> <kind> <compose> <probe> <port> <url> <host>
  local name="$1" kind="$2" compose="$3" probe="$4" port="$5" url="$6" host="${7:-}"
  PIPELINE_SVC_KIND[$name]="$kind"
  PIPELINE_SVC_COMPOSE[$name]="$compose"
  PIPELINE_SVC_PROBE[$name]="$probe"
  PIPELINE_SVC_URL[$name]="$url"
  PIPELINE_SVC_PORT[$name]="$port"
  PIPELINE_SVC_HOST[$name]="$host"
  PIPELINE_SVC_DISPLAY[$name]="$name"
}

_svc nginx                 container nginx                   http       8080 "http://localhost:8080/health"
_svc db                    container db                      pg         5432 ""
_svc redis                 container redis                   redis      6379 ""
_svc windmill              container windmill                http       8001 "http://localhost:8001/api/version"
_svc windmill_worker       container windmill_worker         container ""   ""
_svc windmill_worker_native container windmill_worker_native container ""   ""
_svc devgodzilla-api       container devgodzilla-api         http       8080 "http://localhost:8080/api/health"
_svc frontend              container frontend                http_any   8080 "http://localhost:8080/"
_svc lsp                   container lsp                     tcp        3001 ""           localhost
_svc backend-host          host      ""                      host_http  8000 "http://localhost:8000/health"
_svc frontend-host         host      ""                      host_http_any 3000 "http://localhost:3000/"

PIPELINE_SVC_DISPLAY[backend-host]="backend (host)"
PIPELINE_SVC_DISPLAY[frontend-host]="frontend (host)"

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

pipeline_compose() {
  docker compose -f "$PIPELINE_COMPOSE_FILE" "$@"
}

pipeline_is_known_service() {
  local needle="$1" name
  for name in "${PIPELINE_SERVICES[@]}"; do
    [[ "$name" == "$needle" ]] && return 0
  done
  return 1
}

pipeline_container_id() {
  local compose_name="$1"
  [[ -z "$compose_name" ]] && return 0
  pipeline_compose ps -q "$compose_name" 2>/dev/null | head -n 1
}

pipeline_container_state() {
  local compose_name="$1" id
  id="$(pipeline_container_id "$compose_name")"
  if [[ -z "$id" ]]; then
    echo "stopped"
    return 0
  fi
  docker inspect --format='{{.State.Status}}' "$id" 2>/dev/null || echo "unknown"
}

pipeline_container_health() {
  # Returns docker's own healthcheck verdict (healthy|unhealthy|starting|none).
  local compose_name="$1" id
  id="$(pipeline_container_id "$compose_name")"
  [[ -z "$id" ]] && { echo "none"; return 0; }
  docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$id" 2>/dev/null || echo "none"
}

pipeline_container_started_at() {
  local compose_name="$1" id
  id="$(pipeline_container_id "$compose_name")"
  [[ -z "$id" ]] && return 0
  docker inspect --format='{{.State.StartedAt}}' "$id" 2>/dev/null
}

pipeline_uptime_human() {
  # Converts an ISO-8601 StartedAt to a compact human uptime string.
  local started="$1"
  [[ -z "$started" || "$started" == "0001-01-01T00:00:00Z" ]] && { echo "-"; return 0; }
  local start_ts now secs
  start_ts="$(date -u -d "$started" +%s 2>/dev/null || echo 0)"
  now="$(date -u +%s)"
  secs=$((now - start_ts))
  (( secs < 0 )) && { echo "-"; return 0; }
  if (( secs < 60 )); then printf '%ds' "$secs"
  elif (( secs < 3600 )); then printf '%dm%ds' $((secs/60)) $((secs%60))
  elif (( secs < 86400 )); then printf '%dh%dm' $((secs/3600)) $(((secs%3600)/60))
  else printf '%dd%dh' $((secs/86400)) $(((secs%86400)/3600))
  fi
}

# -----------------------------------------------------------------------------
# Probes — each echoes a status token to stdout and returns 0 on healthy.
# Tokens: ok | down | unhealthy | starting | n/a
# -----------------------------------------------------------------------------

_probe_http_generic() {
  # $1 url, $2 any-status-ok (0/1)
  local url="$1" any_ok="${2:-0}" code
  code="$(curl -sS -o /dev/null -m 3 -w '%{http_code}' "$url" 2>/dev/null || echo 000)"
  if [[ "$code" == "000" ]]; then
    echo "down"; return 1
  fi
  if [[ "$any_ok" == "1" ]]; then
    (( code >= 200 && code < 500 )) && { echo "ok"; return 0; }
  else
    (( code >= 200 && code < 400 )) && { echo "ok"; return 0; }
  fi
  echo "unhealthy"; return 1
}

probe_http() { _probe_http_generic "$1" 0; }
probe_http_any() { _probe_http_generic "$1" 1; }

probe_tcp() {
  local host="$1" port="$2"
  if command -v nc >/dev/null 2>&1; then
    if nc -z -w 2 "$host" "$port" >/dev/null 2>&1; then
      echo "ok"; return 0
    fi
  else
    # /dev/tcp fallback (bash built-in).
    if timeout 2 bash -c ">/dev/tcp/$host/$port" >/dev/null 2>&1; then
      echo "ok"; return 0
    fi
  fi
  echo "down"; return 1
}

probe_pg() {
  if pipeline_compose exec -T db pg_isready -U postgres >/dev/null 2>&1; then
    echo "ok"; return 0
  fi
  # Fall back to container state so we distinguish down vs unhealthy.
  local state
  state="$(pipeline_container_state db)"
  if [[ "$state" != "running" ]]; then
    echo "down"; return 1
  fi
  echo "unhealthy"; return 1
}

probe_redis() {
  local out
  out="$(pipeline_compose exec -T redis redis-cli ping 2>/dev/null | tr -d '\r\n ')"
  if [[ "$out" == "PONG" ]]; then
    echo "ok"; return 0
  fi
  local state
  state="$(pipeline_container_state redis)"
  if [[ "$state" != "running" ]]; then
    echo "down"; return 1
  fi
  echo "unhealthy"; return 1
}

probe_container_only() {
  local compose_name="$1" state health
  state="$(pipeline_container_state "$compose_name")"
  case "$state" in
    running)
      health="$(pipeline_container_health "$compose_name")"
      case "$health" in
        healthy|none) echo "ok"; return 0 ;;
        starting)     echo "starting"; return 1 ;;
        unhealthy)    echo "unhealthy"; return 1 ;;
        *)            echo "ok"; return 0 ;;
      esac
      ;;
    restarting) echo "starting"; return 1 ;;
    stopped)    echo "down"; return 1 ;;
    *)          echo "$state"; return 1 ;;
  esac
}

probe_host_http() {
  # $1 port, $2 url, $3 any-status-ok
  local port="$1" url="$2" any_ok="${3:-0}"
  if ! pipeline_port_is_listening "$port"; then
    echo "-"; return 0
  fi
  _probe_http_generic "$url" "$any_ok"
}

pipeline_port_is_listening() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -lnt "sport = :$port" 2>/dev/null | awk 'NR>1{found=1} END{exit !found}' && return 0
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1 && return 0
  fi
  # /dev/tcp fallback
  timeout 1 bash -c ">/dev/tcp/127.0.0.1/$port" >/dev/null 2>&1 && return 0
  return 1
}

# -----------------------------------------------------------------------------
# High-level: compute the full row for a service.
# Echoes: state|health|port|url|uptime (pipe-separated, suitable for table).
# -----------------------------------------------------------------------------

pipeline_probe_service() {
  local name="$1"
  local kind="${PIPELINE_SVC_KIND[$name]:-}"
  local compose="${PIPELINE_SVC_COMPOSE[$name]:-}"
  local probe="${PIPELINE_SVC_PROBE[$name]:-}"
  local url="${PIPELINE_SVC_URL[$name]:-}"
  local port="${PIPELINE_SVC_PORT[$name]:-}"
  local host="${PIPELINE_SVC_HOST[$name]:-localhost}"

  local state="-" health="-" uptime="-"

  if [[ "$kind" == "container" ]]; then
    state="$(pipeline_container_state "$compose")"
    uptime="$(pipeline_uptime_human "$(pipeline_container_started_at "$compose")")"
    if [[ "$state" != "running" ]]; then
      health="down"
    else
      case "$probe" in
        http)       health="$(probe_http "$url" || true)" ;;
        http_any)   health="$(probe_http_any "$url" || true)" ;;
        tcp)        health="$(probe_tcp "$host" "$port" || true)" ;;
        pg)         health="$(probe_pg || true)" ;;
        redis)      health="$(probe_redis || true)" ;;
        container)  health="$(probe_container_only "$compose" || true)" ;;
        *)          health="n/a" ;;
      esac
    fi
  else
    # Host process.
    if pipeline_port_is_listening "$port"; then
      state="running"
    else
      state="-"
    fi
    case "$probe" in
      host_http)      health="$(probe_host_http "$port" "$url" 0 || true)" ;;
      host_http_any)  health="$(probe_host_http "$port" "$url" 1 || true)" ;;
      *)              health="n/a" ;;
    esac
  fi

  local port_display="${port:--}"
  local url_display="${url:--}"
  printf '%s|%s|%s|%s|%s\n' "$state" "$health" "$port_display" "$url_display" "$uptime"
}

pipeline_any_unhealthy() {
  # Exits 0 if every service is "ok" or "-" (for missing host processes).
  local name row health
  for name in "${PIPELINE_SERVICES[@]}"; do
    row="$(pipeline_probe_service "$name")"
    health="$(printf '%s' "$row" | awk -F'|' '{print $2}')"
    case "$health" in
      ok|-) ;;
      *) return 0 ;;
    esac
  done
  return 1
}
