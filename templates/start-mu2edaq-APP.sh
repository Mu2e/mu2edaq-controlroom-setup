#!/usr/bin/env bash
#
# start-mu2edaq-APP.sh - standardized Mu2e control-room start script.
#
# TEMPLATE. Copy this into an application repository, rename the file to
# match the app (start-mu2edaq-dashboard.sh, ...), then fill in the three
# blocks marked "EDIT". The control room launches it via:
#
#     crs-app start <app-id>
#
# (server/crs-app), which exports CRS_PORT_<NAME> for every port declared
# under this app's `ports:` in config/apps.yaml before exec'ing this
# script. The script can also be run by hand.
#
# Port resolution precedence (highest wins), matching the project-wide
# convention command line > environment > config file > default:
#
#   1. command line       --port NAME=VALUE      (repeatable)
#   2. environment        CRS_PORT_<NAME>        (crs-app sets these)
#   3. config file        sourced from --config FILE / $CRS_APP_CONFIG
#   4. built-in default    (PORT_SPEC below)
#
# Portable to bash 3.2 (the system bash on macOS): no associative arrays.
#
# Exit status: 0 = started or already running; non-zero = failure.

set -euo pipefail

# ===== EDIT 1: identity ================================================
APP_ID="APP"                       # MUST match the id: in apps.yaml
APP_DESC="Mu2e DAQ APP"            # human-readable; used in messages

# ===== EDIT 2: ports ===================================================
# One "NAME DEFAULT" per line. Each NAME must match a key under this
# app's `ports:` in apps.yaml; crs-app exports it as CRS_PORT_<NAME>
# (the name upper-cased). Leave the list empty if the app has no ports.
PORT_SPEC="
HTTP 8080
"

# ===== runtime locations (override via env if your site differs) =======
CRS_HOME="${CRS_HOME:-$HOME/controlroom}"
RUN_DIR="${CRS_RUN_DIR:-$CRS_HOME/run}"
LOG_DIR="${CRS_LOG_DIR:-$CRS_HOME/log}"
PID_FILE="$RUN_DIR/$APP_ID.pid"
LOG_FILE="$LOG_DIR/$APP_ID.log"

CONFIG_FILE="${CRS_APP_CONFIG:-}"
FOREGROUND=0

# Space-separated list of declared port names (for messages).
port_names() {
  local name _default
  while read -r name _default; do
    [ -n "$name" ] && printf '%s ' "$name"
  done <<EOF
$PORT_SPEC
EOF
  return 0   # the loop's final read returns nonzero at EOF; mask it (set -e)
}

usage() {
  local names; names="$(port_names)"
  cat <<EOF
Usage: $(basename "$0") [options]
Start $APP_DESC under the Mu2e control room.

Options:
  --port NAME=VALUE   override one port (repeatable); NAME one of: ${names:-(none)}
  --config FILE       source KEY=VALUE overrides (e.g. CRS_PORT_*) from FILE
  --foreground        run in the foreground instead of daemonizing
  -h, --help          show this help and exit

Port precedence: --port > CRS_PORT_<NAME> env > --config file > built-in default.
EOF
}

# ---- parse command line ----------------------------------------------
# CLI port overrides are stashed as PORT_CLI_<NAME> shell variables.
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)   _kv="$2"; shift 2;;
    --port=*) _kv="${1#*=}"; shift;;
    --config)     CONFIG_FILE="$2"; shift 2; continue;;
    --config=*)   CONFIG_FILE="${1#*=}"; shift; continue;;
    --foreground) FOREGROUND=1; shift; continue;;
    -h|--help)    usage; exit 0;;
    *) echo "error: unknown option: $1" >&2; usage >&2; exit 2;;
  esac
  _name="${_kv%%=*}"; _val="${_kv#*=}"
  case "$_name" in
    [A-Za-z_]*) ;;
    *) echo "error: invalid --port name: $_name" >&2; exit 2;;
  esac
  eval "PORT_CLI_$_name=\$_val"
done

# ---- config-file layer (sourced; may set CRS_PORT_* or other env) -----
if [[ -n "$CONFIG_FILE" ]]; then
  [[ -r "$CONFIG_FILE" ]] || { echo "error: config not readable: $CONFIG_FILE" >&2; exit 1; }
  set -a; # shellcheck disable=SC1090
  source "$CONFIG_FILE"; set +a
fi

# ---- resolve and export each port (precedence applied here) -----------
while read -r name default; do
  [ -n "$name" ] || continue
  env_var="CRS_PORT_${name}"
  cli_var="PORT_CLI_${name}"
  if [[ -n "${!cli_var:-}" ]]; then
    value="${!cli_var}"
  elif [[ -n "${!env_var:-}" ]]; then
    value="${!env_var}"
  else
    value="$default"
  fi
  [[ "$value" =~ ^[0-9]+$ ]] || { echo "error: $env_var is not numeric: $value" >&2; exit 1; }
  export "$env_var=$value"
done <<EOF
$PORT_SPEC
EOF

mkdir -p "$RUN_DIR" "$LOG_DIR"

# ---- already running? -------------------------------------------------
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "$APP_DESC already running (pid $(cat "$PID_FILE"))"
  exit 0
fi
rm -f "$PID_FILE"

ports_summary() {
  local name _default var out=""
  while read -r name _default; do
    [ -n "$name" ] || continue
    var="CRS_PORT_$name"; out+="$name=${!var} "
  done <<EOF
$PORT_SPEC
EOF
  echo "${out:-(none)}"
  return 0
}

# ===== EDIT 3: the launch command ======================================
# Build CMD as an array pointing at the app's real entry point. Reference
# ports through the exported CRS_PORT_<NAME> variables so they honor the
# precedence resolved above. Replace the placeholder below.
#
# Example (Python app):
#   CMD=( "$CRS_HOME/apps/$APP_ID/venv/bin/python" -m mu2edaq_app
#         --http-port "$CRS_PORT_HTTP" )
CMD=( false "TODO: set CMD to the $APP_ID entry point using \$CRS_PORT_*" )

echo "Starting $APP_DESC ($(ports_summary | sed 's/ *$//'))"

if [[ "$FOREGROUND" -eq 1 ]]; then
  exec "${CMD[@]}"
fi

nohup "${CMD[@]}" >>"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 1
if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "$APP_DESC started (pid $(cat "$PID_FILE")); logging to $LOG_FILE"
else
  echo "error: $APP_DESC failed to start; see $LOG_FILE" >&2
  rm -f "$PID_FILE"
  exit 1
fi
