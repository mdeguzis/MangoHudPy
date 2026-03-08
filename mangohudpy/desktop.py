"""XDG desktop integration: install .desktop file and icon on first run."""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path


_DESKTOP_CONTENT = """\
[Desktop Entry]
Version=1.0
Type=Application
Name=MangoHudPy
Comment=MangoHud configurator, profiler, and log manager
Exec=mangohud-py-gui
Icon=mangohudpy
Terminal=false
Categories=Utility;Settings;Game;
Keywords=mangohud;fps;gaming;linux;performance;
StartupNotify=true
"""

# XDG hicolor theme paths — the standard fallback every DE honours
_ICONS_BASE  = Path.home() / ".local" / "share" / "icons" / "hicolor"
_SVG_DIR     = _ICONS_BASE / "scalable" / "apps"
_PNG_DIR     = _ICONS_BASE / "128x128"  / "apps"
_APPS_DIR    = Path.home() / ".local" / "share" / "applications"
_DESKTOP     = _APPS_DIR / "mangohud-py-gui.desktop"
_ICON_SVG    = _SVG_DIR  / "mangohudpy.svg"
_ICON_PNG    = _PNG_DIR  / "mangohudpy.png"


def _icon_src() -> Path | None:
    """Return the bundled SVG icon path, or None if not found."""
    # Editable / source installs: file is next to this module
    candidate = Path(__file__).parent / "data" / "mangohudpy.svg"
    if candidate.exists():
        return candidate
    # Wheel installs: use importlib.resources
    try:
        import importlib.resources as _ir
        ref = _ir.files("mangohudpy.data").joinpath("mangohudpy.svg")
        with _ir.as_file(ref) as p:
            return Path(str(p)) if Path(str(p)).exists() else None
    except Exception:
        return None


def _render_png(svg_path: Path, png_path: Path, size: int = 128) -> bool:
    """Render the SVG to a PNG using PySide6 QSvgRenderer (no display needed)."""
    try:
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtCore import Qt

        app = QApplication.instance() or QApplication([])  # noqa: F841
        renderer = QSvgRenderer(str(svg_path))
        if not renderer.isValid():
            return False
        img = QImage(size, size, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        renderer.render(painter)
        painter.end()
        png_path.parent.mkdir(parents=True, exist_ok=True)
        return img.save(str(png_path))
    except Exception:
        return False


def install_desktop(force: bool = False) -> None:
    """
    Install the XDG .desktop entry and icon into the hicolor icon theme.

    Places the SVG at  ~/.local/share/icons/hicolor/scalable/apps/mangohudpy.svg
    and a 128×128 PNG at ~/.local/share/icons/hicolor/128x128/apps/mangohudpy.png
    so all desktop environments find the icon via the standard hicolor fallback.

    Silently skips if already installed unless *force* is True.
    """
    if _DESKTOP.exists() and not force:
        return

    _APPS_DIR.mkdir(parents=True, exist_ok=True)
    _SVG_DIR.mkdir(parents=True, exist_ok=True)
    _PNG_DIR.mkdir(parents=True, exist_ok=True)

    src = _icon_src()
    if src:
        shutil.copy2(src, _ICON_SVG)
        _render_png(src, _ICON_PNG)

    _DESKTOP.write_text(_DESKTOP_CONTENT, encoding="utf-8")

    # Refresh caches so the DE picks up the new entry immediately
    for cmd in (
        ["update-desktop-database", str(_APPS_DIR)],
        ["gtk-update-icon-cache", "-q", "-t", "-f", str(_ICONS_BASE)],
        ["xdg-icon-resource", "forceupdate"],
    ):
        try:
            subprocess.run(cmd, check=False, capture_output=True, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
