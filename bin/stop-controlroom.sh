#!/usr/bin/env bash
# Tear down the control room: close all tunnels, stop all VNC sessions.
set -euo pipefail
cd "$(dirname "$0")/.."

[[ -x venv/bin/crs-remote ]] || {
  echo "Run ./bootstrap.sh first to create the venv." >&2
  exit 1
}

venv/bin/crs-tunnel close --all || true
venv/bin/crs-remote stop --all

echo ""
echo "Control room is down."
