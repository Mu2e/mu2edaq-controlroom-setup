"""Tunnel and ssh argv construction, with subprocess mocked out."""

import os
from unittest import mock

import pytest

from mu2edaq_controlroom_setup import sshutil
from mu2edaq_controlroom_setup.session import ControlRoomConfig, Session
from mu2edaq_controlroom_setup.tunnels import TunnelManager


@pytest.fixture
def config():
    return ControlRoomConfig(
        gateway="mu2egateway01.fnal.gov",
        personal_user="anorman",
        install_dir="~/controlroom",
        vnc_password_file="~/.vnc/passwd",
        discovery={"group": "239.255.42.99", "port": 28999},
        accounts=["mu2edaq"],
        sessions=[Session(name="daq-main", host="mu2e-dl-01.fnal.gov",
                          account="mu2edaq", display=1,
                          geometry="2560x1440", local_port=5953)],
    )


def test_tunnel_open_argv(config):
    s = config.sessions[0]
    argv = sshutil.tunnel_open_argv(
        s.target, s.local_port, s.vnc_port, "/tmp/sock",
        gateway=config.gateway)
    assert argv[0] == "ssh"
    assert "-J" in argv and argv[argv.index("-J") + 1] == "mu2egateway01.fnal.gov"
    assert "-L" in argv and argv[argv.index("-L") + 1] == "5953:localhost:5901"
    assert "-M" in argv and "-N" in argv and "-f" in argv
    assert argv[argv.index("-S") + 1] == "/tmp/sock"
    assert argv[-1] == "mu2edaq@mu2e-dl-01.fnal.gov"
    assert "GSSAPIAuthentication=yes" in argv


def test_remote_command_argv_includes_batchmode(config):
    argv = sshutil.remote_command_argv(
        "mu2edaq@mu2e-dl-01.fnal.gov", "hostname", gateway=config.gateway)
    assert "BatchMode=yes" in argv
    assert argv[-1] == "hostname"


def test_ssh_config_flag():
    argv = sshutil.base_ssh_args(gateway="gw", ssh_config="/tmp/cfg")
    assert argv[argv.index("-F") + 1] == "/tmp/cfg"


def test_control_socket_path_uses_short_host(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    path = sshutil.control_socket_path("mu2e-dl-01.fnal.gov", 5953)
    assert path.endswith("ssh-ctrl-mu2e-dl-01-5953")
    assert os.path.isdir(os.path.join(str(tmp_path), ".crs"))


def test_check_ticket_raises_without_ticket():
    with mock.patch("subprocess.run") as run:
        run.return_value = mock.Mock(returncode=1)
        with pytest.raises(sshutil.KerberosError):
            sshutil.check_ticket()


def test_open_skips_when_already_open(config):
    manager = TunnelManager(config)
    with mock.patch.object(manager, "status", return_value="open"):
        assert manager.open(config.sessions[0]) == "already-open"


def test_open_runs_ssh(config, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    manager = TunnelManager(config)
    s = config.sessions[0]
    with mock.patch.object(manager, "status", return_value="closed"), \
         mock.patch("mu2edaq_controlroom_setup.sshutil.check_ticket"), \
         mock.patch("mu2edaq_controlroom_setup.tunnels.subprocess.run") as run:
        run.return_value = mock.Mock(returncode=0, stderr="")
        assert manager.open(s) == "open"
        argv = run.call_args[0][0]
        assert "5953:localhost:5901" in argv


def test_open_failure_raises(config, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    manager = TunnelManager(config)
    with mock.patch.object(manager, "status", return_value="closed"), \
         mock.patch("mu2edaq_controlroom_setup.sshutil.check_ticket"), \
         mock.patch("mu2edaq_controlroom_setup.tunnels.subprocess.run") as run:
        run.return_value = mock.Mock(returncode=255, stderr="kex error")
        with pytest.raises(RuntimeError, match="kex error"):
            manager.open(config.sessions[0])


def test_status_closed_when_no_socket(config, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    manager = TunnelManager(config)
    assert manager.status(config.sessions[0]) == "closed"


def test_close_when_not_open(config, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    manager = TunnelManager(config)
    assert manager.close(config.sessions[0]) == "not-open"
