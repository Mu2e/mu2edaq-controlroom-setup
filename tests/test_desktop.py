"""Exercise the real server-side crs-provision-desktop and crs-app scripts."""

import configparser
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_DIR = os.path.join(REPO_ROOT, "server")
PROVISION = os.path.join(SERVER_DIR, "crs-provision-desktop")
CRS_APP = os.path.join(SERVER_DIR, "crs-app")


@pytest.fixture
def crs_home(tmp_path):
    """A fake ~/controlroom with the shipped configs installed."""
    home = tmp_path / "controlroom"
    (home / "etc").mkdir(parents=True)
    (home / "bin").mkdir()
    for fname in ("controlroom.yaml", "apps.yaml"):
        src = os.path.join(REPO_ROOT, "config", fname)
        (home / "etc" / fname).write_text(open(src).read())
    (home / "bin" / "crs-app").write_text(open(CRS_APP).read())
    os.chmod(home / "bin" / "crs-app", 0o755)
    return home


def _run_provision(crs_home, tmp_path, *args):
    env = dict(os.environ, CRS_HOME=str(crs_home))
    desktop = tmp_path / "Desktop"
    return subprocess.run(
        [sys.executable, PROVISION, "--desktop-dir", str(desktop), *args],
        env=env, capture_output=True, text=True,
    ), desktop


def test_provision_writes_start_stop_pairs(crs_home, tmp_path):
    result, desktop = _run_provision(crs_home, tmp_path, "--session", "daq-main")
    assert result.returncode == 0, result.stderr
    files = sorted(p.name for p in desktop.iterdir())
    # daq-main hosts dashboard, diskwatcher, fts, resource-manager (apps.yaml)
    assert "dashboard-start.desktop" in files
    assert "dashboard-stop.desktop" in files
    assert "resource-manager-start.desktop" in files
    # shift-only apps must not leak onto this desktop
    assert "controlcenter-start.desktop" not in files


def test_desktop_entry_format(crs_home, tmp_path):
    _, desktop = _run_provision(crs_home, tmp_path, "--session", "daq-main")
    parser = configparser.ConfigParser()
    parser.read(desktop / "dashboard-start.desktop")
    entry = parser["Desktop Entry"]
    assert entry["Type"] == "Application"
    assert entry["Name"] == "Start DAQ Message Dashboard"
    assert entry["Exec"].endswith("crs-app start dashboard")
    assert entry["Terminal"] == "false"


def test_stop_entry_uses_stop_icon(crs_home, tmp_path):
    _, desktop = _run_provision(crs_home, tmp_path, "--session", "daq-main")
    parser = configparser.ConfigParser()
    parser.read(desktop / "dashboard-stop.desktop")
    assert parser["Desktop Entry"]["Icon"] == "process-stop"
    assert parser["Desktop Entry"]["Exec"].endswith("crs-app stop dashboard")


def test_desktop_files_are_executable(crs_home, tmp_path):
    _, desktop = _run_provision(crs_home, tmp_path, "--session", "daq-main")
    path = desktop / "dashboard-start.desktop"
    assert os.access(path, os.X_OK)


def test_session_with_no_apps(crs_home, tmp_path):
    result, desktop = _run_provision(crs_home, tmp_path, "--session", "dcs-main")
    assert result.returncode == 0
    assert "no apps assigned" in result.stdout
    assert not desktop.exists() or not list(desktop.iterdir())


def test_crs_app_list(crs_home):
    env = dict(os.environ, CRS_HOME=str(crs_home))
    result = subprocess.run([sys.executable, CRS_APP, "list"],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "dashboard" in result.stdout
    assert "http=5001" in result.stdout


def test_crs_app_unknown_id(crs_home):
    env = dict(os.environ, CRS_HOME=str(crs_home))
    result = subprocess.run([sys.executable, CRS_APP, "start", "bogus"],
                            env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "unknown app" in result.stderr


@pytest.mark.skipif(os.name != "posix",
                    reason="crs-app execs a bash .sh start script (POSIX only)")
def test_crs_app_exports_ports_and_execs(crs_home, tmp_path):
    """crs-app must export CRS_PORT_* and exec the start script."""
    fake = crs_home / "bin" / "start-mu2edaq-dashboard.sh"
    fake.write_text("#!/bin/sh\necho \"HTTP=$CRS_PORT_HTTP ZMQ=$CRS_PORT_ZMQ\"\n")
    os.chmod(fake, 0o755)
    env = dict(os.environ, CRS_HOME=str(crs_home))
    result = subprocess.run([sys.executable, CRS_APP, "start", "dashboard"],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "HTTP=5001 ZMQ=5555" in result.stdout
