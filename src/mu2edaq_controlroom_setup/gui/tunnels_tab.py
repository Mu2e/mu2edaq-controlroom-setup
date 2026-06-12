"""Tunnels tab: one row per VNC session with tunnel state and actions.

All ssh work happens in a worker thread; results come back to the UI
thread via Qt signals (never touch widgets from the worker).
"""

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..tunnels import TunnelManager
from ..sshutil import KerberosError
from .. import viewer as viewer_mod

REFRESH_MS = 15000


class _TunnelWorker(QThread):
    """Runs one tunnel operation (or a status sweep) off the UI thread."""
    result = pyqtSignal(str, str)        # session name, state
    error = pyqtSignal(str)

    def __init__(self, manager, action, sessions, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.action = action             # 'status' | 'open' | 'close' | 'connect'
        self.sessions = sessions

    def run(self):
        for session in self.sessions:
            try:
                if self.action == "status":
                    state = self.manager.status(session)
                elif self.action == "open":
                    self.manager.open(session)
                    state = "open"
                elif self.action == "close":
                    self.manager.close(session)
                    state = "closed"
                elif self.action == "connect":
                    if self.manager.status(session) != "open":
                        self.manager.open(session)
                    viewer_mod.attach(session)
                    state = "open"
                else:
                    continue
                self.result.emit(session.name, state)
            except (KerberosError, RuntimeError) as exc:
                self.error.emit(str(exc))
                return


class TunnelsTab(QWidget):
    COLS = ("Session", "Host", "Account", "Display", "Local port",
            "State", "", "", "")

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.manager = TunnelManager(config)
        self._workers = []
        self._build_ui()
        self.refresh()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(REFRESH_MS)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget(len(self.config.sessions), len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)

        for row, session in enumerate(self.config.sessions):
            for col, text in enumerate((
                    session.name, session.host.split(".")[0], session.account,
                    ":%d" % session.display, str(session.local_port))):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(row, col, item)
            state = QTableWidgetItem("…")
            state.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, 5, state)
            for col, (label, action) in enumerate(
                    (("Open", "open"), ("Close", "close"), ("Connect", "connect")),
                    start=6):
                btn = QPushButton(label)
                btn.clicked.connect(
                    lambda _, s=session, a=action: self._do(a, [s]))
                self.table.setCellWidget(row, col, btn)
        layout.addWidget(self.table)

        controls = QHBoxLayout()
        for label, action in (("Open all", "open"), ("Close all", "close"),
                              ("Refresh", "status")):
            btn = QPushButton(label)
            btn.clicked.connect(
                lambda _, a=action: self._do(a, list(self.config.sessions)))
            controls.addWidget(btn)
        controls.addStretch()
        self.status_label = QLabel("")
        controls.addWidget(self.status_label)
        layout.addLayout(controls)

    def refresh(self):
        self._do("status", list(self.config.sessions))

    def _do(self, action, sessions):
        worker = _TunnelWorker(self.manager, action, sessions, parent=self)
        worker.result.connect(self._on_result)
        worker.error.connect(self._on_error)
        worker.finished.connect(lambda w=worker: self._workers.remove(w))
        self._workers.append(worker)
        worker.start()

    def _on_result(self, name, state):
        for row, session in enumerate(self.config.sessions):
            if session.name == name:
                item = self.table.item(row, 5)
                item.setText(state)
                color = Qt.GlobalColor.darkGreen if state == "open" \
                    else Qt.GlobalColor.darkRed
                item.setForeground(color)
                break

    def _on_error(self, message):
        QMessageBox.warning(self, "Tunnel error", message)
