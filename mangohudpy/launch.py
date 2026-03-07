"""launch-option command: TUI to set per-game Steam mangohud launch options."""
from __future__ import annotations

import argparse
import curses
import os
import pathlib
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

from .constants import MANGOHUD_LOG_DIR, PROG_NAME, VERSION
from .utils import load_steam_app_names, log

# ── Steam paths ────────────────────────────────────────────────────────

_STEAM_USERDATA = pathlib.Path.home() / ".local/share/Steam/userdata"
_FLATPAK_USERDATA = (
    pathlib.Path.home()
    / ".var/app/com.valvesoftware.Steam/.local/share/Steam/userdata"
)


def _userdata_dir() -> Optional[pathlib.Path]:
    for d in (_STEAM_USERDATA, _FLATPAK_USERDATA):
        if d.is_dir():
            return d
    return None


def _steam_userid() -> Optional[str]:
    base = _userdata_dir()
    if not base:
        return None
    users = [d for d in base.iterdir() if d.is_dir() and d.name.isdigit() and d.name != "0"]
    if not users:
        return None
    return max(users, key=lambda p: p.stat().st_mtime).name


def _localconfig_path() -> Optional[pathlib.Path]:
    base = _userdata_dir()
    uid = _steam_userid()
    if not base or not uid:
        return None
    return base / uid / "config" / "localconfig.vdf"


def _steam_running() -> bool:
    try:
        return subprocess.run(["pgrep", "-x", "steam"], capture_output=True).returncode == 0
    except Exception:
        return False


def _is_game_mode() -> bool:
    for key in ("XDG_SESSION_DESKTOP", "DESKTOP_SESSION", "XDG_CURRENT_DESKTOP"):
        if "gamescope" in os.environ.get(key, "").lower():
            return True
    return False


# ── VDF helpers ────────────────────────────────────────────────────────


def _load_localconfig(path: pathlib.Path) -> dict:
    try:
        import vdf
    except ImportError:
        print("ERROR: 'vdf' library not installed.  Run: pip install vdf", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8", errors="replace") as f:
        return vdf.load(f)


def _save_localconfig(data: dict, path: pathlib.Path) -> None:
    try:
        import vdf
    except ImportError:
        sys.exit(1)
    with open(path, "w", encoding="utf-8") as f:
        vdf.dump(data, f, pretty=True)


def _get_launch_option(data: dict, app_id: str) -> str:
    try:
        apps = data["UserLocalConfigStore"]["Software"]["Valve"]["Steam"]["apps"]
        entry = apps.get(app_id) or apps.get(app_id.lower()) or {}
        return entry.get("LaunchOptions", "") if isinstance(entry, dict) else ""
    except (KeyError, TypeError):
        return ""


def _set_launch_option(data: dict, app_id: str, option: str) -> None:
    store = data.setdefault("UserLocalConfigStore", {})
    apps = (
        store.setdefault("Software", {})
        .setdefault("Valve", {})
        .setdefault("Steam", {})
        .setdefault("apps", {})
    )
    if app_id not in apps:
        apps[app_id] = {}
    if isinstance(apps[app_id], dict):
        apps[app_id]["LaunchOptions"] = option
    else:
        apps[app_id] = {"LaunchOptions": option}


# ── Mangohud option helpers ────────────────────────────────────────────

_MH_RE = re.compile(r'(?:MANGOHUD_CONFIG="[^"]*"\s+)?mangohud\s+', re.IGNORECASE)


def _mangohud_prefix(log_dir: pathlib.Path) -> str:
    cfg = (
        f"autostart_log=1,output_folder={log_dir},"
        "log_interval=100,log_versioning=1,log_duration=0"
    )
    return f'MANGOHUD_CONFIG="{cfg}" mangohud '


def _has_mangohud(opt: str) -> bool:
    return bool(_MH_RE.search(opt))


def _add_mangohud(opt: str, prefix: str) -> str:
    """Inject mangohud prefix before %command%, preserving existing env vars."""
    if not opt.strip():
        return f"{prefix}%command%"
    if "%command%" in opt:
        return opt.replace("%command%", f"{prefix}%command%", 1)
    return f"{prefix}{opt}"


def _remove_mangohud(opt: str) -> str:
    """Strip our mangohud injection, leaving other launch options intact."""
    result = _MH_RE.sub("", opt).strip()
    if result == "%command%":
        return ""
    return result


# ── TUI ────────────────────────────────────────────────────────────────


class _LaunchOptionTUI:
    """Curses TUI for toggling per-game mangohud launch options."""

    def __init__(
        self,
        games: List[Tuple[str, str]],   # [(app_id, name), ...]
        vdf_data: dict,
        log_dir: pathlib.Path,
        game_mode: bool,
        steam_running: bool,
    ):
        self.games = sorted(games, key=lambda x: x[1].lower())
        self.vdf_data = vdf_data
        self.log_dir = log_dir
        self.game_mode = game_mode
        self.steam_running = steam_running
        self.prefix = _mangohud_prefix(log_dir)

        # Build initial state: {app_id: current_launch_option}
        self.original: Dict[str, str] = {
            app_id: _get_launch_option(vdf_data, app_id)
            for app_id, _ in self.games
        }
        self.pending: Dict[str, str] = dict(self.original)

        self.filter_text = ""
        self.cursor = 0
        self.scroll = 0

    def _filtered(self) -> List[Tuple[str, str]]:
        if not self.filter_text:
            return self.games
        fl = self.filter_text.lower()
        return [(aid, name) for aid, name in self.games if fl in name.lower()]

    def _toggle(self, app_id: str) -> None:
        cur = self.pending[app_id]
        if _has_mangohud(cur):
            self.pending[app_id] = _remove_mangohud(cur)
        else:
            self.pending[app_id] = _add_mangohud(cur, self.prefix)

    def _changes(self) -> Dict[str, str]:
        return {
            aid: val
            for aid, val in self.pending.items()
            if val != self.original.get(aid, "")
        }

    def run(self) -> Dict[str, str]:
        return curses.wrapper(self._main)

    def _main(self, stdscr: "curses.window") -> Dict[str, str]:
        curses.curs_set(0)
        curses.use_default_colors()
        if curses.has_colors():
            curses.init_pair(1, curses.COLOR_GREEN, -1)   # enabled
            curses.init_pair(2, curses.COLOR_YELLOW, -1)  # changed
            curses.init_pair(3, curses.COLOR_CYAN, -1)    # header
            curses.init_pair(4, curses.COLOR_RED, -1)     # warning

        while True:
            stdscr.erase()
            h, w = stdscr.getmaxyx()
            filtered = self._filtered()

            # Clamp cursor
            if filtered:
                self.cursor = max(0, min(self.cursor, len(filtered) - 1))
            else:
                self.cursor = 0

            # Scroll so cursor is visible
            list_h = h - 7  # rows available for game list
            if self.cursor < self.scroll:
                self.scroll = self.cursor
            elif self.cursor >= self.scroll + list_h:
                self.scroll = self.cursor - list_h + 1

            row = 0

            # Header
            title = f" MangoHud Launch Options  [v{VERSION}]"
            mode_str = "Game Mode (changes lost on Steam restart)" if self.game_mode else "Desktop Mode"
            steam_str = "Steam running" if self.steam_running else "Steam stopped"
            stdscr.addstr(row, 0, title[:w], curses.color_pair(3) | curses.A_BOLD)
            stdscr.addstr(row, min(len(title) + 2, w - 1),
                          f"{mode_str}  |  {steam_str}"[:w - len(title) - 3],
                          curses.color_pair(4) if self.game_mode else curses.color_pair(1))
            row += 1

            # Filter bar
            filter_line = f" Filter: {self.filter_text}_"
            stdscr.addstr(row, 0, filter_line[:w])
            row += 1

            # Column header
            col_hdr = f"  {'Game':<50}  Status"
            stdscr.addstr(row, 0, col_hdr[:w], curses.A_UNDERLINE)
            row += 1

            # Game list
            visible = filtered[self.scroll: self.scroll + list_h]
            for i, (app_id, name) in enumerate(visible):
                abs_i = self.scroll + i
                opt = self.pending[app_id]
                orig = self.original.get(app_id, "")
                has_mh = _has_mangohud(opt)
                changed = opt != orig

                sel = abs_i == self.cursor
                prefix_ch = ">" if sel else " "

                status = "[MANGOHUD]" if has_mh else "[-]      "
                attr = curses.color_pair(1) if has_mh else 0
                if changed:
                    attr = curses.color_pair(2) | curses.A_BOLD
                if sel:
                    attr |= curses.A_REVERSE

                line = f" {prefix_ch} {name:<50}  {status}"
                try:
                    stdscr.addstr(row, 0, line[:w], attr)
                except curses.error:
                    pass
                row += 1

            # Scroll indicator
            if len(filtered) > list_h:
                pct = int(self.scroll / max(1, len(filtered) - list_h) * 100)
                stdscr.addstr(row, 0, f"  ... {len(filtered)} games  ({pct}% scrolled)"[:w])
            row += 1

            # Status bar
            nchanges = len(self._changes())
            change_str = f"  {nchanges} pending change(s)" if nchanges else ""
            stdscr.addstr(
                h - 2, 0,
                f" SPACE toggle  |  u apply+quit  |  q quit{change_str}"[:w],
                curses.A_DIM,
            )

            stdscr.refresh()

            # Input
            try:
                key = stdscr.get_wch()
            except curses.error:
                continue

            if isinstance(key, str):
                if key in ("\x1b", "\x03"):  # Esc / Ctrl-C
                    self.filter_text = ""
                elif key == "\n":
                    pass
                elif key == " ":
                    if filtered:
                        self._toggle(filtered[self.cursor][0])
                elif key.lower() == "u":
                    return self._changes()
                elif key.lower() == "q":
                    return {}
                elif key == "\x7f":  # Backspace
                    self.filter_text = self.filter_text[:-1]
                    self.cursor = 0
                    self.scroll = 0
                elif key.isprintable():
                    self.filter_text += key
                    self.cursor = 0
                    self.scroll = 0
            else:
                if key == curses.KEY_UP:
                    self.cursor = max(0, self.cursor - 1)
                elif key == curses.KEY_DOWN:
                    if filtered:
                        self.cursor = min(len(filtered) - 1, self.cursor + 1)
                elif key == curses.KEY_PPAGE:
                    self.cursor = max(0, self.cursor - 10)
                elif key == curses.KEY_NPAGE:
                    if filtered:
                        self.cursor = min(len(filtered) - 1, self.cursor + 10)
                elif key == curses.KEY_BACKSPACE:
                    self.filter_text = self.filter_text[:-1]
                    self.cursor = 0
                    self.scroll = 0


# ── Subcommand handler ─────────────────────────────────────────────────


def cmd_launch_option(args: argparse.Namespace) -> int:
    log_dir = pathlib.Path(args.log_dir) if args.log_dir else MANGOHUD_LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)

    cfg_path = _localconfig_path()
    if not cfg_path or not cfg_path.exists():
        print("ERROR: Steam localconfig.vdf not found.  Is Steam installed?")
        return 1

    game_mode = _is_game_mode()
    running = _steam_running()

    print(f"  Loading Steam config: {cfg_path}")
    vdf_data = _load_localconfig(cfg_path)

    app_names = load_steam_app_names()
    if not app_names:
        print("ERROR: No Steam games found in steamapps/*.acf")
        return 1

    games = [(aid, name) for aid, name in app_names.items()]

    if game_mode:
        print("  NOTE: Running in Game Mode — changes will be lost when Steam restarts.")
    if not running:
        print("  NOTE: Steam is not running — changes will persist.")

    tui = _LaunchOptionTUI(
        games=games,
        vdf_data=vdf_data,
        log_dir=log_dir,
        game_mode=game_mode,
        steam_running=running,
    )
    changes = tui.run()

    if not changes:
        print("  No changes applied.")
        return 0

    for app_id, new_opt in changes.items():
        _set_launch_option(vdf_data, app_id, new_opt)
        name = app_names.get(app_id, app_id)
        status = "[MANGOHUD]" if _has_mangohud(new_opt) else "[-]"
        print(f"  {status}  {name}")
        if new_opt:
            print(f"         {new_opt}")

    _save_localconfig(vdf_data, cfg_path)
    print(f"\n  Saved: {cfg_path}")

    if running and not game_mode:
        print("  Steam is running — restart it for launch option changes to apply in-game.")

    return 0
