"""launch-option command: TUI to set per-game Steam mangohud launch options.

When Steam is running, uses the Steam CEF debugger (localhost:8080) to call
SteamClient.Apps.SetAppLaunchOptions() live -- no restart required.
When Steam is not running, writes directly to localconfig.vdf.
"""
from __future__ import annotations

import argparse
import curses
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.request
from typing import Dict, List, Optional, Tuple

from .constants import MANGOHUD_LOG_DIR, VERSION
from .utils import load_steam_app_names, log

# ── Steam paths ────────────────────────────────────────────────────────

_STEAM_USERDATA = pathlib.Path.home() / ".local/share/Steam/userdata"
_FLATPAK_USERDATA = (
    pathlib.Path.home()
    / ".var/app/com.valvesoftware.Steam/.local/share/Steam/userdata"
)
_CEF_PORT = 8080


def _userdata_dir() -> Optional[pathlib.Path]:
    for d in (_STEAM_USERDATA, _FLATPAK_USERDATA):
        if d.is_dir():
            return d
    return None


def _steam_userid() -> Optional[str]:
    base = _userdata_dir()
    if not base:
        return None
    users = [
        d for d in base.iterdir()
        if d.is_dir() and d.name.isdigit() and d.name != "0"
    ]
    if not users:
        return None
    return max(users, key=lambda p: p.stat().st_mtime).name


def _localconfig_path() -> Optional[pathlib.Path]:
    base = _userdata_dir()
    uid = _steam_userid()
    if not base or not uid:
        return None
    return base / uid / "config" / "localconfig.vdf"


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
        if not isinstance(entry, dict):
            return ""
        # Key can be 'LaunchOptions' or 'launchoptions' depending on Steam version
        for k in entry:
            if k.lower() == "launchoptions":
                return entry[k]
        return ""
    except (KeyError, TypeError):
        return ""


def _set_launch_option_vdf(data: dict, app_id: str, option: str) -> None:
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


# ── Steam CEF IPC ──────────────────────────────────────────────────────


def _cef_target() -> Optional[str]:
    """Return the WebSocket URL for SharedJSContext, or None."""
    try:
        raw = urllib.request.urlopen(
            f"http://localhost:{_CEF_PORT}/json", timeout=2
        ).read()
        pages = json.loads(raw)
        target = next(
            (p for p in pages if "SharedJSContext" in p.get("title", "")),
            None,
        )
        if not target:
            target = next(
                (p for p in pages if p.get("type") == "page"),
                None,
            )
        return target["webSocketDebuggerUrl"] if target else None
    except Exception:
        return None


def _cef_set_launch_option(app_id: str, option: str) -> bool:
    """Call SteamClient.Apps.SetAppLaunchOptions via CEF debugger. Returns True on success."""
    try:
        import websocket
    except ImportError:
        return False

    ws_url = _cef_target()
    if not ws_url:
        return False

    # Escape option string for JS: escape backslashes and double-quotes
    safe_opt = option.replace("\\", "\\\\").replace('"', '\\"')
    js = f'SteamClient.Apps.SetAppLaunchOptions({int(app_id)}, "{safe_opt}")'

    try:
        ws = websocket.create_connection(ws_url, timeout=5)
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": js, "awaitPromise": True},
        }))
        result = json.loads(ws.recv())
        ws.close()
        # undefined return means success for this Steam API call
        res_type = result.get("result", {}).get("result", {}).get("type", "")
        return res_type in ("undefined", "boolean", "object")
    except Exception as exc:
        log.debug("CEF set_launch_option failed: %s", exc)
        return False


def _cef_available() -> bool:
    return _cef_target() is not None


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
    if not opt.strip():
        return f"{prefix}%command%"
    if "%command%" in opt:
        return opt.replace("%command%", f"{prefix}%command%", 1)
    return f"{prefix}{opt}"


def _remove_mangohud(opt: str) -> str:
    result = _MH_RE.sub("", opt).strip()
    if result == "%command%":
        return ""
    return result


# ── TUI ────────────────────────────────────────────────────────────────


class _LaunchOptionTUI:
    def __init__(
        self,
        games: List[Tuple[str, str]],
        vdf_data: dict,
        log_dir: pathlib.Path,
        game_mode: bool,
        use_cef: bool,
    ):
        self.games = sorted(games, key=lambda x: x[1].lower())
        self.vdf_data = vdf_data
        self.log_dir = log_dir
        self.game_mode = game_mode
        self.use_cef = use_cef
        self.prefix = _mangohud_prefix(log_dir)

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
            curses.init_pair(1, curses.COLOR_GREEN, -1)   # enabled + unchanged
            curses.init_pair(2, curses.COLOR_YELLOW, -1)  # pending change
            curses.init_pair(3, curses.COLOR_CYAN, -1)    # header
            curses.init_pair(4, curses.COLOR_RED, -1)     # warning

        while True:
            stdscr.erase()
            h, w = stdscr.getmaxyx()
            filtered = self._filtered()

            if filtered:
                self.cursor = max(0, min(self.cursor, len(filtered) - 1))
            else:
                self.cursor = 0

            list_h = h - 6
            if self.cursor < self.scroll:
                self.scroll = self.cursor
            elif self.cursor >= self.scroll + list_h:
                self.scroll = self.cursor - list_h + 1

            row = 0

            # Header
            inject_method = "live via Steam CEF" if self.use_cef else "via localconfig.vdf"
            mode_label = "Game Mode" if self.game_mode else "Desktop Mode"
            hdr = f" MangoHud Launch Options  [{mode_label}  |  {inject_method}]  v{VERSION}"
            stdscr.addstr(row, 0, hdr[:w], curses.color_pair(3) | curses.A_BOLD)
            row += 1

            # Filter bar
            stdscr.addstr(row, 0, f" Filter: {self.filter_text}_"[:w])
            row += 1

            # Column header
            stdscr.addstr(row, 0, f"  {'Game':<45}  St."[:w], curses.A_UNDERLINE)
            row += 1

            # Game list
            for i, (app_id, name) in enumerate(filtered[self.scroll: self.scroll + list_h]):
                abs_i = self.scroll + i
                opt = self.pending[app_id]
                orig = self.original.get(app_id, "")
                has_mh = _has_mangohud(opt)
                changed = opt != orig
                sel = abs_i == self.cursor

                if changed:
                    attr = curses.color_pair(2) | curses.A_BOLD
                    status = "[ ON*]" if has_mh else "[OFF*]"
                elif has_mh:
                    attr = curses.color_pair(1)
                    status = "[ ON ]"
                else:
                    attr = 0
                    status = "[OFF ]"

                if sel:
                    attr |= curses.A_REVERSE

                line = f" {'>' if sel else ' '} {name:<45}  {status}"
                try:
                    stdscr.addstr(row, 0, line[:w], attr)
                except curses.error:
                    pass
                row += 1

            # Scroll hint
            if len(filtered) > list_h:
                pct = int(self.scroll / max(1, len(filtered) - list_h) * 100)
                try:
                    stdscr.addstr(row, 0, f"  ... {len(filtered)} games ({pct}%)"[:w])
                except curses.error:
                    pass

            # Footer
            nchanges = len(self._changes())
            change_str = f"  |  {nchanges} pending" if nchanges else ""
            footer = f" SPACE toggle  |  a select all  |  u apply+quit  |  q quit{change_str}"
            try:
                stdscr.addstr(h - 1, 0, footer[:w], curses.A_DIM)
            except curses.error:
                pass

            stdscr.refresh()

            try:
                key = stdscr.get_wch()
            except curses.error:
                continue

            if isinstance(key, str):
                if key in ("\x1b", "\x03"):
                    self.filter_text = ""
                    self.cursor = 0
                    self.scroll = 0
                elif key == " ":
                    if filtered:
                        self._toggle(filtered[self.cursor][0])
                elif key.lower() == "a":
                    # Select all visible: enable all if any are off, else disable all
                    all_on = all(_has_mangohud(self.pending[aid]) for aid, _ in filtered)
                    for aid, _ in filtered:
                        cur = self.pending[aid]
                        if all_on:
                            self.pending[aid] = _remove_mangohud(cur)
                        elif not _has_mangohud(cur):
                            self.pending[aid] = _add_mangohud(cur, self.prefix)
                elif key.lower() == "u":
                    return self._changes()
                elif key.lower() == "q":
                    return {}
                elif key in ("\x7f",):
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

    use_cef = _cef_available()
    game_mode = _is_game_mode()

    print(f"  Steam config : {cfg_path}")
    print(f"  Mode         : {'Game Mode' if game_mode else 'Desktop Mode'}")
    print(f"  Apply method : {'live via Steam CEF (no restart needed)' if use_cef else 'localconfig.vdf (Steam must not be running)'}")

    vdf_data = _load_localconfig(cfg_path)
    app_names = load_steam_app_names()
    if not app_names:
        print("ERROR: No Steam games found in steamapps/*.acf")
        return 1

    tui = _LaunchOptionTUI(
        games=list(app_names.items()),
        vdf_data=vdf_data,
        log_dir=log_dir,
        game_mode=game_mode,
        use_cef=use_cef,
    )
    changes = tui.run()

    if not changes:
        print("  No changes applied.")
        return 0

    failed = []
    for app_id, new_opt in changes.items():
        name = app_names.get(app_id, app_id)
        status = "[MANGOHUD]" if _has_mangohud(new_opt) else "[-]"

        if use_cef:
            ok = _cef_set_launch_option(app_id, new_opt)
            if not ok:
                failed.append((app_id, name, new_opt))
                print(f"  {status}  {name}  (CEF failed, falling back to VDF)")
                _set_launch_option_vdf(vdf_data, app_id, new_opt)
            else:
                print(f"  {status}  {name}  (live)")
        else:
            _set_launch_option_vdf(vdf_data, app_id, new_opt)
            print(f"  {status}  {name}")

        if new_opt:
            print(f"         {new_opt}")

    if not use_cef or failed:
        _save_localconfig(vdf_data, cfg_path)
        print(f"\n  Saved: {cfg_path}")
    else:
        print("\n  Applied live — no Steam restart needed.")

    return 0
