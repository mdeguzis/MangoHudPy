"""Config page: preset picker, key-value editor, write MangoHud.conf."""
from __future__ import annotations
import argparse
from typing import List, Optional, Tuple

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from mangohudpy.constants import CONFIG_PRESETS, MANGOHUD_CONF_FILE
from mangohudpy.config import cmd_configure


def _preset_rows(preset_name: str) -> List[Tuple[str, str]]:
    """Return sorted (key, value) pairs for a preset."""
    vals = CONFIG_PRESETS[preset_name]["values"]
    return [(k, str(v)) for k, v in sorted(vals.items())]


class ConfigPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Configure MangoHud</h2>"))

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(CONFIG_PRESETS.keys()))
        self.preset_combo.currentTextChanged.connect(self._load_preset)
        preset_row.addWidget(self.preset_combo)
        self.desc_label = QLabel("")
        preset_row.addWidget(self.desc_label, stretch=1)
        layout.addLayout(preset_row)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Output:"))
        self.out_edit = QLineEdit(str(MANGOHUD_CONF_FILE))
        out_row.addWidget(self.out_edit, stretch=1)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_output)
        out_row.addWidget(browse_btn)
        layout.addLayout(out_row)

        game_row = QHBoxLayout()
        game_row.addWidget(QLabel("Per-game name (optional):"))
        self.game_edit = QLineEdit()
        self.game_edit.setPlaceholderText("e.g. Cyberpunk2077")
        game_row.addWidget(self.game_edit, stretch=1)
        layout.addLayout(game_row)

        self.force_check = QCheckBox("Overwrite existing config")
        layout.addWidget(self.force_check)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Key", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, stretch=1)

        self.write_btn = QPushButton("Write Config")
        self.write_btn.clicked.connect(self._write)
        layout.addWidget(self.write_btn)

        self._load_preset(self.preset_combo.currentText())

    def on_game_selected(self, game: str) -> None:
        if game:
            self.game_edit.setText(game)

    def _load_preset(self, name: str) -> None:
        self.desc_label.setText(CONFIG_PRESETS[name]["description"])
        rows = _preset_rows(name)
        self.table.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(k))
            self.table.setItem(i, 1, QTableWidgetItem(v))

    def _browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save config to", self.out_edit.text(), "Conf Files (*.conf)"
        )
        if path:
            self.out_edit.setText(path)

    def _collect_overrides(self) -> List[str]:
        overrides = []
        for row in range(self.table.rowCount()):
            k_item = self.table.item(row, 0)
            v_item = self.table.item(row, 1)
            if k_item and v_item:
                overrides.append(f"{k_item.text()}={v_item.text()}")
        return overrides

    def _write(self) -> None:
        reply = QMessageBox.question(
            self, "Write Config",
            f"Write MangoHud config to:\n{self.out_edit.text()}\n\nContinue?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        args = argparse.Namespace(
            preset=self.preset_combo.currentText(),
            output=self.out_edit.text(),
            set=self._collect_overrides(),
            log_dir=None,
            game=self.game_edit.text().strip() or None,
            check=False,
            force=self.force_check.isChecked(),
        )
        ret = cmd_configure(args)
        if ret == 0:
            QMessageBox.information(self, "Done", "Config written successfully.")
        else:
            QMessageBox.warning(self, "Error", "Config write failed.")
