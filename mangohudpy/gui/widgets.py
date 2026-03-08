"""Shared reusable widgets for MangoHudPy GUI."""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame, QLabel, QPlainTextEdit, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)


class StatCard(QFrame):
    """Compact card showing key stats for one game."""

    def __init__(self, game_name: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(180)

        layout = QVBoxLayout(self)
        layout.setSpacing(2)

        title = QLabel(f"<b>{game_name}</b>")
        title.setWordWrap(True)
        layout.addWidget(title)

        self.fps_label = QLabel("Avg FPS: —")
        self.low1_label = QLabel("1% Low: —")
        self.jitter_label = QLabel("Jitter: —")
        self.sessions_label = QLabel("Sessions: —")

        for lbl in (self.fps_label, self.low1_label,
                    self.jitter_label, self.sessions_label):
            layout.addWidget(lbl)

    def set_stats(
        self,
        avg_fps: float,
        low1: float,
        jitter: float,
        sessions: int,
    ) -> None:
        self.fps_label.setText(f"Avg FPS: {avg_fps:.1f}")
        self.low1_label.setText(f"1% Low: {low1:.1f}")
        self.jitter_label.setText(f"Jitter: {jitter:.2f} ms")
        self.sessions_label.setText(f"Sessions: {sessions}")


class LogViewer(QPlainTextEdit):
    """Read-only scrolling log output area."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)

    def append_line(self, text: str) -> None:
        self.appendPlainText(text)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def clear_log(self) -> None:
        self.clear()


class ImageViewer(QScrollArea):
    """Scrollable widget that displays a single image file."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_path: Optional[Path] = None
        self._label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._label.setText("No image loaded.")
        self.setWidget(self._label)
        self.setWidgetResizable(True)

    def clear_image(self) -> None:
        self.current_path = None
        self._label.setPixmap(QPixmap())
        self._label.setText("No image loaded.")

    def load_image(self, path: Path) -> None:
        px = QPixmap(str(path))
        if px.isNull():
            self.current_path = None
            self._label.setText(f"Could not load: {path.name}")
        else:
            self.current_path = path
            self._label.setPixmap(
                px.scaled(
                    self._label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
