#!/usr/bin/env bash
# Aggregated log streaming for scripts/pipeline-ctl.sh.
# Spawns `docker compose logs -f` per service and prefixes each line with a
# coloured [service] tag. Optionally tees everything to a dated file and
# filters by regex or log-level.

if [[ -n "${_PIPELINE_LOGS_LOADED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
_PIPELINE_LOGS_LOADED=1

: "${PIPELINE_PROJECT_DIR:?PIPELINE_PROJECT_DIR must be set by caller}"

PIPELINE_LOG_DIR="${PIPELINE_LOG_DIR:-$PIPELINE_PROJECT_DIR/runs/pipeline-logs}"

# Usage: pipeline_stream_logs <save:0|1> <grep_pattern> <level> <since> -- <service> [<service>...]
#
# All filters apply post-prefix (i.e. on the "[service] <line>" text), so
# --grep matches across service names and payloads.
pipeline_stream_logs() {
  local save="$1" pattern="$2" level="$3" since="$4"
  shift 4
  [[ "${1:-}" == "--" ]] && shift

  local services=("$@")
  if [[ "${#services[@]}" -eq 0 ]]; then
    # Default: every container-kind service.
    local name
    for name in "${PIPELINE_SERVICES[@]}"; do
      [[ "${PIPELINE_SVC_KIND[$name]:-}" == "container" ]] && services+=("$name")
    done
  fi

  # Validate + resolve to compose service names.
  local compose_svcs=() colour_idx=0 svc_colour
  declare -A svc_colour_map=()
  local s
  for s in "${services[@]}"; do
    if ! pipeline_is_known_service "$s"; then
      printf 'pipeline-ctl: unknown service: %s\n' "$s" >&2
      return 2
    fi
    if [[ "${PIPELINE_SVC_KIND[$s]:-}" != "container" ]]; then
      printf 'pipeline-ctl: logs only supported for container services, skipping: %s\n' "$s" >&2
      continue
    fi
    compose_svcs+=("${PIPELINE_SVC_COMPOSE[$s]}")
    svc_colour_map[$s]="$(pc_service_colour "$colour_idx")"
    colour_idx=$((colour_idx + 1))
  done

  if [[ "${#compose_svcs[@]}" -eq 0 ]]; then
    echo "pipeline-ctl: no container services to tail" >&2
    return 2
  fi

  local outfile=""
  if [[ "$save" == "1" ]]; then
    mkdir -p "$PIPELINE_LOG_DIR"
    outfile="$PIPELINE_LOG_DIR/pipeline-$(date +%Y%m%d).log"
    printf '# pipeline-ctl logs %s - services: %s\n' "$(date -Is)" "${services[*]}" >>"$outfile"
  fi

  # Per-service coloured prefix stream. We launch one child per service so the
  # prefix colour is stable; `docker compose logs` always emits "<svc>   | ..."
  # which would otherwise need parsing.
  _PIPELINE_LOG_PIDS=()
  _PIPELINE_LOG_CLEANUP_DONE=0
  trap _pipeline_logs_cleanup EXIT INT TERM

  # A temporary fifo-less approach: each child writes directly to stdout.
  # The coloured prefix + filter pipeline is built with awk for per-line flush.
  local i svc colour compose_name
  for i in "${!services[@]}"; do
    svc="${services[$i]}"
    [[ "${PIPELINE_SVC_KIND[$svc]:-}" != "container" ]] && continue
    compose_name="${PIPELINE_SVC_COMPOSE[$svc]}"
    colour="${svc_colour_map[$svc]}"
    _pipeline_stream_one "$svc" "$compose_name" "$colour" "$pattern" "$level" "$since" "$outfile" &
    _PIPELINE_LOG_PIDS+=("$!")
  done

  # Wait for any child; when one exits (e.g. docker compose is down) tear the
  # rest down so we don't leak processes.
  local status=0
  if [[ "${#_PIPELINE_LOG_PIDS[@]}" -gt 0 ]]; then
    wait -n "${_PIPELINE_LOG_PIDS[@]}" 2>/dev/null || status=$?
  fi
  _pipeline_logs_cleanup
  return "$status"
}

_pipeline_logs_cleanup() {
  (( ${_PIPELINE_LOG_CLEANUP_DONE:-0} )) && return 0
  _PIPELINE_LOG_CLEANUP_DONE=1
  local pid
  for pid in "${_PIPELINE_LOG_PIDS[@]:-}"; do
    [[ -n "$pid" ]] && kill "$pid" >/dev/null 2>&1 || true
  done
}

_pipeline_stream_one() {
  local svc="$1" compose_name="$2" colour="$3" pattern="$4" level="$5" since="$6" outfile="$7"
  local prefix
  if [[ -n "$colour" ]]; then
    prefix="${colour}[${svc}]${PC_RESET} "
  else
    prefix="[${svc}] "
  fi

  # When --since is set, show history matching that window; otherwise skip
  # history (tail=0) and follow only new output.
  local -a args=(logs -f --no-color)
  if [[ -n "$since" ]]; then
    args+=(--since "$since")
  else
    args+=(--tail=0)
  fi
  args+=("$compose_name")

  # Stream: docker compose -> awk (prefix + filters) -> (tee outfile) -> stdout
  # awk is used for line-buffered behaviour.
  local filter_awk
  filter_awk="$(_pipeline_build_filter_awk "$pattern" "$level")"

  if [[ -n "$outfile" ]]; then
    pipeline_compose "${args[@]}" 2>&1 \
      | awk -v pfx="$prefix" -v pat="$pattern" -v lvl="$level" "$filter_awk" \
      | tee -a "$outfile"
  else
    pipeline_compose "${args[@]}" 2>&1 \
      | awk -v pfx="$prefix" -v pat="$pattern" -v lvl="$level" "$filter_awk"
  fi
}

_pipeline_build_filter_awk() {
  local pattern="$1" level="$2"
  # We pass the regexes to awk via -v so we don't have to worry about awk
  # literal escaping for user-supplied strings.
  local have_pat=0 have_lvl=0
  [[ -n "$pattern" ]] && have_pat=1
  [[ -n "$level" ]] && have_lvl=1

  cat <<AWK
BEGIN { have_pat = ${have_pat}; have_lvl = ${have_lvl} }
{
  line = pfx \$0
  keep = 1
  if (have_pat && line !~ pat) keep = 0
  if (keep && have_lvl) {
    lvl_u = toupper(lvl)
    lvl_l = tolower(lvl)
    json_u = "\"level\"[ \\\\t]*:[ \\\\t]*\"" lvl_u "\""
    json_l = "\"level\"[ \\\\t]*:[ \\\\t]*\"" lvl_l "\""
    bare  = "(^|[^A-Za-z0-9_])" lvl_u "([^A-Za-z0-9_]|\$)"
    if (line !~ json_u && line !~ json_l && line !~ bare) keep = 0
  }
  if (keep) { print line; fflush() }
}
AWK
}
