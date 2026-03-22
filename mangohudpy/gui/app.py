"""QApplication entry point for mangohud-py-gui."""
from __future__ import annotations
import sys
import argparse
from importlib.metadata import version as _pkg_version, PackageNotFoundError


try:
    _VERSION = _pkg_version("mangohudpy")
except PackageNotFoundError:
    _VERSION = "0.0.0"


def _ensure_display() -> None:
    """Set QT_QPA_PLATFORM to wayland if no X display is available."""
    import os
    if not os.environ.get("DISPLAY") and not os.environ.get("QT_QPA_PLATFORM"):
        if os.environ.get("WAYLAND_DISPLAY"):
            os.environ["QT_QPA_PLATFORM"] = "wayland"


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    # Handle --help / -h explicitly so main() returns 0 instead of raising SystemExit.
    # This also keeps Qt imports deferred — Qt is never imported for help requests.
    if "--help" in args or "-h" in args:
        p = argparse.ArgumentParser(
            prog="mangohud-py-gui",
            description="MangoHudPy Desktop GUI — run without arguments to open the window.",
        )
        p.print_help()
        return 0

    _ensure_display()

    try:
        from PySide6.QtGui import QColor, QPalette
        from PySide6.QtWidgets import QApplication, QStyleFactory
        from mangohudpy.gui.main_window import MainWindow
    except ImportError as exc:
        print(f"Cannot start GUI: {exc}")
        print("Install with: pip install 'mangohudpy[gui]'")
        return 1

    app = QApplication(sys.argv if argv is None else ["mangohud-py-gui"] + list(args))
    app.setApplicationName("MangoHudPy")
    app.setApplicationVersion(_VERSION)

    # Set the window icon from the bundled SVG so the titlebar + taskbar show it
    try:
        from PySide6.QtGui import QIcon
        from pathlib import Path
        _icon_path = Path(__file__).parent.parent / "data" / "mangohudpy.svg"
        if not _icon_path.exists():
            import importlib.resources as _ir
            _ref = _ir.files("mangohudpy.data").joinpath("mangohudpy.svg")
            with _ir.as_file(_ref) as _p:
                _icon_path = _p
        app.setWindowIcon(QIcon(str(_icon_path)))
    except Exception:
        pass

    # Force Fusion so the dark palette is respected on all platforms/DEs.
    # Without Fusion, some native styles (e.g. GTK) ignore custom palettes.
    if "Fusion" in QStyleFactory.keys():
        app.setStyle("Fusion")

    # Increase base font size for readability at 1280×800 (Steam Deck native)
    from PySide6.QtGui import QFont
    font = app.font()
    font.setPointSize(max(font.pointSize() + 2, 13))
    app.setFont(font)

    apply_theme("dark", app)

    # Install XDG desktop entry + icon on first run (silent no-op if already done)
    try:
        from mangohudpy.desktop import install_desktop
        install_desktop()
    except Exception:
        pass

    win = MainWindow()
    win.show()
    return app.exec()


def apply_theme(theme: str, app=None) -> None:
    """Apply 'dark' or 'light' theme to the QApplication."""
    from PySide6.QtWidgets import QApplication
    if app is None:
        app = QApplication.instance()
    if app is None:
        return
    if theme == "dark":
        app.setPalette(_dark_palette())
        app.setStyleSheet(
            "QToolTip { color: #ffffff; background-color: #2a2a2a; border: 1px solid #555; }"
            "QPlainTextEdit { background-color: #1e1e1e; color: #d4d4d4; }"
            "QTableWidget { background-color: #1e1e1e; color: #d4d4d4; gridline-color: #3a3a3a; }"
            "QHeaderView::section { background-color: #2d2d2d; color: #d4d4d4; border: 1px solid #3a3a3a; }"
            "QListWidget { background-color: #1e1e1e; color: #d4d4d4; }"
            "QComboBox { background-color: #2d2d2d; color: #d4d4d4; }"
            "QLineEdit { background-color: #2d2d2d; color: #d4d4d4; }"
            "QSpinBox, QDoubleSpinBox { background-color: #2d2d2d; color: #d4d4d4; }"
            "QSplitter::handle { background-color: #4a4a4a; }"
            "QSplitter::handle:horizontal { width: 6px; }"
            "QSplitter::handle:vertical { height: 6px; }"
            "QSplitter::handle:hover { background-color: #7cb5ec; }"
        )
    else:
        app.setPalette(_light_palette())
        app.setStyleSheet(
            "QSplitter::handle { background-color: #cccccc; }"
            "QSplitter::handle:horizontal { width: 6px; }"
            "QSplitter::handle:vertical { height: 6px; }"
            "QSplitter::handle:hover { background-color: #7cb5ec; }"
        )


def _dark_palette() -> "QPalette":
    """Return a dark QPalette matching a VS Code / MangoHud dark aesthetic."""
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtCore import Qt

    p = QPalette()
    # Base colors
    p.setColor(QPalette.ColorRole.Window,          QColor("#212121"))
    p.setColor(QPalette.ColorRole.WindowText,      QColor("#e0e0e0"))
    p.setColor(QPalette.ColorRole.Base,            QColor("#1e1e1e"))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor("#2a2a2a"))
    p.setColor(QPalette.ColorRole.Text,            QColor("#e0e0e0"))
    p.setColor(QPalette.ColorRole.BrightText,      QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.Button,          QColor("#2d2d2d"))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor("#e0e0e0"))
    p.setColor(QPalette.ColorRole.Link,            QColor("#7cb5ec"))
    p.setColor(QPalette.ColorRole.LinkVisited,     QColor("#8085e9"))
    # Highlights — use MangoHud's blue accent
    p.setColor(QPalette.ColorRole.Highlight,       QColor("#7cb5ec"))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))
    # Disabled state — muted versions
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#555555"))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,       QColor("#555555"))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#555555"))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight,  QColor("#3a3a3a"))
    return p


def _light_palette() -> "QPalette":
    """Return a clean light QPalette with MangoHud blue accent."""
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication
    # Start from the default palette so Qt fills in everything correctly
    p = QApplication.style().standardPalette()
    p.setColor(QPalette.ColorRole.Highlight,       QColor("#7cb5ec"))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))
    p.setColor(QPalette.ColorRole.Link,            QColor("#2980b9"))
    return p


if __name__ == "__main__":
    sys.exit(main())
