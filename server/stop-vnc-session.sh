#!/usr/bin/env bash
# Stop a VNC session and its discovery responder sidecar.
# Runs ON a DAQ host as the session-owner account.
#
# Usage: stop-vnc-session.sh <session-name> <display-number>
set -euo pipefail

RUN_DIR="$HOME/.crs"

usage() {
  echo "Usage: $(basename "$0") <session-name> <display-number>"
  exit 1
}

[[ $# -lt 2 ]] && usage
NAME="$1"; DISPLAY_NUM="$2"
[[ "$DISPLAY_NUM" =~ ^[0-9]+$ ]] || { echo "Error: display must be a number"; exit 1; }

# Stop the responder first so the session disappears from discovery
# before the port actually closes.
PID_FILE="$RUN_DIR/vnc-responder-:$DISPLAY_NUM.pid"
if [[ -f "$PID_FILE" ]]; then
  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null || true
    echo "STOP $NAME: discovery responder pid $PID"
  fi
  rm -f "$PID_FILE"
fi

if vncserver -list 2>/dev/null | grep -qE "^:${DISPLAY_NUM}[[:space:]]"; then
  vncserver -kill ":$DISPLAY_NUM"
  echo "STOP $NAME: display :$DISPLAY_NUM"
else
  echo "SKIP $NAME: display :$DISPLAY_NUM not running"
fi
