# Shared by remote-site/install.sh, crs-screen and crs-nodes. Sourced, not
# run. Works with bash 3.2 (macOS) and later.

REMOTE_SITE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CRS_DIR=$(cd "$REMOTE_SITE_DIR/.." && pwd)
CRS_VENV=$CRS_DIR/venv
CRS_BASE_CONFIG=${CRS_CONFIG:-$CRS_DIR/config/controlroom.yaml}
# Machine-local settings, sourced after the site file: <dir>/<site>.env
LOCAL_CONF_DIR=${XDG_CONFIG_HOME:-$HOME/.config}/mu2edaq-remote-site

# fail MESSAGE: print it and stop. In a terminal (a launcher window), wait
# for Enter first so the message can be read before the window closes.
fail() {
    echo >&2
    echo "*** $* ***" >&2
    if [ -t 0 ] && [ -z "${CRS_NO_PAUSE:-}" ]; then
        read -rp "Press Enter to close this window " _
    fi
    exit 1
}

# expand_home PATH: PATH with a leading ~ or ~/ replaced by $HOME
expand_home() {
    case $1 in
        "~") printf '%s\n' "$HOME" ;;
        "~/"*) printf '%s/%s\n' "$HOME" "${1#\~/}" ;;
        *) printf '%s\n' "$1" ;;
    esac
}

# load_site NAME: read sites/NAME.env, then the machine-local override.
# Sets SITE_NAME, SITE_YAML, SITE_ENV and the SITE_* settings.
load_site() {
    case $1 in
        ''|*[!A-Za-z0-9_-]*) fail "bad site name '$1' (letters, digits, - and _ only)" ;;
    esac
    SITE_NAME=$1
    SITE_YAML=$REMOTE_SITE_DIR/sites/$1.yaml
    SITE_ENV=$REMOTE_SITE_DIR/sites/$1.env
    [ -f "$SITE_YAML" ] || fail "no site overlay $SITE_YAML"
    [ -f "$SITE_ENV" ] || fail "no site settings $SITE_ENV"

    # Defaults; the site file and the local file may override any of them.
    SITE_TITLE=$1
    SITE_PRINCIPAL=
    SITE_KEYTAB=
    SITE_VIEWER=
    SITE_PASSWORD_FILE=
    SITE_LAUNCHERS=
    SITE_CLUSTER_TOOLS=$CRS_DIR/../mu2edaq-cluster-tools
    SITE_SSH_SELECTOR=
    SITE_DAQ_HOSTS=$HOME/.local/share/mu2edaq-cluster-tools/config/mu2e_daq.yaml

    # shellcheck source=/dev/null
    . "$SITE_ENV"
    if [ -f "$LOCAL_CONF_DIR/$1.env" ]; then
        # shellcheck source=/dev/null
        . "$LOCAL_CONF_DIR/$1.env"
    fi

    # A leading ~ in a path setting means $HOME, wherever it was written
    SITE_KEYTAB=$(expand_home "$SITE_KEYTAB")
    SITE_VIEWER=$(expand_home "$SITE_VIEWER")
    SITE_PASSWORD_FILE=$(expand_home "$SITE_PASSWORD_FILE")
    SITE_CLUSTER_TOOLS=$(expand_home "$SITE_CLUSTER_TOOLS")
    SITE_SSH_SELECTOR=$(expand_home "$SITE_SSH_SELECTOR")
    SITE_DAQ_HOSTS=$(expand_home "$SITE_DAQ_HOSTS")

    if [ -z "$SITE_SSH_SELECTOR" ]; then
        SITE_SSH_SELECTOR=$(command -v ssh-selector 2> /dev/null || true)
        for f in "$HOME/.local/bin/ssh-selector" "$HOME/bin/ssh-selector"; do
            [ -n "$SITE_SSH_SELECTOR" ] || { [ -x "$f" ] && SITE_SSH_SELECTOR=$f; }
        done
    fi
}

# ensure_ticket: get a Kerberos ticket if there is none, from the site
# keytab when one is configured, else by password.
ensure_ticket() {
    klist -s 2> /dev/null && return 0
    echo "No Kerberos ticket, getting one for ${SITE_PRINCIPAL:-the default principal}"
    if [ -n "$SITE_KEYTAB" ]; then
        [ -n "$SITE_PRINCIPAL" ] || fail "SITE_KEYTAB is set but SITE_PRINCIPAL is empty"
        [ -r "$SITE_KEYTAB" ] || fail "cannot read the keytab $SITE_KEYTAB"
        # -f forwardable, -A addressless, 26 h: as NOvA's GetTicket.sh.
        # The same flags work with MIT (Linux) and Heimdal (macOS) kinit.
        kinit -f -A -l 26h -k -t "$SITE_KEYTAB" "$SITE_PRINCIPAL" \
            || fail "kinit from $SITE_KEYTAB failed"
    elif [ -n "$SITE_PRINCIPAL" ]; then
        kinit -f -A "$SITE_PRINCIPAL" || fail "kinit failed"
    else
        kinit || fail "kinit failed"
    fi
}

# require_crs: set CRS_PY and CRS_TUNNEL from the controlroom-setup venv,
# or fail with the command that makes it.
require_crs() {
    [ -x "$CRS_VENV/bin/python" ] && [ -x "$CRS_VENV/bin/crs-tunnel" ] \
        || fail "controlroom-setup is not installed: run  $REMOTE_SITE_DIR/install.sh --site ${SITE_NAME:-NAME}"
    CRS_PY=$CRS_VENV/bin/python
    CRS_TUNNEL=$CRS_VENV/bin/crs-tunnel
}

# site_query WHAT [SESSION...]: ask the merged configuration (controlroom.yaml
# plus this site's overlay) through controlroom-setup's own loader.
#   sessions        one line per session: name account host managed
#   view_only       true or false
#   targets S...    gateway, then each distinct ssh login target for S...
#   check S...      exit 1 with a message if a name is not a session
#   passwords S...  the password file crs-tunnel would use for each session
#                   (SITE_PASSWORD_FILE expanded by viewer.password_file_path)
site_query() {
    SITE_PASSWORD_FILE=$SITE_PASSWORD_FILE \
    "$CRS_PY" - "$CRS_BASE_CONFIG" "$SITE_YAML" "$@" << 'EOF'
import os, sys
from mu2edaq_controlroom_setup.config import ConfigError, load_config
from mu2edaq_controlroom_setup.viewer import password_file_path
base, site, what, names = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
try:
    cfg = load_config(base, overlays=[site])
except ConfigError as exc:
    sys.exit("site configuration error: %s" % exc)
known = {s.name: s for s in cfg.sessions}
bad = [n for n in names if n not in known]
if bad:
    sys.exit("unknown session %s; known: %s" % (", ".join(bad), " ".join(known)))
if what == "sessions":
    for s in cfg.sessions:
        print(s.name, s.account, s.host, "managed" if s.managed else "site")
elif what == "view_only":
    print("true" if cfg.view_only else "false")
elif what == "passwords":
    for n in names or list(known):
        path = password_file_path(os.environ.get("SITE_PASSWORD_FILE", ""), known[n])
        if path:
            print(path)
elif what == "targets":
    print(cfg.gateway)
    seen = []
    for n in names or list(known):
        target = "%s@%s" % (cfg.personal_user or known[n].account, known[n].host)
        if target not in seen:
            seen.append(target)
            print(target)
EOF
}
