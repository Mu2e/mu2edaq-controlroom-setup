"""TunnelManager.open runs ssh without hanging on a ProxyJump child.

A fake `ssh` on PATH stands in for OpenSSH: like `ssh -f -J ...`, it leaves
a background process that keeps the inherited stderr open after the
foreground ssh exits. It also records its argv, SIGHUP disposition, session
and process group, so the tests can check how ssh was started.
"""

import json
import os
import signal
import stat
import sys
import threading

import pytest

from mu2edaq_controlroom_setup import sshutil, tunnels
from mu2edaq_controlroom_setup.session import ControlRoomConfig, Session
from mu2edaq_controlroom_setup.tunnels import TunnelManager

FAKE_SSH = """#!{python}
import json, os, signal, subprocess, sys
out = os.environ["FAKE_SSH_OUT"]
info = {{
    "argv": sys.argv[1:],
    "sighup_ignored": signal.getsignal(signal.SIGHUP) == signal.SIG_IGN,
    "sid": os.getsid(0),
    "pgrp": os.getpgrp(),
}}
# Like the ProxyJump child: outlives this process, holding stderr open.
child = subprocess.Popen(["sleep", "30"])
info["child"] = child.pid
with open(out, "w") as fh:
    json.dump(info, fh)
sys.stderr.write(os.environ.get("FAKE_SSH_STDERR", "") + "\\n")
sys.exit(int(os.environ.get("FAKE_SSH_EXIT", "0")))
"""


@pytest.fixture
def fake_ssh(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    ssh = bindir / "ssh"
    ssh.write_text(FAKE_SSH.format(python=sys.executable))
    ssh.chmod(ssh.stat().st_mode | stat.S_IXUSR)
    out = tmp_path / "fake-ssh.json"
    monkeypatch.setenv("PATH", "%s%s%s" % (bindir, os.pathsep, os.environ["PATH"]))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FAKE_SSH_OUT", str(out))
    monkeypatch.setattr(sshutil, "check_ticket", lambda: None)
    yield out
    if out.exists():
        try:
            os.kill(json.loads(out.read_text())["child"], signal.SIGKILL)
        except (OSError, KeyError, ValueError):
            pass


@pytest.fixture
def manager():
    config = ControlRoomConfig(
        gateway="mu2egateway01.fnal.gov", personal_user="mu2eshift",
        install_dir="~/controlroom", vnc_password_file="~/.vnc/passwd",
        discovery={}, accounts=[],
        sessions=[Session(name="shift-main", host="mu2e-mgr-01.fnal.gov",
                          account="mu2eshift", display=2, local_port=5952)])
    return TunnelManager(config)


def _open_with_timeout(manager, session, timeout=10):
    result = {}

    def run():
        try:
            result["state"] = manager.open(session)
        except Exception as exc:  # reported to the test below
            result["error"] = exc

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout)
    assert not thread.is_alive(), "TunnelManager.open did not return"
    return result


def test_open_returns_while_child_holds_stderr(fake_ssh, manager):
    result = _open_with_timeout(manager, manager.config.sessions[0])
    assert result == {"state": "open"}


def test_open_passes_unchanged_argv(fake_ssh, manager):
    session = manager.config.sessions[0]
    _open_with_timeout(manager, session)
    recorded = json.loads(fake_ssh.read_text())["argv"]
    expected = sshutil.tunnel_open_argv(
        "mu2eshift@mu2e-mgr-01.fnal.gov", 5952, 5902,
        manager._socket(session), gateway="mu2egateway01.fnal.gov")
    assert recorded == expected[1:]


def test_open_ignores_sighup_and_keeps_terminal(fake_ssh, manager):
    _open_with_timeout(manager, manager.config.sessions[0])
    info = json.loads(fake_ssh.read_text())
    assert info["sighup_ignored"] is True
    # Same session and process group as the caller: the controlling
    # terminal stays available for ssh's /dev/tty prompts.
    assert info["sid"] == os.getsid(0)
    assert info["pgrp"] == os.getpgrp()


def test_open_failure_reports_ssh_message(fake_ssh, manager, monkeypatch):
    monkeypatch.setenv("FAKE_SSH_EXIT", "255")
    monkeypatch.setenv("FAKE_SSH_STDERR", "Permission denied (gssapi-with-mic).")
    result = _open_with_timeout(manager, manager.config.sessions[0])
    assert isinstance(result.get("error"), RuntimeError)
    assert "Permission denied (gssapi-with-mic)." in str(result["error"])
    assert "shift-main" in str(result["error"])


def test_open_writes_log(fake_ssh, manager, monkeypatch):
    monkeypatch.setenv("FAKE_SSH_STDERR", "some ssh warning")
    _open_with_timeout(manager, manager.config.sessions[0])
    log = open(sshutil.tunnel_log_path()).read()
    assert "shift-main" in log and "some ssh warning" in log


def test_nohup_argv_wraps_command():
    argv = tunnels.nohup_argv(["ssh", "-N", "host"])
    assert argv[0] == sys.executable and argv[-3:] == ["ssh", "-N", "host"]
