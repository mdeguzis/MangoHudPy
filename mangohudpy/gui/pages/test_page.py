"""Test page: verify MangoHud logging works via vkcube/glxgears."""
from __future__ import annotations
import argparse
from typing import Optional

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from mangohudpy.constants import MANGOHUD_LOG_DIR
from mangohudpy.test_cmd import cmd_test
from mangohudpy.gui.widgets import LogViewer
from mangohudpy.gui.worker import Worker


class TestPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        outer.addWidget(splitter)

        # ── top pane: controls ────────────────────────────────────────
        top = QWidget()
        layout = QVBoxLayout(top)
        layout.addWidget(QLabel("<h2>Test MangoHud Logging</h2>"))
        layout.addWidget(QLabel(
            "Verify that MangoHud can write CSV logs by running a short vkcube/glxgears "
            "session. Useful on Bazzite/SteamOS to confirm the gamescope override works."
        ))

        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("Duration (seconds):"))
        self.dur_spin = QSpinBox()
        self.dur_spin.setRange(2, 60)
        self.dur_spin.setValue(5)
        dur_row.addWidget(self.dur_spin)
        dur_row.addStretch()
        layout.addLayout(dur_row)

        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("Log dir:"))
        self.dir_edit = QLineEdit(str(MANGOHUD_LOG_DIR))
        dir_row.addWidget(self.dir_edit, stretch=1)
        layout.addLayout(dir_row)

        self.run_btn = QPushButton("Run Test")
        self.run_btn.clicked.connect(self._run)
        layout.addWidget(self.run_btn)
        layout.addStretch()

        splitter.addWidget(top)

        # ── bottom pane: log output ───────────────────────────────────
        self.log = LogViewer()
        splitter.addWidget(self.log)

        splitter.setSizes([220, 480])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

    def on_game_selected(self, game: str) -> None:
        pass  # test is not source-specific

    def _run(self) -> None:
        args = argparse.Namespace(
            log_dir=self.dir_edit.text().strip() or None,
            duration=self.dur_spin.value(),
            live=False,
        )
        self.run_btn.setEnabled(False)
        self.log.clear_log()
        self.log.append_line(f"Running MangoHud test ({self.dur_spin.value()}s)...")
        worker = Worker(cmd_test, args)
        worker.signals.output.connect(self.log.append_line)
        worker.signals.error.connect(self.log.append_line)
        worker.signals.finished.connect(lambda: self.run_btn.setEnabled(True))
        QThreadPool.globalInstance().start(worker)
