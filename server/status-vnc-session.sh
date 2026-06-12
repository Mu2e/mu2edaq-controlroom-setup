#!/usr/bin/env bash
# Report VNC session status in a machine-parseable form.
# Runs ON a DAQ host as the session-owner account.
#
# Output, one line per queried display:
#   <name>|<display>|<port>|<state>|<responder>
# where state is running|stopped and responder is alive|dead|none.
#
# Usage: status-vnc-session.sh <session-name> <display-number> [...]
#        (pairs may repeat: status-vnc-session.sh daq-main 1 daq-aux 2)
set -euo pipefail

RUN_DIR="$HOME/.crs"

[[ $# -lt 2 || $(( $# % 2 )) -ne 0 ]] && {
  echo "Usage: $(basename "$0") <session-name> <display-number> [<name> <display> ...]"
  exit 1
}

LIST=$(vncserver -list 2>/dev/null || true)

while [[ $# -gt 0 ]]; do
  NAME="$1"; DISPLAY_NUM="$2"; shift 2
  PORT=$((5900 + DISPLAY_NUM))
  if echo "$LIST" | grep -qE "^:${DISPLAY_NUM}[[:space:]]"; then
    STATE="running"
  else
    STATE="stopped"
  fi
  RESPONDER="none"
  PID_FILE="$RUN_DIR/vnc-responder-:$DISPLAY_NUM.pid"
  if [[ -f "$PID_FILE" ]]; then
    if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      RESPONDER="alive"
    else
      RESPONDER="dead"
    fi
  fi
  echo "$NAME|:$DISPLAY_NUM|$PORT|$STATE|$RESPONDER"
done
