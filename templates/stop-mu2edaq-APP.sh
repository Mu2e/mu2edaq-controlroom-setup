#!/usr/bin/env bash
#
# stop-mu2edaq-APP.sh - standardized Mu2e control-room stop script.
#
# TEMPLATE. Copy into the app repository, rename to match the app, and
# set APP_ID/APP_DESC to the SAME values as the matching start script.
# The control room invokes it via:
#
#     crs-app stop <app-id>
#
# It reads the pid file written by start-mu2edaq-APP.sh, sends SIGTERM,
# and escalates to SIGKILL if the process does not exit within a timeout.
#
# Exit status: 0 = stopped or already not running; non-zero = failure.

set -euo pipefail

# ===== EDIT: identity (must match start-mu2edaq-APP.sh) ================
APP_ID="APP"
APP_DESC="Mu2e DAQ APP"

CRS_HOME="${CRS_HOME:-$HOME/controlroom}"
RUN_DIR="${CRS_RUN_DIR:-$CRS_HOME/run}"
PID_FILE="$RUN_DIR/$APP_ID.pid"
TIMEOUT="${CRS_STOP_TIMEOUT:-10}"   # seconds to wait for graceful exit

usage() {
  cat <<EOF
Usage: $(basename "$0") [--timeout SECONDS] [-h|--help]
Stop $APP_DESC (control room). Sends SIGTERM, then SIGKILL after the
timeout (default ${TIMEOUT}s; override with --timeout or CRS_STOP_TIMEOUT).
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --timeout)   TIMEOUT="$2"; shift 2;;
    --timeout=*) TIMEOUT="${1#*=}"; shift;;
    -h|--help)   usage; exit 0;;
    *) echo "error: unknown option: $1" >&2; usage >&2; exit 2;;
  esac
done
[[ "$TIMEOUT" =~ ^[0-9]+$ ]] || { echo "error: timeout not numeric: $TIMEOUT" >&2; exit 2; }

if [[ ! -f "$PID_FILE" ]]; then
  echo "$APP_DESC not running (no pid file)"
  exit 0
fi
pid="$(cat "$PID_FILE")"
if ! kill -0 "$pid" 2>/dev/null; then
  echo "$APP_DESC not running (stale pid $pid); cleaning up"
  rm -f "$PID_FILE"
  exit 0
fi

echo "Stopping $APP_DESC (pid $pid)..."
kill -TERM "$pid" 2>/dev/null || true
for ((i = 0; i < TIMEOUT; i++)); do
  kill -0 "$pid" 2>/dev/null || break
  sleep 1
done
if kill -0 "$pid" 2>/dev/null; then
  echo "did not exit within ${TIMEOUT}s; sending SIGKILL"
  kill -KILL "$pid" 2>/dev/null || true
  sleep 1
fi
rm -f "$PID_FILE"
echo "$APP_DESC stopped"
