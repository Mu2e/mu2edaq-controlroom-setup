"""Remote orchestration: run server-side commands per session over ssh.

Implements crs-remote {start|stop|status|install|provision}. The install
command ships the server/ payload plus rendered configs as a tar stream
over the ssh channel.
"""

import io
import os
import subprocess
import tarfile

from . import sshutil

SERVER_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "server",
)

PAYLOAD_FILES = [
    "start-vnc-session.sh", "stop-vnc-session.sh", "status-vnc-session.sh",
    "vnc-discovery-responder.py", "crs-app", "crs-provision-desktop",
    "xstartup", "install-controlroom.sh",
]


class RemoteRunner:
    def __init__(self, config, ssh_config=None, config_dir=None):
        self.config = config
        self.ssh_config = ssh_config
        self.config_dir = config_dir

    def _run(self, target, command, capture=True):
        sshutil.check_ticket()
        argv = sshutil.remote_command_argv(
            target, command, gateway=self.config.gateway,
            ssh_config=self.ssh_config,
        )
        return subprocess.run(argv, capture_output=capture, text=True)

    # -- per-session operations --------------------------------------------

    def start(self, session):
        cmd = ("~/controlroom/bin/start-vnc-session.sh %s %d -g %s -d %d" %
               (session.name, session.display, session.geometry, session.depth))
        return self._run(session.target, cmd)

    def stop(self, session):
        cmd = ("~/controlroom/bin/stop-vnc-session.sh %s %d" %
               (session.name, session.display))
        return self._run(session.target, cmd)

    def status(self, session):
        cmd = ("~/controlroom/bin/status-vnc-session.sh %s %d" %
               (session.name, session.display))
        return self._run(session.target, cmd)

    def provision(self, session):
        cmd = "~/controlroom/bin/crs-provision-desktop --session %s" % session.name
        return self._run(session.target, cmd)

    # -- installation -------------------------------------------------------

    def _build_payload(self):
        """In-memory tar of server scripts + configs."""
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for fname in PAYLOAD_FILES:
                path = os.path.join(SERVER_DIR, fname)
                if os.path.exists(path):
                    tar.add(path, arcname=os.path.join("crs-payload", fname))
            config_dir = self.config_dir or os.path.join(
                os.path.dirname(SERVER_DIR), "config")
            for fname in ("controlroom.yaml", "apps.yaml"):
                path = os.path.join(config_dir, fname)
                if os.path.exists(path):
                    tar.add(path, arcname=os.path.join("crs-payload", fname))
        return buf.getvalue()

    def install(self, session):
        """Ship the payload to the session account and run the installer."""
        sshutil.check_ticket()
        payload = self._build_payload()
        argv = sshutil.base_ssh_args(self.config.gateway, self.ssh_config) + [
            "-o", "BatchMode=yes",
            session.target,
            "rm -rf ~/.crs-payload && mkdir -p ~/.crs-payload && "
            "tar xzf - -C ~/.crs-payload --strip-components=1 && "
            "bash ~/.crs-payload/install-controlroom.sh && "
            "rm -rf ~/.crs-payload",
        ]
        return subprocess.run(argv, input=payload, capture_output=True)

    # -- selection helpers ---------------------------------------------------

    def select(self, session=None, host=None, all_sessions=False):
        """Resolve --session/--host/--all to a session list. Install/status
        style commands operate once per (host, account) pair when selecting
        by host or all."""
        if session:
            return [self.config.session(session)]
        if host:
            matched = self.config.sessions_on(host)
            if not matched:
                raise KeyError("no sessions on host %r" % host)
            return matched
        if all_sessions:
            return list(self.config.sessions)
        raise ValueError("select a target: --session NAME, --host H, or --all")
