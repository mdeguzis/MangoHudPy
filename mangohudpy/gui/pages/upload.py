"""Upload page: token management, file checklist, bundle, upload to FlightlessSomething."""
from __future__ import annotations
import argparse
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from mangohudpy.constants import (
    BENCH_LOG_DIR, FLIGHTLESS_BASE, FLIGHTLESS_TOKEN_FILE,
)
from mangohudpy.utils import _extract_game_name, find_logs
from mangohudpy.upload import cmd_upload
from mangohudpy.gui.widgets import LogViewer
from mangohudpy.gui.worker import Worker


class UploadPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        outer.addWidget(splitter)

        # ── top pane: controls + file list ───────────────────────────
        top = QWidget()
        layout = QVBoxLayout(top)
        layout.addWidget(QLabel("<h2>Upload to FlightlessSomething</h2>"))

        tok_row = QHBoxLayout()
        tok_row.addWidget(QLabel("API Token:"))
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("Paste token or load from ~/.flightless-token")
        tok_row.addWidget(self.token_edit, stretch=1)
        save_tok_btn = QPushButton("Save Token")
        save_tok_btn.clicked.connect(self._save_token)
        tok_row.addWidget(save_tok_btn)
        layout.addLayout(tok_row)
        self._load_token()

        opt_row = QHBoxLayout()
        self.append_check = QCheckBox("Append to existing benchmark")
        self.force_check = QCheckBox("Force re-upload")
        opt_row.addWidget(self.append_check)
        opt_row.addWidget(self.force_check)
        opt_row.addStretch()
        layout.addLayout(opt_row)

        meta_row = QHBoxLayout()
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Benchmark title (optional)")
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Description (optional)")
        meta_row.addWidget(self.title_edit, stretch=1)
        meta_row.addWidget(self.desc_edit, stretch=1)
        layout.addLayout(meta_row)

        layout.addWidget(QLabel("Select files to upload:"))
        self.file_list = QTableWidget(0, 2)
        self.file_list.setHorizontalHeaderLabels(["File", "Title"])
        self.file_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.file_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.file_list.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.file_list.verticalHeader().setVisible(False)
        layout.addWidget(self.file_list, stretch=1)

        self.upload_btn = QPushButton("Upload Selected")
        self.upload_btn.clicked.connect(self._upload)
        layout.addWidget(self.upload_btn)

        # ── bundle section ────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        layout.addWidget(QLabel("<b>Bundle</b> — zip logs for manual upload or sharing"))
        bundle_row = QHBoxLayout()
        self.bundle_btn = QPushButton("Create Bundle Zip")
        self.bundle_btn.clicked.connect(self._bundle)
        bundle_row.addWidget(self.bundle_btn)
        bundle_row.addStretch()
        layout.addLayout(bundle_row)

        splitter.addWidget(top)

        # ── bottom pane: log output ───────────────────────────────────
        self.log = LogViewer()
        splitter.addWidget(self.log)

        splitter.setSizes([500, 200])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        self._game = ""
        self._refresh_files()

    def on_game_selected(self, game: str) -> None:
        self._game = game
        self._refresh_files()

    def _load_token(self) -> None:
        if FLIGHTLESS_TOKEN_FILE.exists():
            self.token_edit.setText(FLIGHTLESS_TOKEN_FILE.read_text().strip())

    def _save_token(self) -> None:
        tok = self.token_edit.text().strip()
        if tok:
            FLIGHTLESS_TOKEN_FILE.write_text(tok + "\n")
            FLIGHTLESS_TOKEN_FILE.chmod(0o600)
            self.log.append_line(f"Token saved to {FLIGHTLESS_TOKEN_FILE}")

    def _refresh_files(self) -> None:
        self.file_list.setRowCount(0)
        logs = find_logs(game=self._game or None)
        for p in sorted(logs, key=lambda p: p.stat().st_mtime, reverse=True):
            row = self.file_list.rowCount()
            self.file_list.insertRow(row)
            name_item = QTableWidgetItem(p.name)
            name_item.setData(Qt.ItemDataRole.UserRole, p)
            name_item.setCheckState(Qt.CheckState.Unchecked)
            name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            self.file_list.setItem(row, 0, name_item)
            title = _extract_game_name(p.stem)
            title_item = QTableWidgetItem(title)
            title_item.setFlags(title_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.file_list.setItem(row, 1, title_item)

    def _selected_paths(self) -> List[Path]:
        paths = []
        for i in range(self.file_list.rowCount()):
            item = self.file_list.item(i, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                paths.append(item.data(Qt.ItemDataRole.UserRole))
        return paths

    def _bundle(self) -> None:
        from mangohudpy.bundle import cmd_bundle
        args = argparse.Namespace(
            game=self._game or None,
            source=str(BENCH_LOG_DIR),
            output=None,
            limit=None,
        )
        self.bundle_btn.setEnabled(False)
        self.log.clear_log()
        worker = Worker(cmd_bundle, args)
        worker.signals.output.connect(self.log.append_line)
        worker.signals.error.connect(self.log.append_line)
        worker.signals.finished.connect(lambda: self.bundle_btn.setEnabled(True))
        QThreadPool.globalInstance().start(worker)

    def _upload(self) -> None:
        selected = self._selected_paths()
        if not selected:
            self.log.append_line("No files selected.")
            return
        args = argparse.Namespace(
            token=self.token_edit.text().strip() or None,
            append=self.append_check.isChecked(),
            force=self.force_check.isChecked(),
            yes=True,  # clicking Upload Selected IS the confirmation
            game=self._game or None,
            input=[str(p) for p in selected],
            source=str(BENCH_LOG_DIR),
            title=self.title_edit.text().strip() or None,
            description=self.desc_edit.text().strip() or None,
            url=FLIGHTLESS_BASE,
            limit=None,
        )
        self.upload_btn.setEnabled(False)
        self.log.clear_log()
        worker = Worker(cmd_upload, args)
        worker.signals.output.connect(self.log.append_line)
        worker.signals.error.connect(self.log.append_line)
        worker.signals.finished.connect(self._upload_done)
        QThreadPool.globalInstance().start(worker)

    def _upload_done(self) -> None:
        self.upload_btn.setEnabled(True)
