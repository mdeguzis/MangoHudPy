"""Tests for shared widgets — uses offscreen Qt platform."""
import os
import sys
import pytest

# Force offscreen rendering so tests work without a display server
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_stat_card_initial_labels(qapp):
    """StatCard shows placeholder dashes initially."""
    from mangohudpy.gui.widgets import StatCard
    card = StatCard("Test Game")
    assert "—" in card.fps_label.text()
    assert "—" in card.low1_label.text()
    assert "—" in card.jitter_label.text()
    assert "—" in card.sessions_label.text()


def test_stat_card_set_stats(qapp):
    """StatCard.set_stats() updates all labels correctly."""
    from mangohudpy.gui.widgets import StatCard
    card = StatCard("Cyberpunk 2077")
    card.set_stats(avg_fps=89.3, low1=72.1, jitter=2.45, sessions=5)
    assert "89.3" in card.fps_label.text()
    assert "72.1" in card.low1_label.text()
    assert "2.45" in card.jitter_label.text()
    assert "5" in card.sessions_label.text()


def test_log_viewer_append(qapp):
    """LogViewer.append_line() adds text to the widget."""
    from mangohudpy.gui.widgets import LogViewer
    v = LogViewer()
    v.append_line("Organize complete: /home/user/mangologs")
    assert "Organize complete" in v.toPlainText()


def test_log_viewer_clear(qapp):
    """LogViewer.clear_log() empties the widget."""
    from mangohudpy.gui.widgets import LogViewer
    v = LogViewer()
    v.append_line("some text")
    v.clear_log()
    assert v.toPlainText() == ""


def test_log_viewer_is_readonly(qapp):
    """LogViewer is read-only."""
    from mangohudpy.gui.widgets import LogViewer
    v = LogViewer()
    assert v.isReadOnly()


def test_image_viewer_initial_state(qapp):
    """ImageViewer starts with no image loaded."""
    from mangohudpy.gui.widgets import ImageViewer
    v = ImageViewer()
    assert v.current_path is None
    assert "No image" in v._label.text()


def test_image_viewer_load_missing(qapp, tmp_path):
    """ImageViewer.load_image() handles missing file gracefully."""
    from mangohudpy.gui.widgets import ImageViewer
    from pathlib import Path
    v = ImageViewer()
    v.load_image(tmp_path / "nonexistent.png")
    assert "Could not load" in v._label.text()
    assert v.current_path is None  # add this assertion
