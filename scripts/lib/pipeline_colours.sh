#!/usr/bin/env bash
# Colour helpers for scripts/pipeline-ctl.sh.
# Respects NO_COLOR and non-TTY stdout (auto-disables ANSI).

# shellcheck disable=SC2034  # variables are consumed by sourcing scripts

if [[ -n "${_PIPELINE_COLOURS_LOADED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
_PIPELINE_COLOURS_LOADED=1

pc_supports_colour() {
  [[ -z "${NO_COLOR:-}" ]] || return 1
  [[ -t 1 ]] || return 1
  command -v tput >/dev/null 2>&1 || return 1
  local n
  n="$(tput colors 2>/dev/null || echo 0)"
  [[ "$n" =~ ^[0-9]+$ ]] && ((n >= 8))
}

if pc_supports_colour; then
  PC_RESET=$'\033[0m'
  PC_BOLD=$'\033[1m'
  PC_DIM=$'\033[2m'
  PC_RED=$'\033[31m'
  PC_GREEN=$'\033[32m'
  PC_YELLOW=$'\033[33m'
  PC_BLUE=$'\033[34m'
  PC_MAGENTA=$'\033[35m'
  PC_CYAN=$'\033[36m'
  PC_GREY=$'\033[90m'
  PC_BRIGHT_RED=$'\033[91m'
  PC_BRIGHT_GREEN=$'\033[92m'
  PC_BRIGHT_YELLOW=$'\033[93m'
  PC_BRIGHT_BLUE=$'\033[94m'
  PC_BRIGHT_MAGENTA=$'\033[95m'
  PC_BRIGHT_CYAN=$'\033[96m'
else
  PC_RESET=""
  PC_BOLD=""
  PC_DIM=""
  PC_RED=""
  PC_GREEN=""
  PC_YELLOW=""
  PC_BLUE=""
  PC_MAGENTA=""
  PC_CYAN=""
  PC_GREY=""
  PC_BRIGHT_RED=""
  PC_BRIGHT_GREEN=""
  PC_BRIGHT_YELLOW=""
  PC_BRIGHT_BLUE=""
  PC_BRIGHT_MAGENTA=""
  PC_BRIGHT_CYAN=""
fi

# Palette used for per-service log prefixes. Order matters; services are
# assigned colours round-robin by index so the mapping is stable per run.
PC_SERVICE_PALETTE=(
  "$PC_CYAN"
  "$PC_GREEN"
  "$PC_YELLOW"
  "$PC_MAGENTA"
  "$PC_BLUE"
  "$PC_BRIGHT_CYAN"
  "$PC_BRIGHT_GREEN"
  "$PC_BRIGHT_YELLOW"
  "$PC_BRIGHT_MAGENTA"
  "$PC_BRIGHT_BLUE"
)

pc_service_colour() {
  local idx="$1"
  local n="${#PC_SERVICE_PALETTE[@]}"
  (( n == 0 )) && { printf ''; return; }
  printf '%s' "${PC_SERVICE_PALETTE[$((idx % n))]}"
}

# Colour a status token (ok/down/unhealthy/starting/n/a) based on value.
pc_status_colour() {
  case "${1:-}" in
    ok|healthy|running|up) printf '%s' "$PC_GREEN" ;;
    starting|restarting|pending) printf '%s' "$PC_YELLOW" ;;
    down|stopped|exited|unhealthy|error|fail|failed) printf '%s' "$PC_RED" ;;
    n/a|"-"|unknown) printf '%s' "$PC_GREY" ;;
    *) printf '' ;;
  esac
}

pc_paint() {
  local colour="$1"
  shift
  printf '%s%s%s' "$colour" "$*" "$PC_RESET"
}
