"""crs-gui: Mu2e control room manager (tunnels + discovery)."""

import argparse
import sys

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QTabWidget,
)

from ..config import ConfigError, load_config
from ..tunnels import TunnelManager
from ..sshutil import KerberosError
from .. import viewer as viewer_mod
from .discovery_tab import DiscoveryTab
from .tunnels_tab import TunnelsTab


class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setWindowTitle("Mu2e Control Room")
        self.resize(900, 420)

        tabs = QTabWidget()
        self.tunnels_tab = TunnelsTab(config)
        self.discovery_tab = DiscoveryTab(config)
        tabs.addTab(self.tunnels_tab, "Tunnels")
        tabs.addTab(self.discovery_tab, "Discovery")
        self.setCentralWidget(tabs)

        self.discovery_tab.connect_requested.connect(self._connect_to_vnc)

    def _connect_to_vnc(self, host, port):
        """Discovery tab double-click: map host/port to a configured
        session, open its tunnel, and attach the viewer."""
        short = host.split(".")[0]
        for session in self.config.sessions:
            if session.host.split(".")[0] == short and session.vnc_port == port:
                try:
                    manager = TunnelManager(self.config)
                    if manager.status(session) != "open":
                        manager.open(session)
                    viewer_mod.attach(session)
                except (KerberosError, RuntimeError) as exc:
                    QMessageBox.warning(self, "Connect failed", str(exc))
                return
        QMessageBox.information(
            self, "Unknown session",
            "%s:%d is not one of the configured control room sessions." %
            (host, port))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="crs-gui", description="Mu2e control room manager GUI.")
    parser.add_argument("--config", default=None, help="controlroom.yaml path")
    args = parser.parse_args(argv)

    app = QApplication(sys.argv[:1])
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        QMessageBox.critical(None, "Configuration error", str(exc))
        return 1
    window = MainWindow(config)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
