"""Viewer launch: macOS open vnc:// vs vncviewer elsewhere."""

from unittest import mock

from mu2edaq_controlroom_setup import viewer as viewer_mod
from mu2edaq_controlroom_setup.session import Session


def _session():
    return Session(name="dcs-main", host="mu2e-mgr-01.fnal.gov",
                   account="mu2edcs", display=1, local_port=5951)


def test_attach_uses_open_vnc_on_macos(monkeypatch):
    monkeypatch.setattr(viewer_mod.sys, "platform", "darwin")
    with mock.patch("mu2edaq_controlroom_setup.viewer.subprocess.Popen") as popen:
        viewer_mod.attach(_session())
    assert popen.call_args[0][0] == ["open", "vnc://localhost:5951"]


def test_attach_uses_vncviewer_off_macos(monkeypatch):
    monkeypatch.setattr(viewer_mod.sys, "platform", "linux")
    with mock.patch("mu2edaq_controlroom_setup.viewer.find_viewer",
                    return_value="/usr/bin/vncviewer"), \
         mock.patch("mu2edaq_controlroom_setup.viewer.subprocess.Popen") as popen:
        viewer_mod.attach(_session())
    assert popen.call_args[0][0] == \
        ["/usr/bin/vncviewer", "-Shared", "localhost:5951"]


def test_explicit_viewer_overrides_macos(monkeypatch):
    monkeypatch.setattr(viewer_mod.sys, "platform", "darwin")
    with mock.patch("mu2edaq_controlroom_setup.viewer.subprocess.Popen") as popen:
        viewer_mod.attach(_session(), viewer="/opt/vncviewer")
    assert popen.call_args[0][0] == \
        ["/opt/vncviewer", "-Shared", "localhost:5951"]
