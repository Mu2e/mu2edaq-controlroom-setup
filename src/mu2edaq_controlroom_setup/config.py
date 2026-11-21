"""Load and validate the control room configuration.

Precedence: command line arguments > environment (CRS_*) > YAML config
file > built-in defaults. The CLI entry points apply their argparse
values on top of what load_config() returns.

Environment overrides:
    CRS_CONFIG       path to controlroom.yaml
    CRS_APPS_CONFIG  path to apps.yaml
    CRS_GATEWAY      ProxyJump host
    CRS_INSTALL_DIR  bin install area on the DAQ hosts

Site overlays (remote control rooms): load_config(path, overlays=[...])
applies small YAML files on top of controlroom.yaml. Only crs-tunnel
passes overlays (from --site-config, else CRS_SITE_CONFIG; see
site_overlay_paths); load_config never reads CRS_SITE_CONFIG itself, so
crs-remote and crs-gui never see overlay sessions. An overlay may set
personal_user and gateway (last file wins), view_only (true in any file
wins) and add sessions, which are loaded with managed=False.
"""

import os
import re

import yaml

from .session import ControlRoomConfig, Session

_DEFAULTS = {
    "gateway": "mu2egateway01.fnal.gov",
    "personal_user": os.environ.get("USER", ""),
    "install_dir": "~/controlroom",
    "vnc_password_file": "~/.vnc/passwd",
    "discovery": {"group": "239.255.42.99", "port": 28999,
                  "timeout": 2.0, "announce_interval": 30},
    "accounts": [],
}

_GEOMETRY_RE = re.compile(r"^\d{3,5}x\d{3,5}$")

_OVERLAY_KEYS = ("personal_user", "gateway", "view_only", "sessions")


class ConfigError(ValueError):
    pass


def _default_config_path(filename):
    """Search order: $CRS_CONFIG dir, CWD/config, package-relative config/."""
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates = [
        os.path.join(os.getcwd(), "config", filename),
        os.path.join(here, "config", filename),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[-1]


def site_overlay_paths(cli_paths=None):
    """Overlay files for crs-tunnel: --site-config values if any were given,
    else the ':'-separated CRS_SITE_CONFIG, else none."""
    if cli_paths:
        paths = list(cli_paths)
    else:
        paths = [p for p in os.environ.get("CRS_SITE_CONFIG", "").split(":") if p]
    return [os.path.expanduser(p) for p in paths]


def _read_yaml(path, missing_message):
    try:
        with open(path) as fh:
            raw = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        raise ConfigError(missing_message % path)
    if not isinstance(raw, dict):
        raise ConfigError("%s: expected a YAML mapping at the top level" % path)
    return raw


def _session(entry, i, managed=True, where=""):
    try:
        return Session(
            name=entry["name"],
            host=entry["host"],
            account=entry["account"],
            display=int(entry["display"]),
            geometry=str(entry.get("geometry", "1920x1080")),
            depth=int(entry.get("depth", 24)),
            local_port=int(entry.get("local_port", 0)),
            managed=managed,
        )
    except KeyError as exc:
        raise ConfigError("%ssession %d: missing required key %s" % (where, i, exc))


def load_config(path=None, overlays=()):
    """Load controlroom.yaml into a validated ControlRoomConfig.

    overlays: site overlay files applied on top, in order (see module doc).
    """
    path = path or os.environ.get("CRS_CONFIG") or _default_config_path("controlroom.yaml")
    raw = _read_yaml(path, "config file not found: %s")

    merged = dict(_DEFAULTS)
    merged.update({k: v for k, v in raw.items() if k != "sessions"})
    view_only = bool(raw.get("view_only", False))

    sessions = [_session(entry, i) for i, entry in enumerate(raw.get("sessions") or [])]
    origins = [None] * len(sessions)

    for opath in overlays:
        where = "site config %s: " % opath
        oraw = _read_yaml(opath, "site config not found: %s")
        extra = sorted(set(oraw) - set(_OVERLAY_KEYS))
        if extra:
            raise ConfigError("%skeys not allowed in a site overlay: %s (allowed: %s)"
                              % (where, ", ".join(extra), ", ".join(_OVERLAY_KEYS)))
        for key in ("personal_user", "gateway"):
            if key in oraw:
                merged[key] = oraw[key]
        if "view_only" in oraw:
            if not isinstance(oraw["view_only"], bool):
                raise ConfigError("%sview_only must be true or false" % where)
            view_only = view_only or oraw["view_only"]
        for i, entry in enumerate(oraw.get("sessions") or []):
            if "managed" in entry:
                raise ConfigError("%ssession %d: 'managed' cannot be set in a site "
                                  "overlay; overlay sessions are never managed" % (where, i))
            sessions.append(_session(entry, i, managed=False, where=where))
            origins.append(opath)

    if os.environ.get("CRS_GATEWAY"):
        merged["gateway"] = os.environ["CRS_GATEWAY"]
    if os.environ.get("CRS_INSTALL_DIR"):
        merged["install_dir"] = os.environ["CRS_INSTALL_DIR"]

    _validate_sessions(sessions, origins)
    cfg = ControlRoomConfig(sessions=sessions, view_only=view_only, **{
        k: merged[k] for k in
        ("gateway", "personal_user", "install_dir", "vnc_password_file",
         "discovery", "accounts")
    })
    return cfg


def _validate_sessions(sessions, origins=None):
    """Reject duplicate names, local ports and host displays. origins[i] is
    the overlay file session i came from (None for controlroom.yaml), named
    in the error so a site knows which file to fix."""
    origins = origins or [None] * len(sessions)
    names = set()
    local_ports = set()
    per_host_displays = set()
    for s, origin in zip(sessions, origins):
        where = " (in site config %s)" % origin if origin else ""
        if s.name in names:
            raise ConfigError("duplicate session name: %s%s" % (s.name, where))
        names.add(s.name)
        if not _GEOMETRY_RE.match(s.geometry):
            raise ConfigError("session %s: bad geometry %r (want WxH)%s" %
                              (s.name, s.geometry, where))
        if s.display < 1 or s.display > 99:
            raise ConfigError("session %s: display %d out of range 1-99%s" %
                              (s.name, s.display, where))
        key = (s.host, s.display)
        if key in per_host_displays:
            raise ConfigError("duplicate display :%d on host %s%s" %
                              (s.display, s.host, where))
        per_host_displays.add(key)
        if s.local_port:
            if s.local_port in local_ports:
                raise ConfigError("duplicate local_port %d (session %s)%s" %
                                  (s.local_port, s.name, where))
            local_ports.add(s.local_port)


def load_apps(path=None):
    """Load apps.yaml; returns the list of app dicts, validated."""
    path = path or os.environ.get("CRS_APPS_CONFIG") or _default_config_path("apps.yaml")
    try:
        with open(path) as fh:
            raw = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        raise ConfigError("apps config not found: %s" % path)

    apps = raw.get("apps", [])
    seen = set()
    for i, app in enumerate(apps):
        for key in ("id", "repo", "start", "stop"):
            if key not in app:
                raise ConfigError("app %d: missing required key %r" % (i, key))
        if app["id"] in seen:
            raise ConfigError("duplicate app id: %s" % app["id"])
        seen.add(app["id"])
        app.setdefault("title", app["id"])
        app.setdefault("ports", {})
        app.setdefault("sessions", [])
        app.setdefault("desktop", {})
    return apps
