#!/usr/bin/env bash
# Bring up the full control room from this (external) machine:
# start all six VNC sessions on the cluster, then open all tunnels.
set -euo pipefail
cd "$(dirname "$0")/.."

[[ -x venv/bin/crs-remote ]] || {
  echo "Run ./bootstrap.sh first to create the venv." >&2
  exit 1
}

venv/bin/crs-remote start --all
venv/bin/crs-tunnel open --all

echo ""
echo "Control room is up. Attach with: venv/bin/crs-tunnel connect --session <name>"
echo "Or launch the GUI:               venv/bin/crs-gui"
