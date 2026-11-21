#!/usr/bin/env bash
# install.sh -- set up a remote Mu2e control room client (Linux or macOS).
#
# Usage:
#   remote-site/install.sh --site NAME [--launchers "A B ..."] [--no-launchers]
#                          [--replace]
#   remote-site/install.sh --site NAME --uninstall
#   remote-site/install.sh -h | --help
#
# Steps, in order:
#   1. check prerequisites (python3 >= 3.9 with venv, ssh, kinit, klist) and
#      stop with platform hints if any is missing
#   2. make controlroom-setup's venv with PyYAML only, or reuse the one
#      bootstrap.sh made
#   3. check the site overlay sites/NAME.yaml against config/controlroom.yaml
#   4. check for a VNC viewer (macOS: TigerVNC when the site is view-only)
#   5. node menu: install ssh-selector from ../mu2edaq-cluster-tools if needed
#   6. check credentials: keytab and VNC password files (never fetched here)
#   7. make the launchers: SITE_LAUNCHERS from sites/NAME.env, or --launchers.
#      Every launcher file is checked first; files this installer did not
#      make for this site are only overwritten with --replace (symbolic
#      links never), and nothing is written if any check fails.
#
# It never runs crs-remote: nothing is installed, started or stopped on the
# DAQ hosts. Machine-local settings go in
# ~/.config/mu2edaq-remote-site/NAME.env (sourced after sites/NAME.env).
# DRY_RUN=1 prints what would be done. See remote-site/README.md.

set -u
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
. "$REMOTE_SITE_DIR/lib/launchers.sh"
CRS_NO_PAUSE=1   # not run from a launcher window

usage() { sed -n '2,/^$/{/^#/s/^# \{0,1\}//p;}' "${BASH_SOURCE[0]}"; }

site=${CRS_REMOTE_SITE:-}
launchers=
no_launchers=
uninstall=
while [ $# -gt 0 ]; do
    case $1 in
        --site) [ $# -ge 2 ] || fail "--site needs a name"; site=$2; shift 2 ;;
        --site=*) site=${1#*=}; shift ;;
        --launchers) [ $# -ge 2 ] || fail "--launchers needs a list"; launchers=$2; shift 2 ;;
        --launchers=*) launchers=${1#*=}; shift ;;
        --no-launchers) no_launchers=1; shift ;;
        --uninstall) uninstall=1; shift ;;
        --replace) LAUNCHER_REPLACE=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) fail "unknown argument $1 (see --help)" ;;
    esac
done
[ -n "$site" ] || fail "no site given: install.sh --site NAME (sites: $(cd "$REMOTE_SITE_DIR/sites" && ls -- *.yaml | sed 's/\.yaml$//' | grep -v '^example$' | tr '\n' ' '))"
load_site "$site"
INSTALLED_LIST=$LOCAL_CONF_DIR/$SITE_NAME.installed
dry=${DRY_RUN:-}
run() { if [ -n "$dry" ]; then printf '+'; printf ' %q' "$@"; echo; else "$@"; fi; }

case $(uname -s) in
    Darwin) platform=macos ;;
    Linux) platform=linux ;;
    *) fail "only Linux and macOS are supported" ;;
esac

# -- uninstall -------------------------------------------------------------------
if [ -n "$uninstall" ]; then
    [ -f "$INSTALLED_LIST" ] || { echo "Nothing recorded for site $SITE_NAME."; exit 0; }
    if [ -n "$dry" ]; then
        echo "Would remove, where still marked for site $SITE_NAME:"
        sed 's/^/  /' "$INSTALLED_LIST"
        exit 0
    fi
    uninstall_recorded || fail "some launchers could not be removed (listed above); they stay recorded in $INSTALLED_LIST, so --uninstall can be run again"
    echo "Removed the $SITE_NAME launchers. The venv ($CRS_VENV), ssh-selector and credentials are left in place."
    exit 0
fi

echo "== Mu2e remote control room: $SITE_TITLE ($platform)"

# -- 1. prerequisites ----------------------------------------------------------
echo "1. Prerequisites"
missing=
python3 -c 'import sys, venv; sys.exit(sys.version_info < (3, 9))' 2> /dev/null \
    || missing="$missing python3>=3.9-with-venv"
for c in ssh kinit klist; do
    command -v "$c" > /dev/null 2>&1 || missing="$missing $c"
done
if [ -n "$missing" ]; then
    echo "  missing:$missing"
    if [ $platform = macos ]; then
        echo "  python3: xcode-select --install   (ssh, kinit, klist come with macOS)"
    else
        echo "  RHEL/Alma: sudo dnf install python3 openssh-clients krb5-workstation"
        echo "  Debian/Ubuntu: sudo apt install python3 python3-venv openssh-client krb5-user"
    fi
    fail "install the missing tools, then run this again"
fi
echo "  ok: python3 $(python3 -c 'import platform; print(platform.python_version())'), ssh, kinit, klist"

# -- 2. Python environment -------------------------------------------------------
echo "2. Python environment"
if [ -x "$CRS_VENV/bin/crs-tunnel" ]; then
    echo "  reusing $CRS_VENV"
else
    echo "  creating $CRS_VENV (PyYAML only; bootstrap.sh adds the GUI)"
    run python3 -m venv "$CRS_VENV" || fail "could not create $CRS_VENV"
    run "$CRS_VENV/bin/pip" install --quiet --upgrade pip || fail "pip upgrade failed"
    run "$CRS_VENV/bin/pip" install --quiet -e "$CRS_DIR" || fail "pip install of controlroom-setup failed"
fi
if [ -n "$dry" ] && [ ! -x "$CRS_VENV/bin/crs-tunnel" ]; then
    echo "  (dry run: no venv yet, so the remaining checks are skipped)"
    exit 0
fi
require_crs

# -- 3. site configuration -------------------------------------------------------
echo "3. Site configuration: $SITE_YAML"
sessions=$(site_query sessions) || fail "fix $SITE_YAML"
view_only=$(site_query view_only)
echo "$sessions" | while read -r name account host kind; do
    printf '  %-12s %-10s %-22s %s\n' "$name" "$account" "${host%%.*}" \
        "$([ "$kind" = site ] && echo "site screen" || echo "controlroom.yaml")"
done
echo "  view-only: $view_only"

[ -n "$no_launchers" ] && launchers=none
[ -n "$launchers" ] || launchers=$SITE_LAUNCHERS
[ "$launchers" = none ] && launchers=
screen_names=
want_nodes=
for l in $launchers; do
    if [ "$l" = nodes ]; then want_nodes=1; else screen_names="$screen_names $l"; fi
done
if [ -n "$screen_names" ]; then
    # shellcheck disable=SC2086
    site_query check $screen_names > /dev/null || fail "fix SITE_LAUNCHERS or --launchers"
fi

# -- 4. VNC viewer ---------------------------------------------------------------
echo "4. VNC viewer"
if [ -n "$SITE_VIEWER" ]; then
    [ -x "$SITE_VIEWER" ] || fail "SITE_VIEWER is not executable: $SITE_VIEWER"
    echo "  $SITE_VIEWER (SITE_VIEWER)"
elif command -v vncviewer > /dev/null 2>&1; then
    echo "  $(command -v vncviewer)"
elif [ $platform = macos ] && [ -x "/Applications/TigerVNC Viewer.app/Contents/MacOS/TigerVNC Viewer" ]; then
    echo "  /Applications/TigerVNC Viewer.app"
elif [ $platform = macos ] && [ "$view_only" = false ] && [ -z "$SITE_PASSWORD_FILE" ]; then
    echo "  macOS Screen Sharing (built in)"
elif [ $platform = macos ]; then
    echo "  none: this site is view-only or uses password files, which macOS"
    echo "  Screen Sharing cannot do. Install TigerVNC Viewer.app in /Applications"
    echo "  (https://tigervnc.org, macOS .dmg)."
    fail "no suitable VNC viewer"
else
    echo "  none. RHEL/Alma: sudo dnf install tigervnc   Debian/Ubuntu: sudo apt install tigervnc-viewer"
    echo "  or set SITE_VIEWER in $LOCAL_CONF_DIR/$SITE_NAME.env"
    fail "no VNC viewer"
fi

# -- 5. node menu ----------------------------------------------------------------
echo "5. Node menu (ssh-selector)"
if [ -z "$want_nodes" ]; then
    echo "  not requested"
elif [ -n "$SITE_SSH_SELECTOR" ] && [ -x "$SITE_SSH_SELECTOR" ]; then
    echo "  $SITE_SSH_SELECTOR"
elif [ -f "$SITE_CLUSTER_TOOLS/install.sh" ]; then
    echo "  installing from $SITE_CLUSTER_TOOLS"
    run bash "$SITE_CLUSTER_TOOLS/install.sh" || fail "mu2edaq-cluster-tools install.sh failed"
    load_site "$SITE_NAME"   # find the new ssh-selector
else
    echo "  skipped: no ssh-selector and no checkout at $SITE_CLUSTER_TOOLS"
    echo "  (clone mu2edaq-cluster-tools next to controlroom-setup and run this again)"
    want_nodes=
fi

# -- 6. credentials ----------------------------------------------------------------
echo "6. Credentials (never fetched or written by this script)"
mode_of() { if [ $platform = macos ]; then stat -f %Lp "$1"; else stat -c %a "$1"; fi; }
check_private() {  # FILE WHAT
    local m
    m=$(mode_of "$1")
    case $m in
        600|400) echo "  ok: $2 $1" ;;
        *) echo "  warning: $2 $1 has mode $m; run  chmod 600 '$1'" ;;
    esac
}
if [ -n "$SITE_KEYTAB" ]; then
    if [ -f "$SITE_KEYTAB" ]; then
        check_private "$SITE_KEYTAB" keytab
    else
        echo "  missing: keytab $SITE_KEYTAB for $SITE_PRINCIPAL"
        echo "  (get it from your site's DAQ contact; without it kinit will ask for a password)"
    fi
else
    echo "  no keytab configured: kinit will ask for ${SITE_PRINCIPAL:-your} password"
fi
if [ -n "$SITE_PASSWORD_FILE" ] && [ -n "$screen_names" ]; then
    # Expanded by crs-tunnel's own code, so these are the files it will use
    # shellcheck disable=SC2086
    site_query passwords $screen_names | sort -u | while IFS= read -r f; do
        if [ -f "$f" ]; then
            check_private "$f" "VNC password"
        else
            echo "  no VNC password file $f: the viewer will ask"
        fi
    done
fi

# -- 7. launchers ------------------------------------------------------------------
echo "7. Launchers"
names=$screen_names
[ -n "$want_nodes" ] && names="$names nodes"
if [ -z "${names// /}" ]; then
    echo "  none requested"
else
    # shellcheck disable=SC2086
    preflight_launchers $names
    if [ -n "$dry" ]; then
        for n in $names; do echo "  + launcher for $n"; done
    else
        mkdir -p "$LOCAL_CONF_DIR" || fail "cannot create $LOCAL_CONF_DIR"
        for n in $names; do install_launcher "$n"; done
        sort -u "$INSTALLED_LIST" -o "$INSTALLED_LIST"
        if [ $platform = linux ] && command -v update-desktop-database > /dev/null 2>&1; then
            update-desktop-database "${XDG_DATA_HOME:-$HOME/.local/share}/applications" > /dev/null 2>&1 || true
        fi
    fi
fi

echo
echo "Done. Next:"
echo "  $REMOTE_SITE_DIR/crs-screen --site $SITE_NAME --check"
echo "     first ssh contact with the gateway and hosts (answer host-key questions)"
if [ $platform = macos ]; then
    echo "  Open ~/Applications/Mu2e in Finder; drag launchers to the Dock."
else
    echo "  Find \"Mu2e ...\" in the application menu and pin it (GNOME: Add to Favorites)."
fi
