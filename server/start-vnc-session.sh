#!/usr/bin/env bash
# Start a VNC session with its mock-discovery responder sidecar.
# Runs ON a DAQ host as the session-owner account.
#
# Usage: start-vnc-session.sh <session-name> <display> [-g WxH] [-d depth]
#        start-vnc-session.sh daq-main 1 -g 2560x1440
#
# Precedence: command line > environment (CRS_*) > defaults.
set -euo pipefail

CRS_HOME="${CRS_HOME:-$HOME/controlroom}"
RUN_DIR="$HOME/.crs"
GEOMETRY="${CRS_GEOMETRY:-1920x1080}"
DEPTH="${CRS_DEPTH:-24}"
ANNOUNCE_INTERVAL="${CRS_ANNOUNCE_INTERVAL:-30}"

usage() {
  echo "Usage: $(basename "$0") <session-name> <display-number> [-g WxH] [-d depth]"
  exit 1
}

[[ $# -lt 2 ]] && usage
NAME="$1"; DISPLAY_NUM="$2"; shift 2
while [[ $# -gt 0 ]]; do
  case "$1" in
    -g) shift; GEOMETRY="$1" ;;
    -d) shift; DEPTH="$1" ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
  shift
done

[[ "$DISPLAY_NUM" =~ ^[0-9]+$ ]] || { echo "Error: display must be a number"; exit 1; }
VNC_PORT=$((5900 + DISPLAY_NUM))
mkdir -p "$RUN_DIR" "$CRS_HOME/log"

XSTARTUP="$CRS_HOME/etc/xstartup"
[[ -x "$XSTARTUP" ]] || XSTARTUP="$HOME/.vnc/xstartup"

# Refuse to double-start.
if vncserver -list 2>/dev/null | grep -qE "^:${DISPLAY_NUM}[[:space:]]"; then
  echo "SKIP $NAME: display :$DISPLAY_NUM already running on $(hostname -s)"
  exit 0
fi

echo "START $NAME: vncserver :$DISPLAY_NUM ($GEOMETRY depth $DEPTH) on $(hostname -s)"
vncserver ":$DISPLAY_NUM" \
  -geometry "$GEOMETRY" \
  -depth "$DEPTH" \
  -localhost yes \
  -xstartup "$XSTARTUP" \
  >>"$CRS_HOME/log/vnc-$NAME.log" 2>&1

# Launch the discovery responder sidecar (mock auto-discovery for VNC).
RESPONDER="$CRS_HOME/bin/vnc-discovery-responder.py"
if [[ -f "$RESPONDER" ]]; then
  nohup python3 "$RESPONDER" \
    --name "$NAME" \
    --display ":$DISPLAY_NUM" \
    --port "$VNC_PORT" \
    --geometry "$GEOMETRY" \
    --announce-interval "$ANNOUNCE_INTERVAL" \
    >>"$CRS_HOME/log/vnc-responder-$NAME.log" 2>&1 &
  echo $! > "$RUN_DIR/vnc-responder-:$DISPLAY_NUM.pid"
  echo "START $NAME: discovery responder pid $! (port $VNC_PORT)"
else
  echo "WARN $NAME: responder not installed at $RESPONDER; no discovery announce"
fi

echo "OK $NAME: display :$DISPLAY_NUM port $VNC_PORT"
