"""Session model for the control room VNC viewports."""

from dataclasses import dataclass, field

VNC_BASE_PORT = 5900


@dataclass(frozen=True)
class Session:
    name: str
    host: str
    account: str
    display: int
    geometry: str = "1920x1080"
    depth: int = 24
    local_port: int = 0

    @property
    def vnc_port(self):
        return VNC_BASE_PORT + self.display

    @property
    def target(self):
        """ssh destination, e.g. mu2edaq@mu2e-dl-01.fnal.gov"""
        return "%s@%s" % (self.account, self.host)

    def __str__(self):
        return "%s (%s :%d %s, local %d)" % (
            self.name, self.target, self.display, self.geometry, self.local_port
        )


@dataclass
class ControlRoomConfig:
    gateway: str
    personal_user: str
    install_dir: str
    vnc_password_file: str
    discovery: dict
    accounts: list
    sessions: list = field(default_factory=list)

    def session(self, name):
        for s in self.sessions:
            if s.name == name:
                return s
        raise KeyError("no session named %r (have: %s)" %
                       (name, ", ".join(s.name for s in self.sessions)))

    def sessions_on(self, host):
        return [s for s in self.sessions if s.host == host or
                s.host.split(".")[0] == host.split(".")[0]]
