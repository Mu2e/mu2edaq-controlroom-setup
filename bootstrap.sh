#!/usr/bin/env bash
# Bootstrap mu2edaq-controlroom-setup: create venv, install package
# with GUI support plus the sibling mu2edaq-discovery package.
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -d venv ]]; then
  python3 -m venv venv
fi
venv/bin/pip install --upgrade pip >/dev/null

# Prefer the sibling submodule checkout of mu2edaq-discovery when present.
if [[ -d ../mu2edaq-discovery ]]; then
  venv/bin/pip install -e ../mu2edaq-discovery
fi
venv/bin/pip install -e '.[gui,dev]'

echo "Done. Entry points in venv/bin: crs-tunnel crs-remote crs-gui"
echo "Run tests with: venv/bin/pytest"
