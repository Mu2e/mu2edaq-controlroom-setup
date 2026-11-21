"""Launch a VNC viewer against an open tunnel.

Follows the AttachVNC pattern from
mu2edaq-controlroom/Mu2eCR/ControlRoom/scripts/Tools.py:
vncviewer -Shared so multiple operators can attach to one session.

On macOS, with no explicit --viewer, hand the vnc:// URL to `open` so the
built-in Screen Sharing client connects (no TigerVNC install required).
Screen Sharing cannot be told to be view-only or to read a password file,
so when either is asked for, a TigerVNC viewer is required instead.
"""

import os
import shutil
import subprocess
import sys

MAC_VIEWER = "/Applications/TigerVNC Viewer.app/Contents/MacOS/TigerVNC Viewer"


def find_viewer():
    path = shutil.which("vncviewer")
    if path:
        return path
    if os.access(MAC_VIEWER, os.X_OK):
        return MAC_VIEWER
    return None


def resolve_password_file(pattern, session):
    """Password file for a session from a pattern, or None.

    The pattern may contain {account} and {session}, e.g.
    ~/.vnc/{account}.passwd. Returns None when the pattern is empty or the
    file does not exist (the viewer then asks for the password).
    """
    if not pattern:
        return None
    path = os.path.expanduser(pattern.format(account=session.account,
                                             session=session.name))
    return path if os.path.isfile(path) else None


def _log_path(session):
    run_dir = os.path.expanduser("~/.crs")
    os.makedirs(run_dir, exist_ok=True)
    return os.path.join(run_dir, "viewer-%s.log" % session.name)


def _spawn(argv, session):
    """Launch a viewer detached; caller does not wait.

    The viewer gets its own session, so closing the terminal it was started
    from does not hang it up. Its output is appended to
    ~/.crs/viewer-<session>.log.
    """
    with open(_log_path(session), "a") as log:
        return subprocess.Popen(
            argv, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            start_new_session=True,
        )


def attach(session, viewer=None, view_only=False, password_file=None):
    """Launch a VNC client against the session's local tunnel port.

    Returns the Popen handle (caller does not wait). On macOS, with no
    explicit viewer and neither view_only nor password_file, uses
    `open vnc://localhost:PORT` (Screen Sharing); otherwise runs
    `vncviewer -Shared [-ViewOnly] [PasswordFile=F] localhost::PORT`.
    Raises RuntimeError, before launching anything, if no suitable viewer
    is found.
    """
    needs_vncviewer = view_only or bool(password_file)
    if viewer is None and sys.platform == "darwin" and not needs_vncviewer:
        return _spawn(["open", "vnc://localhost:%d" % session.local_port],
                      session)
    viewer = viewer or find_viewer()
    if not viewer:
        if sys.platform == "darwin":
            raise RuntimeError(
                "view-only and saved passwords need TigerVNC Viewer: macOS "
                "Screen Sharing cannot apply them. Install TigerVNC Viewer.app "
                "in /Applications (https://tigervnc.org) or pass --viewer")
        raise RuntimeError(
            "no VNC viewer found; install TigerVNC (vncviewer) or pass --viewer")
    argv = [viewer, "-Shared"]
    if view_only:
        argv.append("-ViewOnly")
    if password_file:
        argv.append("PasswordFile=%s" % password_file)
    # host::port is read as a TCP port by both TigerVNC and RealVNC viewers
    argv.append("localhost::%d" % session.local_port)
    return _spawn(argv, session)
