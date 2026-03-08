"""Profile page: launch a command under MangoHud with a timer."""
from __future__ import annotations
import argparse
from typing import Optional

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from mangohudpy.profile import cmd_profile
from mangohudpy.gui.widgets import LogViewer
from mangohudpy.gui.worker import Worker


class ProfilePage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        outer.addWidget(splitter)

        # ── top pane: controls ────────────────────────────────────────
        top = QWidget()
        layout = QVBoxLayout(top)
        layout.addWidget(QLabel("<h2>Profile</h2>"))
        layout.addWidget(QLabel(
            "Launch any command under MangoHud. "
            "MangoHud will log performance data to ~/mangologs/.",
        ))

        cmd_row = QHBoxLayout()
        cmd_row.addWidget(QLabel("Command:"))
        self.cmd_edit = QLineEdit()
        self.cmd_edit.setPlaceholderText("e.g.  %command%  or  /usr/bin/game")
        cmd_row.addWidget(self.cmd_edit, stretch=1)
        layout.addLayout(cmd_row)

        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("Duration (seconds):"))
        self.dur_spin = QDoubleSpinBox()
        self.dur_spin.setRange(5, 7200)
        self.dur_spin.setValue(60)
        self.dur_spin.setSingleStep(10)
        dur_row.addWidget(self.dur_spin)
        dur_row.addStretch()
        layout.addLayout(dur_row)

        self.summary_check = QCheckBox("Auto-summary after profiling")
        self.summary_check.setChecked(True)
        self.graph_check = QCheckBox("Auto-generate graphs after profiling")
        layout.addWidget(self.summary_check)
        layout.addWidget(self.graph_check)

        self.launch_btn = QPushButton("Launch")
        self.launch_btn.clicked.connect(self._launch)
        layout.addWidget(self.launch_btn)
        layout.addStretch()

        splitter.addWidget(top)

        # ── bottom pane: log output ───────────────────────────────────
        self.log = LogViewer()
        splitter.addWidget(self.log)

        splitter.setSizes([250, 450])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

    def on_game_selected(self, game: str) -> None:
        pass  # profile takes an arbitrary command, not game-filtered

    def _launch(self) -> None:
        cmd = self.cmd_edit.text().strip()
        if not cmd:
            self.log.append_line("Enter a command to profile.")
            return
        args = argparse.Namespace(
            command=cmd,
            duration=self.dur_spin.value(),
            log_dir=None,
            config=None,
            auto_summary=self.summary_check.isChecked(),
            auto_graph=self.graph_check.isChecked(),
            graph_output=None,
            graph_format="png",
        )
        self.launch_btn.setEnabled(False)
        self.log.clear_log()
        self.log.append_line(f"Launching: {cmd}  ({self.dur_spin.value():.0f}s)")
        worker = Worker(cmd_profile, args)
        worker.signals.output.connect(self.log.append_line)
        worker.signals.error.connect(self.log.append_line)
        worker.signals.finished.connect(lambda: self.launch_btn.setEnabled(True))
        QThreadPool.globalInstance().start(worker)
