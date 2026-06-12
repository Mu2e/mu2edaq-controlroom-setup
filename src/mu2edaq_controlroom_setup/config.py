"""Load and validate the control room configuration.

Precedence: command line arguments > environment (CRS_*) > YAML config
file > built-in defaults. The CLI entry points apply their argparse
values on top of what load_config() returns.

Environment overrides:
    CRS_CONFIG       path to controlroom.yaml
    CRS_APPS_CONFIG  path to apps.yaml
    CRS_GATEWAY      ProxyJump host
    CRS_INSTALL_DIR  bin install area on the DAQ hosts
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


def load_config(path=None):
    """Load controlroom.yaml into a validated ControlRoomConfig."""
    path = path or os.environ.get("CRS_CONFIG") or _default_config_path("controlroom.yaml")
    try:
        with open(path) as fh:
            raw = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        raise ConfigError("config file not found: %s" % path)

    merged = dict(_DEFAULTS)
    merged.update({k: v for k, v in raw.items() if k != "sessions"})
    if os.environ.get("CRS_GATEWAY"):
        merged["gateway"] = os.environ["CRS_GATEWAY"]
    if os.environ.get("CRS_INSTALL_DIR"):
        merged["install_dir"] = os.environ["CRS_INSTALL_DIR"]

    sessions = []
    for i, entry in enumerate(raw.get("sessions", [])):
        try:
            sessions.append(Session(
                name=entry["name"],
                host=entry["host"],
                account=entry["account"],
                display=int(entry["display"]),
                geometry=str(entry.get("geometry", "1920x1080")),
                depth=int(entry.get("depth", 24)),
                local_port=int(entry.get("local_port", 0)),
            ))
        except KeyError as exc:
            raise ConfigError("session %d: missing required key %s" % (i, exc))

    _validate_sessions(sessions)
    cfg = ControlRoomConfig(sessions=sessions, **{
        k: merged[k] for k in
        ("gateway", "personal_user", "install_dir", "vnc_password_file",
         "discovery", "accounts")
    })
    return cfg


def _validate_sessions(sessions):
    names = set()
    local_ports = set()
    per_host_displays = set()
    for s in sessions:
        if s.name in names:
            raise ConfigError("duplicate session name: %s" % s.name)
        names.add(s.name)
        if not _GEOMETRY_RE.match(s.geometry):
            raise ConfigError("session %s: bad geometry %r (want WxH)" %
                              (s.name, s.geometry))
        if s.display < 1 or s.display > 99:
            raise ConfigError("session %s: display %d out of range 1-99" %
                              (s.name, s.display))
        key = (s.host, s.display)
        if key in per_host_displays:
            raise ConfigError("duplicate display :%d on host %s" % (s.display, s.host))
        per_host_displays.add(key)
        if s.local_port:
            if s.local_port in local_ports:
                raise ConfigError("duplicate local_port %d (session %s)" %
                                  (s.local_port, s.name))
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
