"""Tests for MainWindow — uses offscreen Qt platform."""
import os
import sys
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_main_window_title(qapp):
    """MainWindow has correct window title."""
    from mangohudpy.gui.main_window import MainWindow
    win = MainWindow()
    assert win.windowTitle() == "MangoHudPy"


def test_main_window_size(qapp):
    """MainWindow fits within the available screen geometry."""
    from mangohudpy.gui.main_window import MainWindow
    win = MainWindow()
    screen = qapp.primaryScreen()
    if screen:
        avail = screen.availableGeometry()
        assert win.width() <= avail.width()
        assert win.height() <= avail.height()
    else:
        assert win.width() > 0
        assert win.height() > 0


def test_sidebar_has_all_nav_buttons(qapp):
    """Sidebar contains all nav buttons from _NAV_PAGES."""
    from mangohudpy.gui.main_window import MainWindow, _NAV_PAGES
    win = MainWindow()
    labels = [btn.text() for btn in win.nav_buttons]
    for page_name in _NAV_PAGES:
        assert page_name in labels, f"Missing nav button: {page_name}"


def test_nav_buttons_count(qapp):
    """Nav button count matches _NAV_PAGES."""
    from mangohudpy.gui.main_window import MainWindow, _NAV_PAGES
    win = MainWindow()
    assert len(win.nav_buttons) == len(_NAV_PAGES)


def test_stack_has_all_pages(qapp):
    """QStackedWidget page count matches _NAV_PAGES."""
    from mangohudpy.gui.main_window import MainWindow, _NAV_PAGES
    win = MainWindow()
    assert win.stack.count() == len(_NAV_PAGES)


def test_game_list_has_all_games_entry(qapp):
    """Game list always starts with (All Games)."""
    from mangohudpy.gui.main_window import MainWindow
    win = MainWindow()
    assert win.game_list.item(0).text() == "(All)"


def test_game_selected_signal_emits(qapp):
    """game_selected signal fires when game list selection changes."""
    from mangohudpy.gui.main_window import MainWindow
    win = MainWindow()
    received = []
    win.game_selected.connect(received.append)
    win._on_game_selected()
    assert len(received) == 1


def test_switch_page_marks_button_checked(qapp):
    """_switch_page marks the correct nav button as checked."""
    from mangohudpy.gui.main_window import MainWindow
    win = MainWindow()
    win._switch_page(2)  # Summary
    assert win.nav_buttons[2].isChecked()
    assert not win.nav_buttons[0].isChecked()
