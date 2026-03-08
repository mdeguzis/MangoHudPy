"""Dashboard page: per-game StatCards with newest session stats."""
from __future__ import annotations
import argparse
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QGridLayout, QLabel, QPushButton, QScrollArea,
    QSplitter, QVBoxLayout, QWidget,
)

from mangohudpy.constants import BENCH_LOG_DIR, MAX_LOGS_PER_GAME
from mangohudpy.utils import _fcol, discover_games, find_logs, parse_csv, pctl, sf
from mangohudpy.gui.widgets import LogViewer, StatCard
from mangohudpy.gui.worker import Worker


def _build_game_stats(csv_path: Path) -> Dict[str, Any]:
    """Return summary stats dict for a single CSV log."""
    cols, rows = parse_csv(csv_path)
    if not rows:
        return {"avg_fps": 0.0, "low1": 0.0, "jitter": 0.0, "sessions": 1}

    fk = _fcol(cols, ["fps", "FPS"])
    ftk = _fcol(cols, ["frametime", "frametime_ms", "Frametime"])
    fps_vals = sorted([sf(r.get(fk, "0")) for r in rows]) if fk else []
    ft_vals = sorted([sf(r.get(ftk, "0")) for r in rows]) if ftk else []

    avg_fps = sum(fps_vals) / len(fps_vals) if fps_vals else 0.0
    low1 = pctl(fps_vals, 1) if fps_vals else 0.0
    jitter = (pctl(ft_vals, 99) - pctl(ft_vals, 1)) if ft_vals else 0.0

    return {"avg_fps": avg_fps, "low1": low1, "jitter": jitter, "sessions": 1}


class DashboardPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        outer.addWidget(splitter)

        # ── top pane: header + stat cards ────────────────────────────
        top = QWidget()
        layout = QVBoxLayout(top)

        hdr = QWidget()
        hdr_layout = QVBoxLayout(hdr)
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.addWidget(QLabel("<h2>Dashboard</h2>"))
        self.organize_btn = QPushButton("Organize Now")
        self.organize_btn.clicked.connect(self._run_organize)
        hdr_layout.addWidget(self.organize_btn)
        layout.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._cards_widget = QWidget()
        self._cards_layout = QGridLayout(self._cards_widget)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self._cards_widget)
        layout.addWidget(scroll, stretch=1)

        splitter.addWidget(top)

        # ── bottom pane: log output ───────────────────────────────────
        self.log = LogViewer()
        splitter.addWidget(self.log)

        splitter.setSizes([520, 200])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        self._current_game = ""
        self.refresh()

    def on_game_selected(self, game: str) -> None:
        self._current_game = game
        self.refresh()

    def refresh(self) -> None:
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        games = [self._current_game] if self._current_game else discover_games()
        col_count = 3
        added = 0
        for game in games:
            logs = find_logs(game=game)
            if not logs:
                continue
            newest = max(logs, key=lambda p: p.stat().st_mtime)
            stats = _build_game_stats(newest)
            stats["sessions"] = len(logs)
            card = StatCard(game)
            card.set_stats(**stats)
            self._cards_layout.addWidget(card, added // col_count, added % col_count)
            added += 1

        if added == 0:
            self._cards_layout.addWidget(
                QLabel("No games found. Play a game with MangoHud, then click Organize Now."),
                0, 0,
            )

    def _run_organize(self) -> None:
        from mangohudpy.organize import cmd_organize
        args = argparse.Namespace(
            source=None,
            dest=str(BENCH_LOG_DIR),
            max_logs=MAX_LOGS_PER_GAME,
            dry_run=False,
        )
        self.organize_btn.setEnabled(False)
        self.log.clear_log()
        worker = Worker(cmd_organize, args)
        worker.signals.output.connect(self.log.append_line)
        worker.signals.error.connect(self.log.append_line)
        worker.signals.finished.connect(self._organize_done)
        QThreadPool.globalInstance().start(worker)

    def _organize_done(self) -> None:
        self.organize_btn.setEnabled(True)
        self.refresh()
