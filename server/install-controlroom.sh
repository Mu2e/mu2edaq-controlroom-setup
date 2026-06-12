#!/usr/bin/env bash
# Install the control room bin area on a DAQ host.
# Runs ON the DAQ host as the session-owner account, from inside an
# unpacked payload directory (crs-remote install ships the payload via
# tar over ssh and runs this script).
#
# Creates ~/controlroom/{bin,etc,log}, installs the server scripts and
# configs, adds an idempotent PATH stanza to ~/.bash_profile, and
# symlinks each app's standardized start/stop scripts into the bin
# area when the app's checkout exists on this host.
set -euo pipefail

CRS_HOME="${CRS_HOME:-$HOME/controlroom}"
PAYLOAD_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing control room area to $CRS_HOME"
mkdir -p "$CRS_HOME/bin" "$CRS_HOME/etc" "$CRS_HOME/log" "$HOME/.crs"

# --- scripts -> bin -------------------------------------------------------
for f in start-vnc-session.sh stop-vnc-session.sh status-vnc-session.sh \
         vnc-discovery-responder.py crs-app crs-provision-desktop; do
  if [[ -f "$PAYLOAD_DIR/$f" ]]; then
    install -m 0755 "$PAYLOAD_DIR/$f" "$CRS_HOME/bin/$f"
    echo "  bin/$f"
  fi
done

# --- configs -> etc -------------------------------------------------------
for f in controlroom.yaml apps.yaml; do
  if [[ -f "$PAYLOAD_DIR/$f" ]]; then
    install -m 0644 "$PAYLOAD_DIR/$f" "$CRS_HOME/etc/$f"
    echo "  etc/$f"
  fi
done
if [[ -f "$PAYLOAD_DIR/xstartup" ]]; then
  install -m 0755 "$PAYLOAD_DIR/xstartup" "$CRS_HOME/etc/xstartup"
  echo "  etc/xstartup"
fi

# --- PATH stanza (idempotent, marker-guarded) -----------------------------
PROFILE="$HOME/.bash_profile"
MARK_BEGIN="# >>> mu2edaq-controlroom >>>"
MARK_END="# <<< mu2edaq-controlroom <<<"
if [[ -f "$PROFILE" ]] && grep -qF "$MARK_BEGIN" "$PROFILE"; then
  echo "  PATH stanza already present in $PROFILE"
else
  {
    echo ""
    echo "$MARK_BEGIN"
    echo 'export PATH="$HOME/controlroom/bin:$PATH"'
    echo "$MARK_END"
  } >> "$PROFILE"
  echo "  PATH stanza added to $PROFILE"
fi

# --- symlink app start/stop scripts into bin ------------------------------
# Reads "start:", "stop:", "install_path:" lines per app from apps.yaml.
python3 - "$CRS_HOME" <<'PYEOF'
import os, sys
crs_home = sys.argv[1]
apps_yaml = os.path.join(crs_home, "etc", "apps.yaml")
sys.path.insert(0, os.path.join(crs_home, "bin"))

def load(path):
    try:
        import yaml
        with open(path) as fh:
            return yaml.safe_load(fh) or {}
    except ImportError:
        import importlib.machinery, importlib.util
        loader = importlib.machinery.SourceFileLoader(
            "crs_app", os.path.join(crs_home, "bin", "crs-app"))
        spec = importlib.util.spec_from_loader("crs_app", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        return mod._tiny_yaml(path)

linked = missing = 0
for app in load(apps_yaml).get("apps", []):
    install = os.path.expanduser(app.get("install_path", ""))
    for which in ("start", "stop"):
        script = app.get(which)
        if not script or not install:
            continue
        src = os.path.join(install, script)
        dst = os.path.join(crs_home, "bin", script)
        if os.path.exists(src):
            if os.path.islink(dst) or os.path.exists(dst):
                os.remove(dst)
            os.symlink(src, dst)
            linked += 1
        else:
            missing += 1
print("  app scripts: %d linked, %d not present on this host" % (linked, missing))
PYEOF

echo "Done. Open a new shell or run: export PATH=\"\$HOME/controlroom/bin:\$PATH\""
