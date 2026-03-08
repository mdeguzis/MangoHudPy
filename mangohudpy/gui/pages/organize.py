"""Organize page: source/dest pickers, dry-run toggle, auto-organize timer, live log output."""
from __future__ import annotations
import argparse
import subprocess
from typing import Optional

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from mangohudpy.constants import BENCH_LOG_DIR, MAX_LOGS_PER_GAME
from mangohudpy.organize import cmd_organize
from mangohudpy.gui.widgets import LogViewer
from mangohudpy.gui.worker import Worker

_TIMER = "mangohud-organize.timer"


class OrganizePage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        outer.addWidget(splitter)

        # ── top pane: controls ────────────────────────────────────────
        top = QWidget()
        layout = QVBoxLayout(top)
        layout.addWidget(QLabel("<h2>Organize Logs</h2>"))
        layout.addWidget(QLabel(
            "Copy logs from /tmp/MangoHud into ~/mangologs/&lt;GameName&gt;/ "
            "with rotation and current symlinks."
        ))

        src_row = QHBoxLayout()
        src_row.addWidget(QLabel("Source:"))
        self.src_edit = QLineEdit()
        self.src_edit.setPlaceholderText("Default: /tmp/MangoHud + ~/mangologs")
        src_row.addWidget(self.src_edit, stretch=1)
        src_btn = QPushButton("Browse")
        src_btn.clicked.connect(lambda: self._browse(self.src_edit))
        src_row.addWidget(src_btn)
        layout.addLayout(src_row)

        dst_row = QHBoxLayout()
        dst_row.addWidget(QLabel("Dest:"))
        self.dst_edit = QLineEdit(str(BENCH_LOG_DIR))
        dst_row.addWidget(self.dst_edit, stretch=1)
        dst_btn = QPushButton("Browse")
        dst_btn.clicked.connect(lambda: self._browse(self.dst_edit))
        dst_row.addWidget(dst_btn)
        layout.addLayout(dst_row)

        opts_row = QHBoxLayout()
        opts_row.addWidget(QLabel("Max logs per game:"))
        self.max_spin = QSpinBox()
        self.max_spin.setRange(1, 100)
        self.max_spin.setValue(MAX_LOGS_PER_GAME)
        opts_row.addWidget(self.max_spin)
        self.dry_check = QCheckBox("Dry run (preview only)")
        opts_row.addWidget(self.dry_check)
        opts_row.addStretch()
        layout.addLayout(opts_row)

        self.run_btn = QPushButton("Run Organize")
        self.run_btn.clicked.connect(self._run)
        layout.addWidget(self.run_btn)

        # ── auto-organize timer ───────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        layout.addWidget(QLabel("<b>Auto-Organize Timer</b> (systemd user timer)"))

        status_row = QHBoxLayout()
        self.status_label = QLabel("Status: checking…")
        status_row.addWidget(self.status_label, stretch=1)
        refresh_status_btn = QPushButton("Check Status")
        refresh_status_btn.clicked.connect(self._check_status_to_log)
        status_row.addWidget(refresh_status_btn)
        layout.addLayout(status_row)

        auto_row = QHBoxLayout()
        auto_row.addWidget(QLabel("Run every"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 1440)
        self.interval_spin.setValue(30)
        auto_row.addWidget(self.interval_spin)
        auto_row.addWidget(QLabel("minutes"))
        auto_row.addStretch()
        layout.addLayout(auto_row)

        auto_btn_row = QHBoxLayout()
        enable_btn = QPushButton("Enable Auto-Organize")
        enable_btn.clicked.connect(self._enable_auto)
        auto_btn_row.addWidget(enable_btn)
        disable_btn = QPushButton("Disable Auto-Organize")
        disable_btn.clicked.connect(self._disable_auto)
        auto_btn_row.addWidget(disable_btn)
        auto_btn_row.addStretch()
        layout.addLayout(auto_btn_row)
        layout.addStretch()
        self._refresh_status()

        splitter.addWidget(top)

        # ── bottom pane: log output ───────────────────────────────────
        self.log = LogViewer()
        splitter.addWidget(self.log)

        splitter.setSizes([300, 400])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

    def on_game_selected(self, game: str) -> None:
        pass  # organize operates on full log dirs, not per-game

    def _refresh_status(self) -> None:
        """Query systemctl for the timer state and update the status label."""
        try:
            active = subprocess.run(
                ["systemctl", "--user", "is-active", _TIMER],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            enabled = subprocess.run(
                ["systemctl", "--user", "is-enabled", _TIMER],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.status_label.setText("Status: systemctl not available")
            self.status_label.setStyleSheet("color: #888888;")
            return

        if active == "active":
            self.status_label.setText(f"Status: active  (enabled: {enabled})")
            self.status_label.setStyleSheet("color: #2ecc71; font-weight: bold;")
        elif enabled in ("enabled", "enabled-runtime"):
            self.status_label.setText(f"Status: inactive  (enabled: {enabled})")
            self.status_label.setStyleSheet("color: #f39c12;")
        else:
            self.status_label.setText("Status: not installed")
            self.status_label.setStyleSheet("color: #888888;")

    def _check_status_to_log(self) -> None:
        """Update status label and dump full systemctl status to the log pane."""
        self._refresh_status()
        self.log.clear_log()
        try:
            result = subprocess.run(
                ["systemctl", "--user", "status", _TIMER],
                capture_output=True, text=True, timeout=5,
            )
            output = (result.stdout + result.stderr).strip()
            if output:
                for line in output.splitlines():
                    self.log.append_line(line)
            else:
                self.log.append_line(f"{_TIMER}: no output from systemctl status")
        except FileNotFoundError:
            self.log.append_line("systemctl not found in PATH")
        except subprocess.TimeoutExpired:
            self.log.append_line("systemctl status timed out")

    def _browse(self, edit: QLineEdit) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select Directory", edit.text())
        if d:
            edit.setText(d)

    def _enable_auto(self) -> None:
        from mangohudpy.config import cmd_auto_organize
        args = argparse.Namespace(interval=self.interval_spin.value(), disable=False)
        self.log.clear_log()
        worker = Worker(cmd_auto_organize, args)
        worker.signals.output.connect(self.log.append_line)
        worker.signals.error.connect(self.log.append_line)
        worker.signals.finished.connect(self._refresh_status)
        QThreadPool.globalInstance().start(worker)

    def _disable_auto(self) -> None:
        from mangohudpy.config import cmd_auto_organize
        args = argparse.Namespace(interval=30, disable=True)
        self.log.clear_log()
        worker = Worker(cmd_auto_organize, args)
        worker.signals.output.connect(self.log.append_line)
        worker.signals.error.connect(self.log.append_line)
        worker.signals.finished.connect(self._refresh_status)
        QThreadPool.globalInstance().start(worker)

    def _run(self) -> None:
        src = self.src_edit.text().strip() or None
        args = argparse.Namespace(
            source=src,
            dest=self.dst_edit.text().strip() or str(BENCH_LOG_DIR),
            max_logs=self.max_spin.value(),
            dry_run=self.dry_check.isChecked(),
        )
        self.run_btn.setEnabled(False)
        self.log.clear_log()
        worker = Worker(cmd_organize, args)
        worker.signals.output.connect(self.log.append_line)
        worker.signals.error.connect(self.log.append_line)
        worker.signals.finished.connect(lambda: self.run_btn.setEnabled(True))
        QThreadPool.globalInstance().start(worker)
