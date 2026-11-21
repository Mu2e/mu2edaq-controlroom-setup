"""Site overlays (load_config overlays=, crs-tunnel --site-config) and the
guard that keeps overlay sessions out of crs-remote lifecycle commands."""

import os
import textwrap
from unittest import mock

import pytest

from mu2edaq_controlroom_setup import cli
from mu2edaq_controlroom_setup.config import (ConfigError, load_config,
                                              site_overlay_paths)
from mu2edaq_controlroom_setup.remote import RemoteRunner, UnmanagedSessionError

BASE = """
gateway: mu2egateway01.fnal.gov
personal_user: anorman
sessions:
  - {name: dcs-main, host: mu2e-mgr-01.fnal.gov, account: mu2edcs, display: 1, local_port: 5951}
  - {name: shift-main, host: mu2e-mgr-01.fnal.gov, account: mu2eshift, display: 2, local_port: 5952}
"""

SITE = """
personal_user: mu2eshift
gateway: mu2eshift@mu2egateway01.fnal.gov
view_only: true
sessions:
  - {name: cr01, host: mu2e-mgr-01.fnal.gov, account: mu2ecr01, display: 4, local_port: 5961}
  - {name: cr02, host: mu2e-mgr-01.fnal.gov, account: mu2ecr02, display: 5, local_port: 5962}
"""


def _write(tmp_path, name, body):
    path = tmp_path / name
    path.write_text(textwrap.dedent(body))
    return str(path)


@pytest.fixture
def base(tmp_path):
    return _write(tmp_path, "controlroom.yaml", BASE)


@pytest.fixture
def site(tmp_path):
    return _write(tmp_path, "site.yaml", SITE)


@pytest.fixture(autouse=True)
def _clean_env(tmp_path, monkeypatch):
    for var in ("CRS_SITE_CONFIG", "CRS_GATEWAY", "CRS_CONFIG", "CRS_INSTALL_DIR"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


# -- loading -----------------------------------------------------------------

def test_overlay_adds_unmanaged_sessions_and_overrides_login(base, site):
    cfg = load_config(base, overlays=[site])
    assert [s.name for s in cfg.sessions] == ["dcs-main", "shift-main", "cr01", "cr02"]
    assert [s.managed for s in cfg.sessions] == [True, True, False, False]
    assert cfg.personal_user == "mu2eshift"
    assert cfg.gateway == "mu2eshift@mu2egateway01.fnal.gov"
    assert cfg.view_only is True


def test_no_overlay_is_unchanged(base):
    cfg = load_config(base)
    assert cfg.personal_user == "anorman" and cfg.view_only is False
    assert all(s.managed for s in cfg.sessions)


def test_load_config_ignores_site_env(base, site, monkeypatch):
    """Only crs-tunnel passes overlays; crs-remote and crs-gui call
    load_config(path) and must not pick them up from the environment."""
    monkeypatch.setenv("CRS_SITE_CONFIG", site)
    cfg = load_config(base)
    assert [s.name for s in cfg.sessions] == ["dcs-main", "shift-main"]


def test_last_overlay_wins_for_scalars(base, tmp_path):
    a = _write(tmp_path, "a.yaml", "gateway: a.example\npersonal_user: ua\n")
    b = _write(tmp_path, "b.yaml", "gateway: b.example\n")
    cfg = load_config(base, overlays=[a, b])
    assert cfg.gateway == "b.example" and cfg.personal_user == "ua"


def test_env_gateway_beats_overlays(base, site, monkeypatch):
    monkeypatch.setenv("CRS_GATEWAY", "env.example")
    assert load_config(base, overlays=[site]).gateway == "env.example"


def test_view_only_is_or_merged(base, tmp_path):
    on = _write(tmp_path, "on.yaml", "view_only: true\n")
    off = _write(tmp_path, "off.yaml", "view_only: false\n")
    assert load_config(base, overlays=[on, off]).view_only is True
    assert load_config(base, overlays=[off]).view_only is False


def test_view_only_must_be_bool(base, tmp_path):
    bad = _write(tmp_path, "bad.yaml", "view_only: 'yes please'\n")
    with pytest.raises(ConfigError, match="view_only"):
        load_config(base, overlays=[bad])


@pytest.mark.parametrize("key", ["install_dir", "vnc_password_file",
                                 "accounts", "discovery"])
def test_overlay_rejects_other_keys(base, tmp_path, key):
    bad = _write(tmp_path, "bad.yaml", "%s: x\n" % key)
    with pytest.raises(ConfigError, match="not allowed in a site overlay"):
        load_config(base, overlays=[bad])


def test_overlay_cannot_set_managed(base, tmp_path):
    bad = _write(tmp_path, "bad.yaml", """
        sessions:
          - {name: x, host: h, account: u, display: 9, managed: true}
    """)
    with pytest.raises(ConfigError, match="managed"):
        load_config(base, overlays=[bad])


@pytest.mark.parametrize("entry, message", [
    ("{name: shift-main, host: h9, account: u, display: 9}", "duplicate session name"),
    ("{name: x, host: h9, account: u, display: 9, local_port: 5951}", "duplicate local_port"),
    ("{name: x, host: mu2e-mgr-01.fnal.gov, account: u, display: 2}", "duplicate display"),
])
def test_overlay_collisions_name_the_file(base, tmp_path, entry, message):
    bad = _write(tmp_path, "bad.yaml", "sessions:\n  - %s\n" % entry)
    with pytest.raises(ConfigError, match=message) as err:
        load_config(base, overlays=[bad])
    assert "bad.yaml" in str(err.value)


def test_missing_overlay_file(base, tmp_path):
    with pytest.raises(ConfigError, match="site config not found"):
        load_config(base, overlays=[str(tmp_path / "nope.yaml")])


def test_site_overlay_paths(monkeypatch):
    assert site_overlay_paths() == []
    monkeypatch.setenv("CRS_SITE_CONFIG", "/a.yaml::/b.yaml")
    assert site_overlay_paths() == ["/a.yaml", "/b.yaml"]
    assert site_overlay_paths(["/c.yaml"]) == ["/c.yaml"]


# -- crs-remote never touches overlay sessions -------------------------------

def _remote_targets(argv, monkeypatch):
    """Run crs-remote with ssh mocked; return the ssh destinations used."""
    with mock.patch("mu2edaq_controlroom_setup.sshutil.check_ticket"), \
         mock.patch("mu2edaq_controlroom_setup.remote.subprocess.run") as run:
        run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
        cli.remote_main(argv)
    return [call[0][0][call[0][0].index("BatchMode=yes") + 1]
            for call in run.call_args_list]


@pytest.mark.parametrize("command", ["start", "stop", "status", "provision", "install"])
@pytest.mark.parametrize("selector", [["--all"], ["--host", "mu2e-mgr-01"]])
def test_remote_ignores_site_overlay(base, site, monkeypatch, command, selector):
    monkeypatch.setenv("CRS_SITE_CONFIG", site)
    targets = _remote_targets([command, "--config", base] + selector, monkeypatch)
    assert targets and all("mu2ecr" not in t for t in targets)


def test_remote_refuses_named_overlay_session(base, site, monkeypatch):
    monkeypatch.setenv("CRS_SITE_CONFIG", site)
    with mock.patch("mu2edaq_controlroom_setup.remote.subprocess.run") as run:
        with pytest.raises(SystemExit) as exc:
            cli.remote_main(["start", "--config", base, "--session", "cr01"])
    assert exc.value.code not in (0, None)
    run.assert_not_called()


@pytest.mark.parametrize("method", ["start", "stop", "status", "provision", "install"])
def test_runner_refuses_unmanaged_session(base, site, method):
    config = load_config(base, overlays=[site])
    runner = RemoteRunner(config)
    with mock.patch("mu2edaq_controlroom_setup.remote.subprocess.run") as run, \
         mock.patch("mu2edaq_controlroom_setup.sshutil.check_ticket"):
        with pytest.raises(UnmanagedSessionError):
            getattr(runner, method)(config.session("cr01"))
    run.assert_not_called()


def test_lifecycle_sessions_filters_and_refuses(base, site):
    config = load_config(base, overlays=[site])
    assert [s.name for s in cli.lifecycle_sessions(config.sessions)] == \
        ["dcs-main", "shift-main"]
    with pytest.raises(SystemExit):
        cli.lifecycle_sessions([config.session("cr01")], explicit=True)


# -- crs-tunnel still reaches overlay sessions -------------------------------

def _tunnel(argv):
    with mock.patch("mu2edaq_controlroom_setup.sshutil.check_ticket"), \
         mock.patch("mu2edaq_controlroom_setup.tunnels.subprocess.run") as run, \
         mock.patch("mu2edaq_controlroom_setup.viewer.attach") as attach:
        run.return_value = mock.Mock(returncode=0)
        cli.tunnel_main(argv)
    return run, attach


def test_tunnel_status_lists_overlay_sessions(base, site, capsys):
    _tunnel(["status", "--config", base, "--site-config", site])
    out = capsys.readouterr().out
    assert "cr01" in out and "cr02" in out and "shift-main" in out


def test_tunnel_open_overlay_session(base, site):
    run, _ = _tunnel(["open", "--config", base, "--site-config", site,
                      "--session", "cr01"])
    argv = run.call_args[0][0]
    assert "5961:localhost:5904" in argv
    assert argv[-1] == "mu2eshift@mu2e-mgr-01.fnal.gov"
    assert argv[argv.index("-J") + 1] == "mu2eshift@mu2egateway01.fnal.gov"


@pytest.mark.parametrize("selector", [["--all"], ["--host", "mu2e-mgr-01"]])
def test_tunnel_open_all_includes_overlay(base, site, selector):
    run, _ = _tunnel(["open", "--config", base, "--site-config", site] + selector)
    forwards = [c[0][0][c[0][0].index("-L") + 1] for c in run.call_args_list]
    assert "5961:localhost:5904" in forwards and "5952:localhost:5902" in forwards


def test_tunnel_close_overlay_session(base, site, capsys):
    _tunnel(["close", "--config", base, "--site-config", site, "--session", "cr02"])
    assert "cr02" in capsys.readouterr().out


def test_connect_uses_site_view_only(base, site, monkeypatch):
    monkeypatch.setenv("CRS_SITE_CONFIG", site)
    _, attach = _tunnel(["connect", "--config", base, "--session", "shift-main"])
    assert attach.call_args[1]["view_only"] is True


def test_connect_without_site_is_not_view_only(base):
    _, attach = _tunnel(["connect", "--config", base, "--session", "shift-main"])
    assert attach.call_args[1]["view_only"] is False
