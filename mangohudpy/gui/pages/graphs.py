"""Graphs page: log picker, options, generate button, inline image viewer."""
from __future__ import annotations
from pathlib import Path
from typing import List, Optional

import shutil

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QListWidget, QMessageBox, QPushButton, QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from mangohudpy.constants import CHART_BASE_DIR
from mangohudpy.utils import _extract_game_name, find_logs  # noqa: F401 (find_logs used in _refresh_combo)
from mangohudpy.gui.widgets import ImageViewer, LogViewer
from mangohudpy.gui.worker import Worker


class GraphsPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        outer.addWidget(splitter)

        # ── top pane: controls + image viewer ────────────────────────
        top = QWidget()
        layout = QVBoxLayout(top)
        layout.addWidget(QLabel("<h2>Graphs</h2>"))

        pick_row = QHBoxLayout()
        self.log_combo = QComboBox()
        self.log_combo.currentIndexChanged.connect(self._on_csv_changed)
        pick_row.addWidget(self.log_combo, stretch=1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        pick_row.addWidget(browse_btn)
        layout.addLayout(pick_row)

        opts_row = QHBoxLayout()
        opts_row.addWidget(QLabel("Format:"))
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["png", "svg", "pdf"])
        opts_row.addWidget(self.fmt_combo)
        opts_row.addWidget(QLabel("DPI:"))
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 300)
        self.dpi_spin.setValue(150)
        opts_row.addWidget(self.dpi_spin)
        opts_row.addStretch()
        layout.addLayout(opts_row)

        gen_row = QHBoxLayout()
        self.gen_btn = QPushButton("Generate Graphs")
        self.gen_btn.clicked.connect(self._generate)
        gen_row.addWidget(self.gen_btn)
        self.del_btn = QPushButton("Delete Charts")
        self.del_btn.clicked.connect(self._delete_charts)
        self.del_btn.setEnabled(False)
        gen_row.addWidget(self.del_btn)
        gen_row.addStretch()
        layout.addLayout(gen_row)

        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.image_list = QListWidget()
        self.image_list.currentRowChanged.connect(self._on_image_selected)
        h_splitter.addWidget(self.image_list)
        self.viewer = ImageViewer()
        h_splitter.addWidget(self.viewer)
        h_splitter.setSizes([280, 720])
        h_splitter.setStretchFactor(0, 1)
        h_splitter.setStretchFactor(1, 4)
        layout.addWidget(h_splitter, stretch=1)

        splitter.addWidget(top)

        # ── bottom pane: log output ───────────────────────────────────
        self.log = LogViewer()
        splitter.addWidget(self.log)

        splitter.setSizes([550, 170])
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        self._game = ""
        self._out_dir: Path = CHART_BASE_DIR
        self._image_paths: List[Path] = []
        self._refresh_combo()

    def on_game_selected(self, game: str) -> None:
        self._game = game
        self._refresh_combo()

    def _refresh_combo(self) -> None:
        self.log_combo.clear()
        logs = find_logs(game=self._game or None)
        for p in sorted(logs, key=lambda p: p.stat().st_mtime, reverse=True):
            self.log_combo.addItem(p.name, userData=p)
        # currentIndexChanged fires on first item added; if no items, clear manually
        if not logs:
            self._populate_image_list([])

    def _on_csv_changed(self, _index: int) -> None:
        csv_path: Optional[Path] = self.log_combo.currentData()
        if csv_path is None:
            self._populate_image_list([])
            return
        game = _extract_game_name(csv_path.stem)
        self._out_dir = CHART_BASE_DIR / game / "charts"
        existing = sorted(self._out_dir.glob("*.png")) if self._out_dir.exists() else []
        self._populate_image_list(existing)

    def _populate_image_list(self, paths: List[Path]) -> None:
        self._image_paths = paths
        self.image_list.clear()
        for p in paths:
            self.image_list.addItem(p.name)
        if paths:
            self.image_list.setCurrentRow(0)
        self.del_btn.setEnabled(bool(paths))

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV log", "", "CSV Files (*.csv)"
        )
        if path:
            p = Path(path)
            self.log_combo.insertItem(0, p.name, userData=p)
            self.log_combo.setCurrentIndex(0)

    def _generate(self) -> None:
        csv_path: Optional[Path] = self.log_combo.currentData()
        if csv_path is None or not csv_path.exists():
            self.log.append_line("No valid log selected.")
            return
        game = _extract_game_name(csv_path.stem)
        self._out_dir = CHART_BASE_DIR / game / "charts"
        self._out_dir.mkdir(parents=True, exist_ok=True)

        import argparse
        from mangohudpy.graph import cmd_graph

        args = argparse.Namespace(
            input=str(csv_path),
            output=str(self._out_dir),
            game=game,
            format=self.fmt_combo.currentText(),
            dpi=self.dpi_spin.value(),
            width=14.0,
            height=6.0,
            matplotlib=False,
        )

        self.gen_btn.setEnabled(False)
        self.log.clear_log()
        worker = Worker(cmd_graph, args)
        worker.signals.output.connect(self.log.append_line)
        worker.signals.error.connect(self.log.append_line)
        worker.signals.finished.connect(self._gen_done)
        QThreadPool.globalInstance().start(worker)

    def _gen_done(self) -> None:
        self.gen_btn.setEnabled(True)
        pngs = sorted(self._out_dir.glob("*.png")) if self._out_dir.exists() else []
        self._populate_image_list(pngs)

    def _delete_charts(self) -> None:
        if not self._out_dir.exists():
            return
        reply = QMessageBox.question(
            self, "Delete Charts",
            f"Delete all charts in:\n{self._out_dir}\n\nContinue?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        shutil.rmtree(self._out_dir, ignore_errors=True)
        self._populate_image_list([])
        self.viewer.clear_image()

    def _on_image_selected(self, row: int) -> None:
        if 0 <= row < len(self._image_paths):
            self.viewer.load_image(self._image_paths[row])
