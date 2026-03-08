"""Graphs page: FlightlessSomething-style tabbed inline charts."""
from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QSizePolicy,
    QSplitter, QTabWidget, QVBoxLayout, QWidget,
)

from mangohudpy.gui.widgets import LogViewer
from mangohudpy.utils import _extract_game_name, _fcol, find_logs, parse_csv, pctl, sf

_RUN_COLORS = [
    "#7cb5ec", "#f7a35c", "#90ed7d", "#f15c80",
    "#e4d354", "#8085e9", "#2b908f", "#f45b5b",
]
_BG   = "#212529"
_TEXT = "#e0e0e0"
_GRID = "#3a3a3a"


# ── matplotlib helpers ─────────────────────────────────────────────────

def _mpl_available() -> bool:
    try:
        import matplotlib  # noqa: F401
        return True
    except ImportError:
        return False


def _style_ax(ax, fig, title: str, xlabel: str = "", ylabel: str = "") -> None:
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)
    ax.set_title(title, color=_TEXT, fontsize=11, fontweight="bold", pad=6)
    ax.set_xlabel(xlabel, color=_TEXT, fontsize=9)
    ax.set_ylabel(ylabel, color=_TEXT, fontsize=9)
    ax.tick_params(colors=_TEXT, labelsize=8)
    ax.grid(True, color=_GRID, linewidth=0.5)
    for spine in ax.spines.values():
        spine.set_color(_GRID)


class _MplCanvas:
    """Wraps a matplotlib Figure + FigureCanvasQTAgg + NavigationToolbar."""

    def __init__(self, fig_w: float = 8.0, fig_h: float = 3.5, dpi: int = 96):
        from matplotlib.backends.backend_qtagg import (
            FigureCanvasQTAgg, NavigationToolbar2QT,
        )
        from matplotlib.figure import Figure

        self.fig = Figure(figsize=(fig_w, fig_h), dpi=dpi,
                          facecolor=_BG, tight_layout=True)

        # Subclass inline so wheel events propagate to the scroll area
        class _Canvas(FigureCanvasQTAgg):
            def wheelEvent(self_, event):
                event.ignore()

        self.canvas = _Canvas(self.fig)
        self.canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.canvas.setMinimumHeight(int(fig_h * dpi))

        self.toolbar = NavigationToolbar2QT(self.canvas, None)
        self.toolbar.setStyleSheet(
            "QToolBar { background: #2d2d2d; border: none; spacing: 2px; }"
            "QToolButton { color: #e0e0e0; background: transparent; }"
            "QToolButton:hover { background: #3a3a3a; }"
        )

    def widget(self) -> QWidget:
        """Return a QWidget containing toolbar + canvas."""
        w = QWidget()
        w.setStyleSheet("background: #212529;")
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(self.toolbar)
        vbox.addWidget(self.canvas)
        return w

    def draw(self):
        self.canvas.draw_idle()


# ── scroll area that always handles wheel events ───────────────────────

class _WheelScrollArea(QScrollArea):
    def wheelEvent(self, event):
        dy = event.angleDelta().y()
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().value() - dy // 3
        )
        event.accept()


def _scrollable(widget: QWidget) -> _WheelScrollArea:
    sa = _WheelScrollArea()
    sa.setWidget(widget)
    sa.setWidgetResizable(True)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sa.setStyleSheet("QScrollArea { border: none; background: #212529; }")
    return sa


# ── run data ───────────────────────────────────────────────────────────

class _RunData:
    def __init__(self, path: Path):
        self.path  = path
        self.label = path.stem
        cols, rows = parse_csv(path)
        self.rows  = rows

        def _v(cands):
            k = _fcol(cols, cands)
            return [sf(r.get(k, "0")) for r in rows] if k else []

        self.fps       = _v(["fps", "FPS"])
        self.frametime = _v(["frametime", "frametime_ms", "Frametime"])
        self.cpu_temp  = _v(["cpu_temp",  "CPU_Temp"])
        self.gpu_temp  = _v(["gpu_temp",  "GPU_Temp"])
        self.cpu_power = _v(["cpu_power", "CPU_Power"])
        self.gpu_power = _v(["gpu_power", "GPU_Power"])
        self.ram       = _v(["ram",  "RAM"])
        self.vram      = _v(["vram", "VRAM"])

    def fps_stats(self) -> Optional[Tuple[float, float, float]]:
        if not self.fps:
            return None
        s = sorted(self.fps)
        return pctl(s, 1), sum(s) / len(s), pctl(s, 97)

    def fps_density(self):
        try:
            import numpy as np
        except ImportError:
            return [], []
        if not self.fps:
            return [], []
        arr = np.array(self.fps)
        counts, edges = np.histogram(arr, bins=60)
        return list((edges[:-1] + edges[1:]) / 2), list(counts.astype(float))


# ── GraphsPage ─────────────────────────────────────────────────────────

class GraphsPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        outer.addWidget(splitter)

        # ── top: controls + tabs ──────────────────────────────────────
        top = QWidget()
        layout = QVBoxLayout(top)
        layout.setContentsMargins(8, 8, 8, 4)
        layout.addWidget(QLabel("<h2>Graphs</h2>"))

        # CSV picker row
        pick_row = QHBoxLayout()
        self.log_combo = QComboBox()
        self.log_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.log_combo.currentIndexChanged.connect(self._load_selected)
        pick_row.addWidget(self.log_combo, stretch=1)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        pick_row.addWidget(browse_btn)
        add_btn = QPushButton("Add Run")
        add_btn.setToolTip("Overlay another CSV on all charts")
        add_btn.clicked.connect(self._add_run)
        pick_row.addWidget(add_btn)
        layout.addLayout(pick_row)

        # Loaded runs list with per-run remove
        runs_row = QHBoxLayout()
        self._runs_list = QListWidget()
        self._runs_list.setMaximumHeight(64)
        self._runs_list.setToolTip("Select a run then click Remove to delete it")
        runs_row.addWidget(self._runs_list, stretch=1)
        remove_btn = QPushButton("Delete File")
        remove_btn.clicked.connect(self._remove_selected)
        runs_row.addWidget(remove_btn)
        layout.addLayout(runs_row)

        if not _mpl_available():
            layout.addWidget(QLabel(
                "matplotlib not installed. Run: pip install matplotlib"
            ))
            splitter.addWidget(top)
            self.log = LogViewer()
            splitter.addWidget(self.log)
            self._runs: List[_RunData] = []
            return

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #3a3a3a; background: #212529; }"
            "QTabBar::tab { background: #2d2d2d; color: #e0e0e0; padding: 4px 12px; }"
            "QTabBar::tab:selected { background: #7cb5ec; color: #000; }"
        )
        layout.addWidget(self.tabs, stretch=1)
        self._build_tabs()

        splitter.addWidget(top)

        # ── bottom: log ───────────────────────────────────────────────
        self.log = LogViewer()
        splitter.addWidget(self.log)
        splitter.setSizes([600, 120])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        self._game = ""
        self._runs: List[_RunData] = []
        self._refresh_combo()

    # ── tab construction ──────────────────────────────────────────────

    def _build_tabs(self) -> None:
        self.tabs.clear()

        # FPS tab — 3 stacked canvases
        self._cv_fps_line    = _MplCanvas(8, 3.2)
        self._cv_fps_bar     = _MplCanvas(8, 1.8)
        self._cv_fps_density = _MplCanvas(8, 2.2)
        fps_container = QWidget()
        fps_container.setStyleSheet("background: #212529;")
        fps_vbox = QVBoxLayout(fps_container)
        fps_vbox.setSpacing(6)
        fps_vbox.setContentsMargins(4, 4, 4, 4)
        for cv in (self._cv_fps_line, self._cv_fps_bar, self._cv_fps_density):
            fps_vbox.addWidget(cv.widget())
        fps_vbox.addStretch()
        self.tabs.addTab(_scrollable(fps_container), "FPS")

        # Simple metric tabs
        self._simple_tabs: dict = {}
        for name, label, unit in [
            ("frametime", "Frametime",  "ms"),
            ("cpu_temp",  "CPU Temp",   "°C"),
            ("gpu_temp",  "GPU Temp",   "°C"),
            ("cpu_power", "CPU Power",  "W"),
            ("gpu_power", "GPU Power",  "W"),
            ("ram",       "RAM",        "MB"),
            ("vram",      "VRAM",       "MB"),
        ]:
            cv = _MplCanvas(8, 3.5)
            container = QWidget()
            container.setStyleSheet("background: #212529;")
            vbox = QVBoxLayout(container)
            vbox.setContentsMargins(4, 4, 4, 4)
            vbox.addWidget(cv.widget())
            vbox.addStretch()
            self._simple_tabs[name] = (cv, label, unit)
            self.tabs.addTab(_scrollable(container), label)

    # ── game/combo ────────────────────────────────────────────────────

    def on_game_selected(self, game: str) -> None:
        self._game = game
        self._refresh_combo()

    def _refresh_combo(self) -> None:
        from mangohudpy.constants import BENCH_LOG_DIR
        self.log_combo.blockSignals(True)
        self.log_combo.clear()

        # Always scan organized folders for current symlinks.
        # Filter to selected game if one is active; otherwise show all.
        current_resolved: set = set()
        if BENCH_LOG_DIR.is_dir():
            game_filter = self._game.lower() if self._game else None
            candidates = []
            for game_dir in BENCH_LOG_DIR.iterdir():
                if not game_dir.is_dir():
                    continue
                symlink = game_dir / f"{game_dir.name}-current-mangohud.csv"
                if not symlink.is_symlink() or not symlink.exists():
                    continue
                resolved = symlink.resolve()
                if game_filter and not resolved.stem.lower().startswith(game_filter):
                    continue
                candidates.append((symlink.stat().st_mtime, symlink.name, resolved))
            for _, sym_name, resolved in sorted(candidates, key=lambda x: x[0], reverse=True):
                self.log_combo.addItem(sym_name, userData=resolved)
                current_resolved.add(resolved)

        logs = find_logs(game=self._game or None)
        for p in sorted(logs, key=lambda p: p.stat().st_mtime, reverse=True):
            if p.resolve() in current_resolved:
                continue  # already listed via symlink
            self.log_combo.addItem(p.name, userData=p)

        self.log_combo.blockSignals(False)
        if self.log_combo.count() > 0:
            self.log_combo.setCurrentIndex(0)
            self._load_selected()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV", "", "CSV Files (*.csv)"
        )
        if path:
            p = Path(path)
            self.log_combo.insertItem(0, p.name, userData=p)
            self.log_combo.setCurrentIndex(0)

    # ── loading ───────────────────────────────────────────────────────

    def _load_selected(self) -> None:
        csv_path: Optional[Path] = self.log_combo.currentData()
        if csv_path is None or not csv_path.exists():
            self.log.append_line("No valid log selected.")
            return
        self._runs.clear()
        self._runs_list.clear()
        self._do_load(csv_path)

    def _add_run(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Add CSV run", "", "CSV Files (*.csv)"
        )
        if path:
            self._do_load(Path(path))

    def _do_load(self, path: Path) -> None:
        try:
            run = _RunData(path)
            self._runs.append(run)
            item = QListWidgetItem(run.label)
            item.setForeground(
                QColor(_RUN_COLORS[(len(self._runs) - 1) % len(_RUN_COLORS)])
            )
            self._runs_list.addItem(item)
            self.log.append_line(
                f"Loaded: {path.name}  ({len(run.rows)} samples)"
            )
            self._render_all()
        except Exception as exc:
            self.log.append_line(f"Error: {exc}")

    def _remove_selected(self) -> None:
        row = self._runs_list.currentRow()
        if row < 0 or row >= len(self._runs):
            return
        run = self._runs[row]
        reply = QMessageBox.question(
            self, "Delete File",
            f"Permanently delete {run.path.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        deleted_path = run.path
        try:
            deleted_path.unlink()
            self.log.append_line(f"Deleted: {deleted_path.name}")
        except OSError as exc:
            self.log.append_line(f"Error deleting {deleted_path.name}: {exc}")
            return
        self._fix_current_symlink(deleted_path)
        self._runs.pop(row)
        self._runs_list.takeItem(row)
        for i in range(self._runs_list.count()):
            self._runs_list.item(i).setForeground(
                QColor(_RUN_COLORS[i % len(_RUN_COLORS)])
            )
        # Block signals so _refresh_combo doesn't trigger spurious _load_selected calls
        self.log_combo.blockSignals(True)
        self._refresh_combo()
        self.log_combo.blockSignals(False)
        if not self._runs and self.log_combo.count() > 0:
            # Auto-select the next available file in the combo
            self.log_combo.setCurrentIndex(0)
            self._load_selected()
        else:
            self._render_all()

    def _fix_current_symlink(self, deleted_path: Path) -> None:
        """Relink the game's current-run symlink if it now points to the deleted file.

        Organized game folders contain a ``{game}-current-mangohud.csv`` symlink
        that tracks the newest log.  Deleting the target leaves a broken link;
        this method repoints it at the next-newest real CSV (or removes it if
        none remain).
        """
        parent = deleted_path.parent
        symlink = parent / f"{parent.name}-current-mangohud.csv"
        # is_symlink() is True even for broken links; exists() is False when broken
        if not symlink.is_symlink() or symlink.exists():
            return
        csvs = sorted(
            [p for p in parent.glob("*.csv")
             if not p.name.endswith("-current-mangohud.csv")
             and not p.name.endswith("_summary.csv")
             and p.name != "current.csv"
             and not p.is_symlink()],
            key=lambda p: p.stat().st_mtime,
        )
        symlink.unlink()
        if csvs:
            symlink.symlink_to(csvs[-1].name)
            self.log.append_line(f"Relinked: {symlink.name} -> {csvs[-1].name}")
        else:
            self.log.append_line(f"Removed stale symlink: {symlink.name} (no logs remain)")

    # ── rendering ─────────────────────────────────────────────────────

    def _render_all(self) -> None:
        if not _mpl_available():
            return
        self._render_fps()
        for key, (cv, title, unit) in self._simple_tabs.items():
            series = [(r.label, getattr(r, key)) for r in self._runs]
            self._render_line(cv, series, f"{title} over Time", "Sample", unit)
            # Show/hide tab based on whether any run has this metric
            idx = list(self._simple_tabs.keys()).index(key) + 1
            has = any(getattr(r, key) for r in self._runs)
            self.tabs.setTabVisible(idx, has or not self._runs)

    def _render_fps(self) -> None:
        # ── FPS line ──────────────────────────────────────────────────
        fig = self._cv_fps_line.fig
        fig.clear()
        ax = fig.add_subplot(111)
        _style_ax(ax, fig, "FPS over Time", "Sample", "FPS")
        for i, run in enumerate(self._runs):
            if not run.fps:
                continue
            c = _RUN_COLORS[i % len(_RUN_COLORS)]
            x = list(range(len(run.fps)))
            ax.plot(x, run.fps, color=c, lw=1.0)
            ax.fill_between(x, run.fps, alpha=0.15, color=c)
        if self._runs:
            _bottom_legend(ax, self._runs, _RUN_COLORS)
        self._cv_fps_line.draw()

        # ── Min/Avg/Max bar ───────────────────────────────────────────
        fig2 = self._cv_fps_bar.fig
        fig2.clear()
        ax2 = fig2.add_subplot(111)
        _style_ax(ax2, fig2, "Min / Avg / Max FPS  (More is better)", "FPS", "")
        bar_h = 0.22
        for i, run in enumerate(self._runs):
            stats = run.fps_stats()
            if not stats:
                continue
            p1, avg, p97 = stats
            y = i * (bar_h * 3 + 0.12)
            ax2.barh(y,           p97, height=bar_h, color="#2ecc71")
            ax2.barh(y + bar_h,   avg, height=bar_h, color="#3498db")
            ax2.barh(y + bar_h*2, p1,  height=bar_h, color="#e74c3c")
            for val, offset in [(p97, y), (avg, y+bar_h), (p1, y+bar_h*2)]:
                ax2.text(val + max(p97*0.01, 0.5), offset + bar_h/2,
                         f"{val:.1f}", va="center", color=_TEXT, fontsize=8)
        ax2.set_yticks([])
        if self._runs:
            # Colour-coded run labels below, stat legend
            _bottom_legend(ax2, self._runs, _RUN_COLORS)
            from matplotlib.patches import Patch
            stat_handles = [
                Patch(color="#2ecc71", label="97th"),
                Patch(color="#3498db", label="Avg"),
                Patch(color="#e74c3c", label="1%"),
            ]
            ax2.legend(handles=stat_handles, loc="lower right",
                       facecolor=_BG, edgecolor=_GRID, labelcolor=_TEXT, fontsize=8)
        self._cv_fps_bar.draw()

        # ── FPS density ───────────────────────────────────────────────
        fig3 = self._cv_fps_density.fig
        fig3.clear()
        ax3 = fig3.add_subplot(111)
        _style_ax(ax3, fig3, "FPS Density", "FPS", "Count")
        for i, run in enumerate(self._runs):
            centres, counts = run.fps_density()
            if not centres:
                continue
            c = _RUN_COLORS[i % len(_RUN_COLORS)]
            ax3.plot(centres, counts, color=c, lw=1.2)
            ax3.fill_between(centres, counts, alpha=0.3, color=c)
        if self._runs:
            _bottom_legend(ax3, self._runs, _RUN_COLORS)
        self._cv_fps_density.draw()

    def _render_line(self, cv: _MplCanvas, series, title, xlabel, ylabel) -> None:
        fig = cv.fig
        fig.clear()
        ax = fig.add_subplot(111)
        _style_ax(ax, fig, title, xlabel, ylabel)
        has = False
        for i, (label, vals) in enumerate(series):
            if not vals or not any(v > 0 for v in vals):
                continue
            c = _RUN_COLORS[i % len(_RUN_COLORS)]
            x = list(range(len(vals)))
            ax.plot(x, vals, color=c, lw=1.0)
            ax.fill_between(x, vals, alpha=0.15, color=c)
            has = True
        if has:
            _bottom_legend(ax, self._runs, _RUN_COLORS)
        cv.draw()


# ── legend helper — always below the axes ─────────────────────────────

def _bottom_legend(ax, runs: list, colors: list) -> None:
    """Add a colour-coded legend below the axes, one entry per run."""
    from matplotlib.lines import Line2D
    handles = [
        Line2D([0], [0], color=colors[i % len(colors)], lw=2, label=r.label)
        for i, r in enumerate(runs)
    ]
    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
        ncol=max(1, min(4, len(runs))),
        facecolor=_BG,
        edgecolor=_GRID,
        labelcolor=_TEXT,
        fontsize=8,
        framealpha=0.8,
    )
