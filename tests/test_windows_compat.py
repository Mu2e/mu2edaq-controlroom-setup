"""Windows compatibility tests.

Added in the windows-compat sweep. Locks in:
  * control_socket_path resolves the home dir on Windows (%USERPROFILE%) as well
    as POSIX ($HOME) and creates the ~/.crs run dir,
  * crs-provision-desktop tolerates a missing `gio` (GNOME/XFCE trust flag) so
    desktop provisioning does not crash on hosts without it, and
  * the client control-room scripts ship PowerShell ports (the server-side VNC
    scripts run on the Linux cluster and are not ported -- see #12).
"""
import os
import pathlib
import shutil
import subprocess

import pytest

from mu2edaq_controlroom_setup import sshutil

REPO = pathlib.Path(__file__).resolve().parent.parent
PWSH = shutil.which("pwsh") or shutil.which("powershell")

CLIENT_SCRIPTS = [
    ("bootstrap.sh", "bootstrap.ps1"),
    ("bin/start-controlroom.sh", "bin/start-controlroom.ps1"),
    ("bin/stop-controlroom.sh", "bin/stop-controlroom.ps1"),
]


def test_control_socket_path_creates_run_dir_cross_platform(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    path = sshutil.control_socket_path("mu2e-dl-01.fnal.gov", 5953)
    assert path.endswith("ssh-ctrl-mu2e-dl-01-5953")
    assert (tmp_path / ".crs").is_dir()


def test_provision_desktop_survives_missing_gio(tmp_path, monkeypatch):
    # Simulate a host without `gio`: provisioning must still write the launcher.
    # The script has no .py extension, so load it via an explicit loader.
    from importlib.machinery import SourceFileLoader
    from importlib.util import spec_from_loader, module_from_spec
    loader = SourceFileLoader(
        "crs_provision_desktop", str(REPO / "server" / "crs-provision-desktop"))
    mod = module_from_spec(spec_from_loader(loader.name, loader))
    loader.exec_module(mod)

    def no_gio(cmd, *a, **k):
        if cmd and cmd[0] == "gio":
            raise FileNotFoundError("gio")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(mod.subprocess, "run", no_gio)
    apps = [{"id": "dashboard", "sessions": ["daq-main"],
             "desktop": {"terminal": False},
             "name": "DAQ Message Dashboard"}]
    written = mod.provision(["daq-main"], apps, str(tmp_path / "Desktop"))
    assert any(p.endswith("dashboard-start.desktop") for p in written)
    assert (tmp_path / "Desktop" / "dashboard-start.desktop").is_file()


def test_client_scripts_have_powershell_ports():
    for sh, ps1 in CLIENT_SCRIPTS:
        assert (REPO / sh).is_file(), f"missing bash script: {sh}"
        assert (REPO / ps1).is_file(), f"missing PowerShell port: {ps1}"


def test_server_vnc_scripts_are_not_ported():
    # These run on the Linux DAQ cluster (vncserver/systemctl); no PowerShell.
    for rel in ("server/start-vnc-session.sh",
                "server/stop-vnc-session.sh",
                "server/install-controlroom.sh"):
        assert (REPO / rel).is_file()
        assert not (REPO / rel).with_suffix(".ps1").exists()


@pytest.mark.skipif(not PWSH, reason="PowerShell not available")
@pytest.mark.parametrize("_sh,ps1", CLIENT_SCRIPTS)
def test_powershell_scripts_parse(_sh, ps1):
    path = (REPO / ps1).as_posix()
    code = (
        "$e=$null;"
        f"[System.Management.Automation.Language.Parser]::ParseFile('{path}',[ref]$null,[ref]$e)|Out-Null;"
        "if($e){$e|ForEach-Object{Write-Error $_};exit 1}else{exit 0}"
    )
    result = subprocess.run(
        [PWSH, "-NoProfile", "-NonInteractive", "-Command", code],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
