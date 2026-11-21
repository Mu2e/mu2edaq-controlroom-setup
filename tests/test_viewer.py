"""Viewer launch: macOS open vnc:// vs vncviewer elsewhere."""

from unittest import mock

import pytest

from mu2edaq_controlroom_setup import viewer as viewer_mod
from mu2edaq_controlroom_setup.session import Session


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    """Viewer logs go to ~/.crs; keep them out of the real home."""
    monkeypatch.setenv("HOME", str(tmp_path))


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
        ["/usr/bin/vncviewer", "-Shared", "localhost::5951"]


def test_explicit_viewer_overrides_macos(monkeypatch):
    monkeypatch.setattr(viewer_mod.sys, "platform", "darwin")
    with mock.patch("mu2edaq_controlroom_setup.viewer.subprocess.Popen") as popen:
        viewer_mod.attach(_session(), viewer="/opt/vncviewer")
    assert popen.call_args[0][0] == \
        ["/opt/vncviewer", "-Shared", "localhost::5951"]


def test_attach_detaches_viewer(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(viewer_mod.sys, "platform", "linux")
    with mock.patch("mu2edaq_controlroom_setup.viewer.find_viewer",
                    return_value="/usr/bin/vncviewer"), \
         mock.patch("mu2edaq_controlroom_setup.viewer.subprocess.Popen") as popen:
        viewer_mod.attach(_session())
    assert popen.call_args[1]["start_new_session"] is True
    assert (tmp_path / ".crs" / "viewer-dcs-main.log").exists()


def test_view_only_and_password_on_linux(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(viewer_mod.sys, "platform", "linux")
    with mock.patch("mu2edaq_controlroom_setup.viewer.find_viewer",
                    return_value="/usr/bin/vncviewer"), \
         mock.patch("mu2edaq_controlroom_setup.viewer.subprocess.Popen") as popen:
        viewer_mod.attach(_session(), view_only=True, password_file="/p/f")
    assert popen.call_args[0][0] == [
        "/usr/bin/vncviewer", "-Shared", "-ViewOnly", "PasswordFile=/p/f",
        "localhost::5951"]


def test_macos_view_only_uses_tigervnc(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(viewer_mod.sys, "platform", "darwin")
    with mock.patch("mu2edaq_controlroom_setup.viewer.find_viewer",
                    return_value=viewer_mod.MAC_VIEWER), \
         mock.patch("mu2edaq_controlroom_setup.viewer.subprocess.Popen") as popen:
        viewer_mod.attach(_session(), view_only=True)
    assert popen.call_args[0][0] == [
        viewer_mod.MAC_VIEWER, "-Shared", "-ViewOnly", "localhost::5951"]


def test_macos_view_only_without_tigervnc_fails_before_launch(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(viewer_mod.sys, "platform", "darwin")
    with mock.patch("mu2edaq_controlroom_setup.viewer.find_viewer",
                    return_value=None), \
         mock.patch("mu2edaq_controlroom_setup.viewer.subprocess.Popen") as popen:
        with pytest.raises(RuntimeError, match="TigerVNC"):
            viewer_mod.attach(_session(), view_only=True)
        with pytest.raises(RuntimeError, match="TigerVNC"):
            viewer_mod.attach(_session(), password_file="/p/f")
    popen.assert_not_called()


def test_macos_plain_still_uses_screen_sharing(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(viewer_mod.sys, "platform", "darwin")
    with mock.patch("mu2edaq_controlroom_setup.viewer.find_viewer",
                    return_value=viewer_mod.MAC_VIEWER), \
         mock.patch("mu2edaq_controlroom_setup.viewer.subprocess.Popen") as popen:
        viewer_mod.attach(_session())
    assert popen.call_args[0][0] == ["open", "vnc://localhost:5951"]


def test_resolve_password_file(tmp_path):
    (tmp_path / "mu2edcs.passwd").write_text("x")
    pattern = str(tmp_path / "{account}.passwd")
    assert viewer_mod.resolve_password_file(pattern, _session()) == \
        str(tmp_path / "mu2edcs.passwd")
    assert viewer_mod.resolve_password_file(
        str(tmp_path / "{session}.passwd"), _session()) is None
    assert viewer_mod.resolve_password_file(None, _session()) is None
