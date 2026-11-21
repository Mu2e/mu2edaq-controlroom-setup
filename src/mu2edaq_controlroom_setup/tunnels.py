"""SSH tunnel lifecycle for the VNC sessions.

One master ssh per session (-f -N -M with a control socket in ~/.crs),
forwarding local_port -> localhost:vnc_port on the session host through
the gateway. Generalizes mu2edaq-controlroom/bin/start_vnc_tunnels_mu2e.sh.
"""

import os
import shlex
import subprocess
import sys
import time

from . import sshutil

# Runs argv[1:] with SIGHUP ignored and SIGPIPE back at its default, like
# nohup(1) but without its stdin/stdout side effects. Used instead of a
# preexec_fn because the GUI opens tunnels from a worker thread.
_NOHUP = ("import os, signal, sys; "
          "signal.signal(signal.SIGHUP, signal.SIG_IGN); "
          "signal.signal(signal.SIGPIPE, signal.SIG_DFL); "
          "os.execvp(sys.argv[1], sys.argv[1:])")


def nohup_argv(argv):
    """argv that runs `argv` with SIGHUP ignored (inherited across exec)."""
    return [sys.executable, "-c", _NOHUP] + list(argv)


class TunnelManager:
    def __init__(self, config, ssh_config=None):
        self.config = config
        self.ssh_config = ssh_config

    def _socket(self, session):
        return sshutil.control_socket_path(session.host, session.local_port)

    def _login_target(self, session):
        """ssh login destination for the forward.

        A tunnel only needs SSH access to the host; the forward target
        (localhost:vnc_port) is resolved on the server side regardless of
        login user, so log in as the personal user rather than the shared
        VNC account (which usually won't accept our Kerberos principal).
        Fall back to the session account if no personal user is configured.
        """
        user = self.config.personal_user or session.account
        return "%s@%s" % (user, session.host)

    def status(self, session):
        """'open' | 'closed' for one session's tunnel."""
        socket_path = self._socket(session)
        if not os.path.exists(socket_path):
            return "closed"
        result = subprocess.run(
            sshutil.tunnel_check_argv(self._login_target(session), socket_path),
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
            self._login_target(session), session.local_port, session.vnc_port,
            self._socket(session), gateway=self.config.gateway,
            ssh_config=self.ssh_config,
        )
        # ssh's output goes to a log file, not a pipe. With a gateway, the
        # ProxyJump child (`ssh -W`) is started before authentication and
        # inherits ssh's stderr; it keeps it open for as long as the tunnel
        # lives, so reading a pipe to EOF (capture_output) never returns.
        # stdin and the controlling terminal are left alone, so password and
        # host-key prompts (read from /dev/tty) work as before. SIGHUP is
        # ignored so the tunnel survives closing the terminal it was opened
        # from; OpenSSH keeps an inherited SIG_IGN for SIGHUP.
        log_path = sshutil.tunnel_log_path()
        with open(log_path, "a") as log:
            log.write("--- %s %s: %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"),
                                            session.name, shlex.join(argv)))
            log.flush()
            start = log.tell()
            result = subprocess.run(nohup_argv(argv), stdout=log, stderr=log)
        if result.returncode != 0:
            with open(log_path) as log:
                log.seek(start)
                detail = log.read().strip()
            raise RuntimeError("tunnel open failed for %s: %s" %
                               (session.name, detail or
                                "ssh exit status %d" % result.returncode))
        return "open"

    def close(self, session):
        """Close the tunnel for a session. Returns 'closed' or 'not-open'."""
        socket_path = self._socket(session)
        if not os.path.exists(socket_path):
            return "not-open"
        subprocess.run(
            sshutil.tunnel_close_argv(self._login_target(session), socket_path),
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
