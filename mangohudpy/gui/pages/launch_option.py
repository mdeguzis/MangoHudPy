"""Launch-option page: table of Steam games with MangoHud toggle + apply."""
from __future__ import annotations
from typing import Dict, Optional

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from mangohudpy.constants import MANGOHUD_LOG_DIR
from mangohudpy.gui.widgets import LogViewer
from mangohudpy.gui.worker import Worker


class LaunchOptionPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        outer.addWidget(splitter)

        # ── top pane: controls + table ────────────────────────────────
        top = QWidget()
        layout = QVBoxLayout(top)
        layout.addWidget(QLabel("<h2>Steam Launch Options</h2>"))

        self._cef_label = QLabel("")
        layout.addWidget(self._cef_label)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("type to search games…")
        self.filter_edit.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.filter_edit, stretch=1)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_games)
        filter_row.addWidget(refresh_btn)
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["MangoHud", "Game", "Launch Options"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.keyPressEvent = self._table_key_press
        layout.addWidget(self.table, stretch=1)

        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton("Apply Changes")
        self.apply_btn.clicked.connect(self._apply_changes)
        self.apply_btn.setEnabled(False)
        btn_row.addWidget(self.apply_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        splitter.addWidget(top)

        # ── bottom pane: log output ───────────────────────────────────
        self.log = LogViewer()
        splitter.addWidget(self.log)

        splitter.setSizes([500, 200])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        # Internal state: app_id -> (original_opt, pending_opt)
        self._original: Dict[str, str] = {}
        self._pending: Dict[str, str] = {}
        self._app_names: Dict[str, str] = {}  # app_id -> name
        self._row_app_ids: list = []           # row index -> app_id

        self._load_games()

    def on_game_selected(self, game: str) -> None:
        if game:
            self.filter_edit.setText(game)

    # ── data loading ──────────────────────────────────────────────────

    def _load_games(self) -> None:
        from mangohudpy.launch import (
            _cef_available, _get_launch_option, _has_mangohud,
            _localconfig_path, _load_localconfig, _is_game_mode,
        )
        from mangohudpy.utils import load_steam_app_names

        self.log.clear_log()
        self.table.setRowCount(0)
        self._original.clear()
        self._pending.clear()
        self._row_app_ids.clear()

        cfg_path = _localconfig_path()
        if not cfg_path or not cfg_path.exists():
            self.log.append_line("Steam localconfig.vdf not found. Is Steam installed?")
            self._cef_label.setText("Steam not found")
            return

        app_names = load_steam_app_names()
        if not app_names:
            self.log.append_line("No Steam games found in steamapps/*.acf")
            return

        vdf_data = _load_localconfig(cfg_path)
        self._app_names = app_names

        use_cef = _cef_available()
        game_mode = _is_game_mode()
        method = "live via Steam CEF" if use_cef else "localconfig.vdf (restart Steam after apply)"
        mode = "Game Mode" if game_mode else "Desktop Mode"
        self._cef_label.setText(f"{mode}  ·  Apply method: {method}")
        self._use_cef = use_cef
        self._vdf_data = vdf_data
        self._cfg_path = cfg_path

        games = sorted(app_names.items(), key=lambda x: x[1].lower())
        self.table.setRowCount(len(games))
        for row, (app_id, name) in enumerate(games):
            opt = _get_launch_option(vdf_data, app_id)
            self._original[app_id] = opt
            self._pending[app_id] = opt
            self._row_app_ids.append(app_id)
            self._set_row(row, app_id, name, opt)

        self.log.append_line(f"Loaded {len(games)} games from {cfg_path}")
        self._apply_filter(self.filter_edit.text())

    def _set_row(self, row: int, app_id: str, name: str, opt: str) -> None:
        from mangohudpy.launch import _has_mangohud

        enabled = _has_mangohud(opt)
        changed = opt != self._original.get(app_id, opt)

        chk = QTableWidgetItem()
        chk.setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
        chk.setFlags(chk.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        chk.setData(Qt.ItemDataRole.UserRole, app_id)
        if changed:
            chk.setForeground(Qt.GlobalColor.yellow)
        self.table.setItem(row, 0, chk)

        name_item = QTableWidgetItem(name)
        if changed:
            name_item.setForeground(Qt.GlobalColor.yellow)
        self.table.setItem(row, 1, name_item)

        opt_item = QTableWidgetItem(opt)
        self.table.setItem(row, 2, opt_item)

    def _apply_filter(self, text: str) -> None:
        fl = text.lower()
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 1)
            hidden = bool(fl) and name_item is not None and fl not in name_item.text().lower()
            self.table.setRowHidden(row, hidden)

    # ── toggle ────────────────────────────────────────────────────────

    def _toggle_row(self, row: int) -> None:
        from mangohudpy.launch import (
            _add_mangohud, _has_mangohud, _mangohud_prefix, _remove_mangohud,
        )

        chk = self.table.item(row, 0)
        if chk is None:
            return
        app_id = chk.data(Qt.ItemDataRole.UserRole)
        if app_id is None:
            return

        cur = self._pending[app_id]
        prefix = _mangohud_prefix(MANGOHUD_LOG_DIR)
        if _has_mangohud(cur):
            self._pending[app_id] = _remove_mangohud(cur)
        else:
            self._pending[app_id] = _add_mangohud(cur, prefix)

        name = self.table.item(row, 1).text() if self.table.item(row, 1) else app_id
        self._set_row(row, app_id, name, self._pending[app_id])
        self._update_apply_btn()

    def _table_key_press(self, event) -> None:
        if event.key() == Qt.Key.Key_Space:
            rows = {idx.row() for idx in self.table.selectedIndexes()}
            for row in rows:
                self._toggle_row(row)
        else:
            QTableWidget.keyPressEvent(self.table, event)

    def _update_apply_btn(self) -> None:
        has_changes = any(
            v != self._original.get(k, v)
            for k, v in self._pending.items()
        )
        self.apply_btn.setEnabled(has_changes)

    # ── apply ─────────────────────────────────────────────────────────

    def _apply_changes(self) -> None:
        changes = {
            aid: val
            for aid, val in self._pending.items()
            if val != self._original.get(aid, "")
        }
        if not changes:
            self.log.append_line("No changes to apply.")
            return

        self.apply_btn.setEnabled(False)
        self.log.clear_log()
        worker = Worker(self._do_apply, changes)
        worker.signals.output.connect(self.log.append_line)
        worker.signals.error.connect(self.log.append_line)
        worker.signals.finished.connect(self._apply_done)
        QThreadPool.globalInstance().start(worker)

    def _do_apply(self, changes: Dict[str, str]) -> None:
        from mangohudpy.launch import (
            _cef_set_launch_option, _has_mangohud,
            _save_localconfig, _set_launch_option_vdf,
        )

        failed = []
        for app_id, new_opt in changes.items():
            name = self._app_names.get(app_id, app_id)
            status = "[ON ]" if _has_mangohud(new_opt) else "[OFF]"

            if self._use_cef:
                ok = _cef_set_launch_option(app_id, new_opt)
                if ok:
                    print(f"  {status}  {name}  (live)")
                else:
                    failed.append((app_id, new_opt))
                    print(f"  {status}  {name}  (CEF failed, falling back to VDF)")
                    _set_launch_option_vdf(self._vdf_data, app_id, new_opt)
            else:
                _set_launch_option_vdf(self._vdf_data, app_id, new_opt)
                print(f"  {status}  {name}")

            if new_opt:
                print(f"         {new_opt}")

        if not self._use_cef or failed:
            _save_localconfig(self._vdf_data, self._cfg_path)
            print(f"\n  Saved: {self._cfg_path}")
            if not self._use_cef:
                print("  Restart Steam for changes to take effect.")
        else:
            print("\n  Applied live — no Steam restart needed.")

    def _apply_done(self) -> None:
        # Promote pending -> original so the yellow highlight clears
        for app_id in self._pending:
            self._original[app_id] = self._pending[app_id]
        for row, app_id in enumerate(self._row_app_ids):
            name_item = self.table.item(row, 1)
            name = name_item.text() if name_item else app_id
            self._set_row(row, app_id, name, self._pending[app_id])
        self.apply_btn.setEnabled(False)
