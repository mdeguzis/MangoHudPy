"""Main application window: sidebar + QStackedWidget."""
from __future__ import annotations
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QPushButton, QSizePolicy, QSplitter, QStackedWidget,
    QVBoxLayout, QWidget,
)

from mangohudpy.utils import discover_games


_NAV_PAGES = [
    "Dashboard",
    "Organize",
    "Summary",
    "Graphs",
    "Config",
    "Upload",
    "Profile",
    "Launch Option",
    "Test",
]


class MainWindow(QMainWindow):
    """Top-level window with sidebar navigation."""

    game_selected = Signal(str)   # "" means "All Games"

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("MangoHudPy")

        app = QApplication.instance()
        self._base_font_size: int = app.font().pointSize() if app else 13
        self._current_font_size: int = self._base_font_size

        self._build_menu()
        self._fit_to_screen()

        # Root splitter: sidebar (resizable) + page stack
        root_splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── sidebar ───────────────────────────────────────────────────
        self._sidebar = QWidget()
        sidebar = self._sidebar
        sidebar.setMinimumWidth(240)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(4, 8, 4, 8)
        sidebar_layout.setSpacing(4)

        sidebar_layout.addWidget(QLabel("<b>SOURCES</b>"))

        self.game_list = QListWidget()
        self.game_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        sidebar_layout.addWidget(self.game_list)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_games)
        sidebar_layout.addWidget(refresh_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sidebar_layout.addWidget(sep)

        self.nav_buttons: List[QPushButton] = []
        for i, name in enumerate(_NAV_PAGES):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=i: self._switch_page(idx))
            sidebar_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        root_splitter.addWidget(sidebar)

        # ── page stack (fills remaining width) ───────────────────────
        self.stack = QStackedWidget()
        self.stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.stack.setMinimumWidth(300)
        root_splitter.addWidget(self.stack)
        root_splitter.setChildrenCollapsible(False)
        root_splitter.setHandleWidth(6)
        self._root_splitter = root_splitter

        self.setCentralWidget(root_splitter)

        self._init_pages()
        self.refresh_games()
        self.game_list.currentRowChanged.connect(lambda _: self._on_game_selected())
        self._switch_page(0)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # After the window is shown at 240px min, relax the minimum so the
        # user can drag the sidebar narrower than 240 if they want.
        QTimer.singleShot(0, lambda: self._sidebar.setMinimumWidth(120))

    def _fit_to_screen(self) -> None:
        """Size the window to fit within the available desktop area at startup."""
        app = QApplication.instance()
        screen = app.primaryScreen() if app else None
        if screen is None:
            self.resize(1280, 800)
            return
        avail = screen.availableGeometry()
        w = min(1280, avail.width())
        h = min(800, avail.height())
        self.resize(w, h)
        self.move(
            avail.left() + (avail.width() - w) // 2,
            avail.top() + (avail.height() - h) // 2,
        )

    def _build_menu(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")

        zoom_in = file_menu.addAction("Zoom In")
        zoom_in.setShortcut(QKeySequence("Ctrl+="))   # = and + are same physical key
        zoom_in.triggered.connect(lambda: self._adjust_zoom(1))
        # Also catch Ctrl++ for keyboards/platforms that send it
        QShortcut(QKeySequence("Ctrl++"), self).activated.connect(
            lambda: self._adjust_zoom(1)
        )

        zoom_out = file_menu.addAction("Zoom Out")
        zoom_out.setShortcut(QKeySequence("Ctrl+-"))
        zoom_out.triggered.connect(lambda: self._adjust_zoom(-1))

        zoom_reset = file_menu.addAction("Reset Zoom")
        zoom_reset.setShortcut(QKeySequence("Ctrl+0"))
        zoom_reset.triggered.connect(self._zoom_reset)

        file_menu.addSeparator()

        quit_action = file_menu.addAction("Quit")
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)

        # ── Settings menu ─────────────────────────────────────────────
        settings_menu = menubar.addMenu("Settings")
        theme_menu = settings_menu.addMenu("Theme")

        from PySide6.QtGui import QActionGroup
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)

        self._dark_action = theme_menu.addAction("Dark")
        self._dark_action.setCheckable(True)
        self._dark_action.setChecked(True)
        theme_group.addAction(self._dark_action)

        self._light_action = theme_menu.addAction("Light")
        self._light_action.setCheckable(True)
        theme_group.addAction(self._light_action)

        self._dark_action.triggered.connect(lambda: self._set_theme("dark"))
        self._light_action.triggered.connect(lambda: self._set_theme("light"))

        # ── Help menu ─────────────────────────────────────────────────
        help_menu = menubar.addMenu("Help")

        about_action = help_menu.addAction("About / GitHub")
        about_action.triggered.connect(self._open_github)

    def _open_github(self) -> None:
        QDesktopServices.openUrl(QUrl("https://github.com/mdeguzis/MangoHudPy"))

    def _set_theme(self, theme: str) -> None:
        from mangohudpy.gui.app import apply_theme
        apply_theme(theme)

    def _adjust_zoom(self, delta: int) -> None:
        new_size = max(8, min(24, self._current_font_size + delta))
        if new_size != self._current_font_size:
            self._current_font_size = new_size
            self._apply_font_size(new_size)

    def _zoom_reset(self) -> None:
        self._current_font_size = self._base_font_size
        self._apply_font_size(self._base_font_size)

    def _apply_font_size(self, size: int) -> None:
        """Set font size on the QApplication and all existing widgets.

        QApplication.setFont() only affects widgets created *after* the call in
        Qt6/PySide6.  Iterating allWidgets() and setting the font explicitly
        forces every already-created widget to update immediately.

        The window size is never changed; zoomed content simply reflows
        within the existing window bounds.
        """
        from PySide6.QtGui import QFont
        app = QApplication.instance()
        if app is None:
            return
        font = QFont(app.font())
        font.setPointSize(size)
        app.setFont(font)
        for widget in app.allWidgets():
            widget.setFont(font)

    def _init_pages(self) -> None:
        from mangohudpy.gui.pages.dashboard import DashboardPage
        from mangohudpy.gui.pages.organize import OrganizePage
        from mangohudpy.gui.pages.summary import SummaryPage
        from mangohudpy.gui.pages.graphs import GraphsPage
        from mangohudpy.gui.pages.config import ConfigPage
        from mangohudpy.gui.pages.upload import UploadPage
        from mangohudpy.gui.pages.profile import ProfilePage
        from mangohudpy.gui.pages.test_page import TestPage
        from mangohudpy.gui.pages.launch_option import LaunchOptionPage

        self._pages = [
            DashboardPage(self),
            OrganizePage(self),
            SummaryPage(self),
            GraphsPage(self),
            ConfigPage(self),
            UploadPage(self),
            ProfilePage(self),
            LaunchOptionPage(self),
            TestPage(self),
        ]
        for page in self._pages:
            self.stack.addWidget(page)
            self.game_selected.connect(page.on_game_selected)

    def _switch_page(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == idx)

    def _on_game_selected(self) -> None:
        item = self.game_list.currentItem()
        game = "" if item is None or item.text() == "(All Games)" else item.text()
        self.game_selected.emit(game)

    def refresh_games(self) -> None:
        self.game_list.clear()
        self.game_list.addItem(QListWidgetItem("(All Games)"))
        for name in discover_games():
            self.game_list.addItem(QListWidgetItem(name))
        self.game_list.setCurrentRow(0)
