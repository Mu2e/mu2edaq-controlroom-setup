"""SSH tunnel lifecycle for the VNC sessions.

One master ssh per session (-f -N -M with a control socket in ~/.crs),
forwarding local_port -> localhost:vnc_port on the session host through
the gateway. Generalizes mu2edaq-controlroom/bin/start_vnc_tunnels_mu2e.sh.
"""

import os
import subprocess

from . import sshutil


class TunnelManager:
    def __init__(self, config, ssh_config=None):
        self.config = config
        self.ssh_config = ssh_config

    def _socket(self, session):
        return sshutil.control_socket_path(session.host, session.local_port)

    def status(self, session):
        """'open' | 'closed' for one session's tunnel."""
        socket_path = self._socket(session)
        if not os.path.exists(socket_path):
            return "closed"
        result = subprocess.run(
            sshutil.tunnel_check_argv(session.target, socket_path),
            capture_output=True,
        )
        if result.returncode == 0:
            return "open"
        # Stale socket: clean it up so the next open succeeds.
        try:
            os.remove(socket_path)
        except OSError:
            pass
        return "closed"

    def open(self, session):
        """Open the tunnel for a session. Returns 'open' or 'already-open'."""
        if self.status(session) == "open":
            return "already-open"
        sshutil.check_ticket()
        argv = sshutil.tunnel_open_argv(
            session.target, session.local_port, session.vnc_port,
            self._socket(session), gateway=self.config.gateway,
            ssh_config=self.ssh_config,
        )
        result = subprocess.run(argv, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError("tunnel open failed for %s: %s" %
                               (session.name, result.stderr.strip()))
        return "open"

    def close(self, session):
        """Close the tunnel for a session. Returns 'closed' or 'not-open'."""
        socket_path = self._socket(session)
        if not os.path.exists(socket_path):
            return "not-open"
        subprocess.run(
            sshutil.tunnel_close_argv(session.target, socket_path),
            capture_output=True,
        )
        if os.path.exists(socket_path):
            try:
                os.remove(socket_path)
            except OSError:
                pass
        return "closed"

    def status_all(self):
        """[(session, 'open'|'closed'), ...] for every configured session."""
        return [(s, self.status(s)) for s in self.config.sessions]
