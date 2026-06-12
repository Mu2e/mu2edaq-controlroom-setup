import os
import textwrap

import pytest

from mu2edaq_controlroom_setup.config import ConfigError, load_apps, load_config

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIPPED_CONFIG = os.path.join(REPO_ROOT, "config", "controlroom.yaml")
SHIPPED_APPS = os.path.join(REPO_ROOT, "config", "apps.yaml")


def _write(tmp_path, body):
    path = tmp_path / "controlroom.yaml"
    path.write_text(textwrap.dedent(body))
    return str(path)


def test_shipped_config_is_valid():
    cfg = load_config(SHIPPED_CONFIG)
    assert cfg.gateway == "mu2egateway01.fnal.gov"
    assert len(cfg.sessions) == 6
    assert {s.account for s in cfg.sessions} == {"mu2eshift", "mu2edaq", "mu2edcs"}


def test_shipped_session_layout():
    cfg = load_config(SHIPPED_CONFIG)
    by_host = {}
    for s in cfg.sessions:
        by_host.setdefault(s.host.split(".")[0], []).append(s)
    assert len(by_host["mu2e-mgr-01"]) == 2
    assert len(by_host["mu2e-dl-01"]) == 2
    assert len(by_host["mu2e-dl-02"]) == 1
    assert len(by_host["mu2e-dcs-01"]) == 1
    assert all(s.account == "mu2eshift" for s in by_host["mu2e-mgr-01"])
    assert all(s.account == "mu2edaq" for s in by_host["mu2e-dl-01"])
    assert by_host["mu2e-dcs-01"][0].account == "mu2edcs"


def test_vnc_port_derivation():
    cfg = load_config(SHIPPED_CONFIG)
    s = cfg.session("daq-main")
    assert s.display == 1
    assert s.vnc_port == 5901
    assert s.target == "mu2edaq@mu2e-dl-01.fnal.gov"


def test_local_ports_unique():
    cfg = load_config(SHIPPED_CONFIG)
    ports = [s.local_port for s in cfg.sessions]
    assert len(ports) == len(set(ports))


def test_session_lookup_unknown_raises():
    cfg = load_config(SHIPPED_CONFIG)
    with pytest.raises(KeyError):
        cfg.session("nope")


def test_sessions_on_host_short_name():
    cfg = load_config(SHIPPED_CONFIG)
    assert len(cfg.sessions_on("mu2e-mgr-01")) == 2
    assert len(cfg.sessions_on("mu2e-mgr-01.fnal.gov")) == 2


def test_duplicate_display_per_host_rejected(tmp_path):
    path = _write(tmp_path, """
        sessions:
          - {name: a, host: h1, account: u, display: 1}
          - {name: b, host: h1, account: u, display: 1}
    """)
    with pytest.raises(ConfigError, match="duplicate display"):
        load_config(path)


def test_duplicate_local_port_rejected(tmp_path):
    path = _write(tmp_path, """
        sessions:
          - {name: a, host: h1, account: u, display: 1, local_port: 5951}
          - {name: b, host: h2, account: u, display: 1, local_port: 5951}
    """)
    with pytest.raises(ConfigError, match="duplicate local_port"):
        load_config(path)


def test_bad_geometry_rejected(tmp_path):
    path = _write(tmp_path, """
        sessions:
          - {name: a, host: h1, account: u, display: 1, geometry: wide}
    """)
    with pytest.raises(ConfigError, match="bad geometry"):
        load_config(path)


def test_missing_required_key_rejected(tmp_path):
    path = _write(tmp_path, """
        sessions:
          - {name: a, host: h1, display: 1}
    """)
    with pytest.raises(ConfigError, match="missing required key"):
        load_config(path)


def test_env_gateway_override(tmp_path, monkeypatch):
    path = _write(tmp_path, "gateway: from-file.example.com\nsessions: []\n")
    monkeypatch.setenv("CRS_GATEWAY", "from-env.example.com")
    cfg = load_config(path)
    assert cfg.gateway == "from-env.example.com"


def test_shipped_apps_config_is_valid():
    apps = load_apps(SHIPPED_APPS)
    ids = {a["id"] for a in apps}
    assert "dashboard" in ids and "trigger-scalers" in ids
    # Every session referenced by an app exists in controlroom.yaml.
    cfg = load_config(SHIPPED_CONFIG)
    session_names = {s.name for s in cfg.sessions}
    for app in apps:
        for sname in app["sessions"]:
            assert sname in session_names, (
                "%s references unknown session %s" % (app["id"], sname))


def test_apps_no_port_collisions_per_session():
    """Two apps sharing a session must not claim the same port number."""
    apps = load_apps(SHIPPED_APPS)
    claimed = {}
    for app in apps:
        for sname in app["sessions"]:
            for port in app["ports"].values():
                key = (sname, port)
                assert key not in claimed, (
                    "port %s claimed by both %s and %s in session %s" %
                    (port, claimed.get(key), app["id"], sname))
                claimed[key] = app["id"]
