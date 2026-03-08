"""Summary page: log picker + stats table."""
from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)
from PySide6.QtWidgets import QHeaderView

from mangohudpy.utils import _fcol, find_logs, parse_csv, pctl, sf  # noqa: F401 (sf used in _build_summary_rows)

_METRICS = [
    (["fps", "FPS"],                               "FPS",        "fps"),
    (["frametime", "frametime_ms", "Frametime"],   "Frame Time", "ms"),
    (["cpu_temp", "CPU_Temp"],                     "CPU Temp",   "C"),
    (["gpu_temp", "GPU_Temp"],                     "GPU Temp",   "C"),
    (["cpu_power", "CPU_Power"],                   "CPU Power",  "W"),
    (["gpu_power", "GPU_Power"],                   "GPU Power",  "W"),
    (["ram", "RAM"],                               "RAM",        "MB"),
    (["vram", "VRAM"],                             "VRAM",       "MB"),
]
_COLS = ["Metric", "Avg", "Min", "Max", "1%", "5%", "95%", "99%", "Unit"]


def _build_summary_rows(path: Path) -> List[Tuple]:
    cols, rows = parse_csv(path)
    result = []
    for cands, label, unit in _METRICS:
        k = _fcol(cols, cands)
        if not k:
            continue
        vs = sorted([sf(r.get(k, "0")) for r in rows])
        if not vs or max(vs) == 0:
            continue
        avg = sum(vs) / len(vs)
        result.append((
            label,
            f"{avg:.1f}", f"{vs[0]:.1f}", f"{vs[-1]:.1f}",
            f"{pctl(vs, 1):.1f}", f"{pctl(vs, 5):.1f}",
            f"{pctl(vs, 95):.1f}", f"{pctl(vs, 99):.1f}",
            unit,
        ))
    return result


class SummaryPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Summary</h2>"))

        pick_row = QHBoxLayout()
        self.log_combo = QComboBox()
        self.log_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        pick_row.addWidget(self.log_combo, stretch=1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        pick_row.addWidget(browse_btn)
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self._load)
        pick_row.addWidget(load_btn)
        layout.addLayout(pick_row)

        self.table = QTableWidget(0, len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, stretch=1)

        self.stability_label = QLabel("")
        self.jitter_label = QLabel("")
        layout.addWidget(self.stability_label)
        layout.addWidget(self.jitter_label)

        self.info_label = QLabel("")
        layout.addWidget(self.info_label)

        self._game = ""
        self._refresh_combo()

    def on_game_selected(self, game: str) -> None:
        self._game = game
        self._refresh_combo()

    def _refresh_combo(self) -> None:
        self.log_combo.clear()
        logs = find_logs(game=self._game or None)
        for p in sorted(logs, key=lambda p: p.stat().st_mtime, reverse=True):
            self.log_combo.addItem(p.name, userData=p)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV log", "", "CSV Files (*.csv)"
        )
        if path:
            p = Path(path)
            self.log_combo.insertItem(0, p.name, userData=p)
            self.log_combo.setCurrentIndex(0)

    def _load(self) -> None:
        path: Optional[Path] = self.log_combo.currentData()
        if path is None or not path.exists():
            self.info_label.setText("No valid log selected.")
            return
        cols, rows = parse_csv(path)
        data = _build_summary_rows(path)
        self.table.setRowCount(len(data))
        for row_i, row_data in enumerate(data):
            for col_i, val in enumerate(row_data):
                self.table.setItem(row_i, col_i, QTableWidgetItem(str(val)))

        # FPS Stability and Frametime Jitter
        fk = _fcol(cols, ["fps", "FPS"])
        ftk = _fcol(cols, ["frametime", "frametime_ms", "Frametime"])
        if fk and rows:
            fv = [sf(r.get(fk, "0")) for r in rows]
            avg = sum(fv) / len(fv)
            if avg > 0:
                stab = (1 - (sum((v - avg) ** 2 for v in fv) / len(fv)) ** 0.5 / avg) * 100
                self.stability_label.setText(f"FPS Stability: {max(0.0, stab):.1f}%  (100% = perfectly stable)")
            else:
                self.stability_label.setText("")
        else:
            self.stability_label.setText("")

        if ftk and rows:
            tv = sorted([sf(r.get(ftk, "0")) for r in rows])
            jitter = pctl(tv, 99) - pctl(tv, 1)
            self.jitter_label.setText(f"Frametime Jitter (P99−P1): {jitter:.2f} ms")
        else:
            self.jitter_label.setText("")

        self.info_label.setText(f"Loaded: {path.name}")
