"""remote-site/: shipped site files, launcher generation, crs-screen dry runs.

Shell pieces run under the system bash (3.2 on macOS) in a temporary HOME.
Nothing here touches the network or a real Kerberos ticket.
"""

import os
import plistlib
import shutil
import subprocess
import sys

import pytest

from mu2edaq_controlroom_setup.config import load_config

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_DIR = os.path.join(REPO, "remote-site")
BASE = os.path.join(REPO, "config", "controlroom.yaml")
SCRIPTS = ["install.sh", "crs-screen", "crs-nodes", "lib/common.sh", "lib/launchers.sh"]


def bash(script, home, env=None, check=True, site_dir=SITE_DIR, platform=None):
    """Run a bash snippet with remote-site/lib loaded and HOME=home.
    platform="linux" makes the launcher code act as on Linux on any OS."""
    full_env = dict(os.environ, HOME=str(home), CRS_NO_PAUSE="1")
    full_env.pop("XDG_DATA_HOME", None)
    full_env.pop("XDG_CONFIG_HOME", None)
    full_env.update(env or {})
    # The directory goes in through the environment, so odd characters in
    # it (the escape test uses a '$') reach the scripts unexpanded.
    full_env["TEST_SITE_DIR"] = str(site_dir)
    prelude = '. "$TEST_SITE_DIR/lib/common.sh"; . "$TEST_SITE_DIR/lib/launchers.sh"; '
    if platform:
        prelude += "launcher_platform() { echo %s; }; " % platform
    return subprocess.run(["bash", "-c", prelude + script], env=full_env,
                          capture_output=True, text=True, check=check)


@pytest.mark.parametrize("script", SCRIPTS)
def test_scripts_parse(script):
    subprocess.run(["bash", "-n", os.path.join(SITE_DIR, script)], check=True)


@pytest.mark.parametrize("site", ["caltech", "example"])
def test_shipped_sites_load(site):
    cfg = load_config(BASE, overlays=[os.path.join(SITE_DIR, "sites", site + ".yaml")])
    assert cfg.view_only is True
    assert all(s.managed for s in cfg.sessions if s.name in ("shift-main", "dcs-main"))


def test_caltech_site_sessions():
    cfg = load_config(BASE, overlays=[os.path.join(SITE_DIR, "sites", "caltech.yaml")])
    crs = [s for s in cfg.sessions if s.name.startswith("cr")]
    assert [s.name for s in crs] == ["cr0%d" % i for i in range(1, 7)]
    assert [s.display for s in crs] == [4, 5, 6, 7, 8, 9]
    assert [s.local_port for s in crs] == list(range(5961, 5967))
    assert not any(s.managed for s in crs)
    assert cfg.personal_user == "mu2eshift"
    assert cfg.gateway == "mu2eshift@mu2egateway01.fnal.gov"


def test_caltech_launchers_name_real_sessions():
    env = open(os.path.join(SITE_DIR, "sites", "caltech.env")).read()
    line = [l for l in env.splitlines() if l.startswith("SITE_LAUNCHERS=")][0]
    names = line.split("=", 1)[1].strip('"').split()
    cfg = load_config(BASE, overlays=[os.path.join(SITE_DIR, "sites", "caltech.yaml")])
    known = {s.name for s in cfg.sessions} | {"nodes"}
    assert set(names) <= known
    assert "trig-main" not in names


def test_load_site_reads_local_override(tmp_path):
    local = tmp_path / ".config" / "mu2edaq-remote-site"
    local.mkdir(parents=True)
    (local / "caltech.env").write_text('SITE_VIEWER=/opt/viewer\n')
    out = bash('load_site caltech; echo "$SITE_VIEWER|$SITE_PRINCIPAL"', tmp_path).stdout
    assert out.strip() == "/opt/viewer|"


def test_load_site_rejects_bad_names(tmp_path):
    result = bash("load_site '../etc'", tmp_path, check=False)
    assert result.returncode != 0 and "bad site name" in result.stderr


def test_icon_labels(tmp_path):
    out = bash("for n in shift-main dcs-main cr01 cr06 trig-main; do icon_label $n; done",
               tmp_path).stdout.split()
    assert out == ["SHIFT", "DCS", "CR1", "CR6", "TRIG"]


def test_linux_launcher(tmp_path):
    bash("load_site caltech; INSTALLED_LIST=$HOME/installed; "
         "install_linux_launcher cr01; install_linux_launcher nodes", tmp_path)
    desktop = (tmp_path / ".local/share/applications/mu2e-cr01.desktop").read_text()
    assert 'Exec="%s/crs-screen" "--site" "caltech" "cr01"' % SITE_DIR in desktop
    assert "Terminal=true" in desktop
    assert "X-Mu2e-Remote-Site=caltech" in desktop
    assert "Icon=%s/.local/share/icons/mu2e/mu2e-cr01.svg" % tmp_path in desktop
    nodes = (tmp_path / ".local/share/applications/mu2e-nodes.desktop").read_text()
    assert '"%s/crs-nodes" "--site" "caltech"' % SITE_DIR in nodes
    svg = (tmp_path / ".local/share/icons/mu2e/mu2e-cr01.svg").read_text()
    assert ">CR1</text>" in svg and "dominant-baseline" not in svg
    installed = (tmp_path / "installed").read_text().split("\n")
    assert str(tmp_path / ".local/share/applications/mu2e-cr01.desktop") in installed


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS app bundles")
def test_mac_launcher(tmp_path):
    bash("load_site caltech; INSTALLED_LIST=$HOME/installed; install_mac_launcher cr01",
         tmp_path)
    bundle = tmp_path / "Applications" / "Mu2e" / "Mu2e cr01.app"
    info = plistlib.loads((bundle / "Contents/Info.plist").read_bytes())
    assert info["CFBundleExecutable"] == "launcher"
    assert info["CFBundleIconFile"] == "icon"
    assert info["CFBundleIdentifier"] == "org.mu2e.remote-site.caltech.cr01"
    assert os.access(bundle / "Contents/MacOS/launcher", os.X_OK)
    run = (bundle / "Contents/Resources/run.command").read_text()
    assert "crs-screen --site caltech cr01" in run
    assert os.access(bundle / "Contents/Resources/run.command", os.X_OK)
    assert "X-Mu2e-Remote-Site=caltech" in (bundle / "Contents/Resources/icon.svg").read_text()
    icns_path = bundle / "Contents/Resources/icon.icns"
    if not icns_path.exists() and os.environ.get("CRS_TEST_NO_ICONUTIL"):
        pytest.skip("CRS_TEST_NO_ICONUTIL set: iconutil refused in this environment")
    assert icns_path.exists(), (
        "icon.icns was not made; if iconutil is refused here (some sandboxes), "
        "set CRS_TEST_NO_ICONUTIL=1")
    icns = icns_path.read_bytes()
    assert icns[:4] == b"icns" and len(icns) > 10000


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS app bundles")
def test_mac_launcher_does_not_replace_foreign_app(tmp_path):
    foreign = tmp_path / "Applications" / "Mu2e" / "Mu2e cr01.app"
    foreign.mkdir(parents=True)
    result = bash("load_site caltech; install_mac_launcher cr01", tmp_path, check=False)
    assert result.returncode != 0 and "not made by this installer" in result.stderr
    assert foreign.exists()


def test_crs_screen_dry_run(tmp_path):
    result = subprocess.run(
        [os.path.join(SITE_DIR, "crs-screen"), "--site", "caltech", "shift-main", "cr01"],
        env=dict(os.environ, HOME=str(tmp_path), DRY_RUN="1", CRS_NO_PAUSE="1"),
        capture_output=True, text=True, check=True)
    lines = [l for l in result.stdout.splitlines() if "crs-tunnel" in l]
    assert len(lines) == 2
    assert "--site-config" in lines[0] and "--session shift-main" in lines[0]
    assert "--session cr01" in lines[1]


def test_crs_screen_needs_site(tmp_path):
    result = subprocess.run(
        [os.path.join(SITE_DIR, "crs-screen"), "shift-main"],
        env=dict(os.environ, HOME=str(tmp_path), CRS_NO_PAUSE="1"),
        capture_output=True, text=True)
    assert result.returncode != 0 and "no site given" in result.stderr


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck not installed")
def test_shellcheck():
    subprocess.run(["shellcheck", "-x"] + [os.path.join(SITE_DIR, s) for s in SCRIPTS],
                   check=True)


# -- launcher safety (review round 1: F1, F2) ---------------------------------

APPS = ".local/share/applications"
ICONS = ".local/share/icons/mu2e"


def test_linux_install_refuses_foreign_files(tmp_path):
    apps = tmp_path / APPS
    apps.mkdir(parents=True)
    foreign = apps / "mu2e-cr01.desktop"
    foreign.write_text("[Desktop Entry]\nName=someone else's\n")
    result = bash("load_site caltech; preflight_launchers shift-main cr01; "
                  "install_launcher shift-main; install_launcher cr01",
                  tmp_path, check=False, platform="linux")
    assert result.returncode != 0
    assert "not made by this installer" in result.stderr
    assert foreign.read_text() == "[Desktop Entry]\nName=someone else's\n"
    # nothing at all was written, not even for shift-main
    assert not (apps / "mu2e-shift-main.desktop").exists()
    assert not (tmp_path / ICONS).exists()


@pytest.mark.parametrize("where", ["icon", "desktop-copy"])
def test_linux_install_refuses_other_foreign_targets(tmp_path, where):
    if where == "icon":
        target = tmp_path / ICONS / "mu2e-cr01.svg"
    else:
        target = tmp_path / "Desktop" / "mu2e-cr01.desktop"
    target.parent.mkdir(parents=True)
    target.write_text("mine")
    result = bash("load_site caltech; preflight_launchers cr01", tmp_path,
                  check=False, platform="linux")
    assert result.returncode != 0 and str(target) in result.stderr
    assert target.read_text() == "mine"


def test_linux_replace_overwrites_foreign_files_but_never_links(tmp_path):
    apps = tmp_path / APPS
    apps.mkdir(parents=True)
    (apps / "mu2e-cr01.desktop").write_text("old caltech-roc launcher")
    result = bash("load_site caltech; preflight_launchers cr01; install_launcher cr01",
                  tmp_path, platform="linux", env={"LAUNCHER_REPLACE": "1"})
    assert "X-Mu2e-Remote-Site=caltech" in (apps / "mu2e-cr01.desktop").read_text()
    elsewhere = tmp_path / "elsewhere.desktop"
    elsewhere.write_text("keep")
    (apps / "mu2e-cr02.desktop").symlink_to(elsewhere)
    result = bash("load_site caltech; preflight_launchers cr02", tmp_path, check=False,
                  platform="linux", env={"LAUNCHER_REPLACE": "1"})
    assert result.returncode != 0 and "symbolic link" in result.stderr
    assert elsewhere.read_text() == "keep"


def test_linux_reinstall_replaces_own_files(tmp_path):
    for _ in range(2):
        bash("load_site caltech; preflight_launchers cr01; install_launcher cr01",
             tmp_path, platform="linux")
    assert (tmp_path / APPS / "mu2e-cr01.desktop").exists()


def test_uninstall_keeps_foreign_files(tmp_path):
    bash("load_site caltech; INSTALLED_LIST=$HOME/installed; "
         "preflight_launchers cr01; install_launcher cr01", tmp_path, platform="linux")
    foreign = tmp_path / APPS / "mu2e-other.desktop"
    foreign.write_text("[Desktop Entry]\n")
    other_site = tmp_path / ICONS / "mu2e-x.svg"
    other_site.write_text("<svg>\n<!-- X-Mu2e-Remote-Site=elsewhere -->\n</svg>\n")
    with open(tmp_path / "installed", "a") as fh:
        fh.write("%s\n%s\n" % (foreign, other_site))
    bash("load_site caltech; INSTALLED_LIST=$HOME/installed; uninstall_recorded",
         tmp_path, platform="linux")
    assert not (tmp_path / APPS / "mu2e-cr01.desktop").exists()
    assert not (tmp_path / ICONS / "mu2e-cr01.svg").exists()
    assert foreign.exists() and other_site.exists()


def test_linux_path_needing_escape_is_refused_before_writing(tmp_path):
    odd = tmp_path / "co$t" / "mu2edaq-controlroom-setup"
    shutil.copytree(SITE_DIR, str(odd / "remote-site"))
    home = tmp_path / "home"
    home.mkdir()
    result = bash("load_site caltech; preflight_launchers cr01", home, check=False,
                  site_dir=str(odd / "remote-site"), platform="linux")
    assert result.returncode != 0 and "Exec line" in result.stderr
    assert not (home / ".local").exists()


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_linux_write_failure_stops(tmp_path):
    apps = tmp_path / APPS
    apps.mkdir(parents=True)
    apps.chmod(0o555)
    try:
        result = bash("load_site caltech; install_launcher cr01; echo REACHED",
                      tmp_path, check=False, platform="linux")
    finally:
        apps.chmod(0o755)
    assert result.returncode != 0 and "REACHED" not in result.stdout
    assert "cannot write" in result.stderr


# -- password files and ~ (review round 1: F3) -----------------------------------

def test_site_paths_expand_tilde(tmp_path):
    local = tmp_path / ".config" / "mu2edaq-remote-site"
    local.mkdir(parents=True)
    (local / "caltech.env").write_text(
        'SITE_KEYTAB="~/.krb/k.keytab"\nSITE_PASSWORD_FILE="~/.vnc/{account}.passwd"\n')
    out = bash('load_site caltech; echo "$SITE_KEYTAB|$SITE_PASSWORD_FILE"', tmp_path).stdout
    assert out.strip() == "%s/.krb/k.keytab|%s/.vnc/{account}.passwd" % (tmp_path, tmp_path)


def test_password_check_uses_crs_tunnel_expansion(tmp_path):
    local = tmp_path / ".config" / "mu2edaq-remote-site"
    local.mkdir(parents=True)
    (local / "caltech.env").write_text('SITE_PASSWORD_FILE="~/.vnc/{account}-{session}.passwd"\n')
    out = bash("load_site caltech; CRS_PY=%s; site_query passwords cr01 shift-main"
               % sys.executable, tmp_path,
               env={"PYTHONPATH": os.path.join(REPO, "src")}).stdout.split()
    assert out == ["%s/.vnc/mu2ecr01-cr01.passwd" % tmp_path,
                   "%s/.vnc/mu2eshift-shift-main.passwd" % tmp_path]


@pytest.mark.skipif(sys.platform != "darwin", reason="AppKit renderer")
def test_svg2png_renders_icon(tmp_path):
    """The AppKit renderer alone (no iconutil): a 1024 px PNG, transparent
    corner, opaque middle."""
    import struct
    import zlib
    bash("SITE_NAME=caltech; icon_svg cr01 > $HOME/i.svg", tmp_path)
    subprocess.run(["osascript", "-l", "JavaScript", os.path.join(SITE_DIR, "lib", "svg2png.js"),
                    str(tmp_path / "i.svg"), str(tmp_path / "i.png"), "1024"], check=True)
    data = (tmp_path / "i.png").read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height, depth, ctype = struct.unpack(">IIBB", data[16:26])
    assert (width, height, depth, ctype) == (1024, 1024, 8, 6)
    pos, idat = 8, b""
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        if data[pos + 4:pos + 8] == b"IDAT":
            idat += data[pos + 8:pos + 8 + n]
        pos += 12 + n
    raw = zlib.decompress(idat)
    stride = 1 + width * 4
    first, prev = None, bytearray(width * 4)
    for y in range(height // 2 + 1):                  # unfilter down to the middle row
        f, line = raw[y * stride], bytearray(raw[y * stride + 1:(y + 1) * stride])
        for x in range(len(line)):
            a = line[x - 4] if x >= 4 else 0
            b, c = prev[x], (prev[x - 4] if x >= 4 else 0)
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
        if first is None:
            first = line
    assert first[3] == 0                                  # top-left corner transparent
    assert prev[(width // 2) * 4 + 3] == 255              # middle pixel opaque


def test_uninstall_failure_keeps_record_and_fails(tmp_path):
    """install.sh --uninstall: a file that cannot be removed stays recorded,
    the command fails, and a later run finishes the job."""
    record = tmp_path / ".config" / "mu2edaq-remote-site" / "caltech.installed"
    record.parent.mkdir(parents=True)
    bash("load_site caltech; INSTALLED_LIST=%s; preflight_launchers cr01; "
         "install_launcher cr01" % record, tmp_path, platform="linux")
    apps = tmp_path / APPS
    env = dict(os.environ, HOME=str(tmp_path), CRS_NO_PAUSE="1")
    env.pop("XDG_DATA_HOME", None)
    env.pop("XDG_CONFIG_HOME", None)
    uninstall = [os.path.join(SITE_DIR, "install.sh"), "--site", "caltech", "--uninstall"]
    apps.chmod(0o555)
    try:
        if os.geteuid() == 0:
            pytest.skip("root ignores directory permissions")
        first = subprocess.run(uninstall, env=env, capture_output=True, text=True)
    finally:
        apps.chmod(0o755)
    assert first.returncode != 0
    assert "Removed the caltech launchers" not in first.stdout
    assert "could not remove" in first.stderr
    assert (apps / "mu2e-cr01.desktop").exists()
    assert record.read_text().strip() == str(apps / "mu2e-cr01.desktop")
    second = subprocess.run(uninstall, env=env, capture_output=True, text=True)
    assert second.returncode == 0, second.stderr
    assert not (apps / "mu2e-cr01.desktop").exists() and not record.exists()


def test_partial_bundle_removal_keeps_marker_for_retry(tmp_path):
    """A macOS bundle that can only be partly deleted keeps its marker, so
    a second --uninstall recognizes it and finishes (runs on any OS: only
    the files are made, no icon is needed)."""
    record = tmp_path / ".config" / "mu2edaq-remote-site" / "caltech.installed"
    record.parent.mkdir(parents=True)
    bash("load_site caltech; INSTALLED_LIST=%s; make_icns() { return 1; }; "
         "install_mac_launcher cr01" % record, tmp_path)
    bundle = tmp_path / "Applications" / "Mu2e" / "Mu2e cr01.app"
    marker = bundle / "Contents" / "Resources" / "X-Mu2e-Remote-Site"
    macos = bundle / "Contents" / "MacOS"
    env = dict(os.environ, HOME=str(tmp_path), CRS_NO_PAUSE="1")
    env.pop("XDG_CONFIG_HOME", None)
    uninstall = [os.path.join(SITE_DIR, "install.sh"), "--site", "caltech", "--uninstall"]
    if os.geteuid() == 0:
        pytest.skip("root ignores directory permissions")
    macos.chmod(0o555)
    try:
        first = subprocess.run(uninstall, env=env, capture_output=True, text=True)
    finally:
        macos.chmod(0o755)
    assert first.returncode != 0 and "could not remove" in first.stderr
    assert marker.read_text().strip() == "caltech"
    assert record.read_text().strip() == str(bundle)
    second = subprocess.run(uninstall, env=env, capture_output=True, text=True)
    assert second.returncode == 0, second.stderr
    assert not bundle.exists() and not record.exists()


def test_uninstall_leaves_unmarked_bundle(tmp_path):
    """An unmarked bundle with content, listed in the record, is left alone."""
    foreign = tmp_path / "Applications" / "Mu2e" / "Mu2e cr01.app" / "Contents"
    foreign.mkdir(parents=True)
    (foreign / "Info.plist").write_text("someone else's app")
    record = tmp_path / "installed"
    record.write_text(str(foreign.parent) + "\n")
    bash("load_site caltech; INSTALLED_LIST=%s; uninstall_recorded" % record, tmp_path)
    assert (foreign / "Info.plist").read_text() == "someone else's app"


def _mac_bundle_with_record(tmp_path):
    """A generated macOS bundle for cr01 (icon step stubbed) and its record."""
    record = tmp_path / ".config" / "mu2edaq-remote-site" / "caltech.installed"
    record.parent.mkdir(parents=True, exist_ok=True)
    bash("load_site caltech; INSTALLED_LIST=%s; make_icns() { return 1; }; "
         "install_mac_launcher cr01" % record, tmp_path)
    return tmp_path / "Applications" / "Mu2e" / "Mu2e cr01.app", record


def _uninstall(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path), CRS_NO_PAUSE="1")
    env.pop("XDG_CONFIG_HOME", None)
    return subprocess.run([os.path.join(SITE_DIR, "install.sh"), "--site", "caltech",
                           "--uninstall"], env=env, capture_output=True, text=True)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_bundle_retry_after_parent_rmdir_failure(tmp_path):
    """Removal fails at the last rmdir (parent not writable): the retry
    removes the empty remains and the record."""
    bundle, record = _mac_bundle_with_record(tmp_path)
    parent = bundle.parent
    parent.chmod(0o555)
    try:
        first = _uninstall(tmp_path)
    finally:
        parent.chmod(0o755)
    assert first.returncode != 0 and "could not remove" in first.stderr
    assert record.exists()
    second = _uninstall(tmp_path)
    assert second.returncode == 0, second.stderr
    assert not bundle.exists() and not record.exists()


def test_uninstall_never_follows_links_out_of_a_bundle(tmp_path):
    """Contents/Resources replaced by a link to an outside directory: the
    bundle no longer counts as ours, and nothing outside is deleted."""
    bundle, record = _mac_bundle_with_record(tmp_path)
    outside = tmp_path / "outside"
    shutil.move(str(bundle / "Contents" / "Resources"), str(outside))
    (outside / "sentinel").write_text("keep")
    (bundle / "Contents" / "Resources").symlink_to(outside)
    result = _uninstall(tmp_path)
    assert result.returncode == 0, result.stderr
    assert (outside / "sentinel").read_text() == "keep"
    assert (outside / "X-Mu2e-Remote-Site").exists()
    assert bundle.exists()


def test_uninstall_removes_link_not_target_inside_owned_bundle(tmp_path):
    """Contents/MacOS replaced by a link to an outside directory in an
    otherwise owned bundle: the link goes, the outside files stay."""
    bundle, record = _mac_bundle_with_record(tmp_path)
    outside = tmp_path / "outside-macos"
    shutil.move(str(bundle / "Contents" / "MacOS"), str(outside))
    (outside / "sentinel").write_text("keep")
    (bundle / "Contents" / "MacOS").symlink_to(outside)
    result = _uninstall(tmp_path)
    assert result.returncode == 0, result.stderr
    assert not bundle.exists()
    assert (outside / "sentinel").read_text() == "keep"
    assert (outside / "launcher").exists()


def test_empty_skeleton_rule_keeps_anything_with_files(tmp_path):
    """A recorded .app path that is not marked but holds a file is left."""
    app = tmp_path / "Applications" / "Mu2e" / "Mu2e cr01.app"
    (app / "Contents").mkdir(parents=True)
    (app / "Contents" / "note").write_text("someone's")
    record = tmp_path / "installed"
    record.write_text(str(app) + "\n")
    bash("load_site caltech; INSTALLED_LIST=%s; uninstall_recorded" % record, tmp_path)
    assert (app / "Contents" / "note").read_text() == "someone's"
