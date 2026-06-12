"""Discovery tab: scan for running DAQ services and list the responses.

Two scan modes:
  - Local multicast: mu2edaq_discovery.discover() on the local segment.
  - Via gateway (production): run `mu2edaq-discover --json` on a cluster
    node over ssh and parse the output, since multicast does not
    traverse the FNAL gateway.

Self-contained widget so it can be lifted into a standalone app.
"""

import json
import subprocess

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .. import sshutil
from ..sshutil import KerberosError

COLUMNS = ("Name", "App", "Host", "Port", "Started", "PID", "Id")


class _ScanWorker(QThread):
    found = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, mode, config, remote_target=None, parent=None):
        super().__init__(parent)
        self.mode = mode                 # 'local' | 'gateway'
        self.config = config
        self.remote_target = remote_target

    def run(self):
        try:
            if self.mode == "local":
                from mu2edaq_discovery import discover
                disc = self.config.discovery
                results = discover(
                    timeout=float(disc.get("timeout", 2.0)),
                    group=disc.get("group", "239.255.42.99"),
                    port=int(disc.get("port", 28999)),
                )
            else:
                sshutil.check_ticket()
                argv = sshutil.remote_command_argv(
                    self.remote_target,
                    "~/controlroom/bin/mu2edaq-discover --json 2>/dev/null"
                    " || mu2edaq-discover --json",
                    gateway=self.config.gateway,
                )
                proc = subprocess.run(argv, capture_output=True, text=True,
                                      timeout=30)
                if proc.returncode != 0:
                    raise RuntimeError(
                        "remote scan failed: %s" % proc.stderr.strip())
                results = json.loads(proc.stdout or "[]")
            self.found.emit(results)
        except (ImportError, KerberosError, RuntimeError,
                json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
            self.error.emit(str(exc))


class DiscoveryTab(QWidget):
    # Emitted when the user double-clicks a vnc row; main window connects
    # this to the tunnels machinery.
    connect_requested = pyqtSignal(str, int)     # host, port

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Scan mode:"))
        self.mode_box = QComboBox()
        self.mode_box.addItem("Via gateway (production)", "gateway")
        self.mode_box.addItem("Local multicast", "local")
        controls.addWidget(self.mode_box)
        controls.addWidget(QLabel("via:"))
        self.target_box = QComboBox()
        seen = set()
        for s in self.config.sessions:
            if s.target not in seen:
                seen.add(s.target)
                self.target_box.addItem(s.target)
        controls.addWidget(self.target_box)
        self.scan_btn = QPushButton("Scan")
        self.scan_btn.clicked.connect(self.scan)
        controls.addWidget(self.scan_btn)
        controls.addStretch()
        self.status_label = QLabel("")
        controls.addWidget(self.status_label)
        layout.addLayout(controls)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)

    def scan(self):
        if self._worker and self._worker.isRunning():
            return
        self.scan_btn.setEnabled(False)
        self.status_label.setText("scanning…")
        mode = self.mode_box.currentData()
        self._worker = _ScanWorker(
            mode, self.config,
            remote_target=self.target_box.currentText(), parent=self)
        self._worker.found.connect(self._on_found)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(
            lambda: self.scan_btn.setEnabled(True))
        self._worker.start()

    def _on_found(self, results):
        self.status_label.setText("%d service(s)" % len(results))
        self.table.setRowCount(len(results))
        for row, svc in enumerate(results):
            values = (svc.get("name", ""), svc.get("app", ""),
                      svc.get("host", ""), str(svc.get("port", "")),
                      svc.get("started", ""), str(svc.get("pid", "")),
                      svc.get("id", ""))
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled |
                              Qt.ItemFlag.ItemIsSelectable)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, svc)
                self.table.setItem(row, col, item)

    def _on_error(self, message):
        self.status_label.setText("scan failed")
        QMessageBox.warning(self, "Discovery error", message)

    def _on_double_click(self, item):
        svc = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
        if svc and svc.get("app") == "vnc":
            self.connect_requested.emit(svc.get("host", ""),
                                        int(svc.get("port", 0)))
