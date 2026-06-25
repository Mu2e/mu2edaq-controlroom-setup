"""Launch a VNC viewer against an open tunnel.

Follows the AttachVNC pattern from
mu2edaq-controlroom/Mu2eCR/ControlRoom/scripts/Tools.py:
vncviewer -Shared so multiple operators can attach to one session.

On macOS, with no explicit --viewer, hand the vnc:// URL to `open` so the
built-in Screen Sharing client connects (no TigerVNC install required).
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


def _spawn(argv):
    """Launch a viewer detached; caller does not wait."""
    return subprocess.Popen(
        argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def attach(session, viewer=None):
    """Launch a VNC client against the session's local tunnel port.

    Returns the Popen handle (caller does not wait). On macOS, with no
    explicit viewer, uses `open vnc://localhost:PORT` (Screen Sharing);
    otherwise runs `vncviewer -Shared localhost:PORT`.
    """
    if viewer is None and sys.platform == "darwin":
        return _spawn(["open", "vnc://localhost:%d" % session.local_port])
    viewer = viewer or find_viewer()
    if not viewer:
        raise RuntimeError(
            "no VNC viewer found; install TigerVNC (vncviewer) or pass --viewer")
    return _spawn([viewer, "-Shared", "localhost:%d" % session.local_port])
