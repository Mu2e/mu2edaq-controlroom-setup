"""Launch a VNC viewer against an open tunnel.

Follows the AttachVNC pattern from
mu2edaq-controlroom/Mu2eCR/ControlRoom/scripts/Tools.py:
vncviewer -Shared so multiple operators can attach to one session.
"""

import os
import shutil
import subprocess

MAC_VIEWER = "/Applications/TigerVNC Viewer.app/Contents/MacOS/TigerVNC Viewer"


def find_viewer():
    path = shutil.which("vncviewer")
    if path:
        return path
    if os.access(MAC_VIEWER, os.X_OK):
        return MAC_VIEWER
    return None


def attach(session, viewer=None):
    """Spawn vncviewer -Shared against the session's local tunnel port.
    Returns the Popen handle (caller does not wait)."""
    viewer = viewer or find_viewer()
    if not viewer:
        raise RuntimeError(
            "no VNC viewer found; install TigerVNC (vncviewer) or pass --viewer")
    return subprocess.Popen(
        [viewer, "-Shared", "localhost:%d" % session.local_port],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
