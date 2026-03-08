"""Shared utility functions: logging setup, OS detection, CSV parsing, helpers."""
from __future__ import annotations

import datetime
import logging
import pathlib
import re
import shutil
import sys
from typing import Dict, List, Optional, Tuple

from .constants import (
    LOG_FMT,
    LOG_DATEFMT,
    MANGOHUD_ALT_LOG,
    MANGOHUD_LOG_DIR,
    MANGOHUD_TMP_LOG,
    PROG_NAME,
    STEAM_APPS_DIR,
    STEAM_FLATPAK_APPS_DIR,
    STEAM_FLATPAK_LOG_DIR,
    STEAM_LOG_DIR,
)

log = logging.getLogger(PROG_NAME)

# ── MangoHud CSV spec header fields ────────────────────────────────────
_MANGOHUD_SPEC_FIELDS = {"os", "cpu", "gpu", "ram", "kernel", "driver", "cpuscheduler"}


def setup_logging(verbosity: int = 0, logfile: Optional[str] = None) -> None:
    level = [logging.WARNING, logging.INFO, logging.DEBUG][min(verbosity, 2)]
    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if logfile:
        fh = logging.FileHandler(logfile, mode="a", encoding="utf-8")
        fh.setFormatter(logging.Formatter(LOG_FMT, datefmt=LOG_DATEFMT))
        handlers.append(fh)
    logging.basicConfig(
        level=level, format=LOG_FMT, datefmt=LOG_DATEFMT, handlers=handlers
    )
    log.setLevel(level)


# ── OS detection ───────────────────────────────────────────────────────


def detect_os() -> Dict[str, str]:
    info: Dict[str, str] = {}
    p = pathlib.Path("/etc/os-release")
    if p.exists():
        for ln in p.read_text().splitlines():
            if "=" in ln:
                k, _, v = ln.partition("=")
                info[k.strip()] = v.strip().strip('"')
    return info


def is_bazzite() -> bool:
    i = detect_os()
    return "bazzite" in (i.get("NAME", "") + " " + i.get("ID", "")).lower()


def is_steamos() -> bool:
    i = detect_os()
    return (
        "steamos" in (i.get("ID", "") + " " + i.get("ID_LIKE", "")).lower()
        or is_bazzite()
    )


def mangohud_installed() -> bool:
    return shutil.which("mangohud") is not None


# ── Log file discovery ─────────────────────────────────────────────────


def find_logs(
    d: Optional[pathlib.Path] = None, pat: str = "*.csv", game: Optional[str] = None
) -> List[pathlib.Path]:
    """Find MangoHud CSV logs, optionally filtered by game name.

    Searches both flat log directories and one level of organized subdirectories
    (e.g. ~/mangologs/<Source>/<file>.csv created by the organize command).
    """
    dirs = [d] if d else [MANGOHUD_LOG_DIR, MANGOHUD_TMP_LOG, MANGOHUD_ALT_LOG]
    seen: set = set()
    r: List[pathlib.Path] = []
    for x in dirs:
        if not (x and x.is_dir()):
            continue
        for p in sorted(x.glob(pat)):
            if p.is_symlink():
                continue
            resolved = p.resolve()
            if resolved not in seen:
                seen.add(resolved)
                r.append(p)
        # Also search organized per-source subdirectories (one level deep)
        for p in sorted(x.glob(f"*/{pat}")):
            if p.is_symlink():
                continue
            resolved = p.resolve()
            if resolved not in seen:
                seen.add(resolved)
                r.append(p)
    if game:
        gl = game.lower()
        r = [p for p in r if p.stem.lower().startswith(gl)]
    return r


def newest_log(
    d: Optional[pathlib.Path] = None, game: Optional[str] = None
) -> Optional[pathlib.Path]:
    ls = find_logs(d, game=game)
    return max(ls, key=lambda p: p.stat().st_mtime) if ls else None


def discover_games(d: Optional[pathlib.Path] = None) -> List[str]:
    """Return sorted unique game names found in MangoHud log filenames."""
    logs = find_logs(d)
    names: set[str] = set()
    for p in logs:
        stem = p.stem
        m = re.match(r"^(.+?)_\d{4}[-_]", stem)
        if m:
            names.add(m.group(1))
        else:
            names.add(stem)
    return sorted(names, key=str.lower)


def _extract_game_name(stem: str) -> str:
    """Extract game name from MangoHud log filename stem."""
    m = re.match(r"^(.+?)_\d{4}[-_]", stem)
    name = m.group(1) if m else stem
    if name.lower().endswith(".exe"):
        name = name[:-4]
    return name


# ── CSV parsing ────────────────────────────────────────────────────────


def _strip_v1_preamble(lines: List[str]) -> List[str]:
    """Remove MangoHud >=0.8 preamble lines, leaving the 3-line spec format."""
    return [
        ln for ln in lines
        if not re.match(r"^v\d", ln.strip())
        and not re.match(r"^-{3}", ln.strip())
    ]


def _normalize_csv_for_flightless(path: pathlib.Path) -> str:
    """Return CSV content normalized to the FlightlessSomething 3-line spec format."""
    raw = path.read_text(encoding="utf-8", errors="replace").splitlines()
    cleaned = _strip_v1_preamble([ln for ln in raw if ln.strip()])
    return "\n".join(cleaned) + "\n"


def parse_csv(
    path: pathlib.Path,
) -> Tuple[List[str], List[Dict[str, str]]]:
    """Parse a MangoHud CSV log, returning (column_names, rows).

    Handles modern 3-line spec-header format, MangoHud 0.8+ v1 format, and
    legacy #-comment format.
    """
    lines = [
        s
        for s in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if s.strip()
    ]
    if not lines:
        return [], []

    lines = _strip_v1_preamble(lines)
    if not lines:
        return [], []

    # Detect modern spec-header format
    first_fields = {f.strip().lower() for f in lines[0].split(",")}
    if first_fields & _MANGOHUD_SPEC_FIELDS and len(first_fields & _MANGOHUD_SPEC_FIELDS) >= 3:
        if len(lines) < 3:
            return [], []
        cols = [c.strip() for c in lines[2].split(",")]
        rows: List[Dict[str, str]] = []
        for ln in lines[3:]:
            vs = ln.split(",")
            if len(vs) == len(cols):
                rows.append(dict(zip(cols, [v.strip() for v in vs])))
        return cols, rows

    # Legacy format
    hi = 0
    for i, ln in enumerate(lines):
        if ln.startswith("#"):
            hi = i + 1
            continue
        parts = ln.split(",")
        if (
            sum(1 for p in parts if re.match(r"^[A-Za-z_]+", p.strip()))
            > len(parts) * 0.5
        ):
            hi = i
            break
    cols = [c.strip() for c in lines[hi].split(",")]
    rows = []
    for ln in lines[hi + 1:]:
        vs = ln.split(",")
        if len(vs) == len(cols):
            rows.append(dict(zip(cols, [v.strip() for v in vs])))
    return cols, rows


# ── Math / formatting helpers ──────────────────────────────────────────


def sf(v: str, d: float = 0.0) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return d


def hdur(s: float) -> str:
    if s < 60:
        return f"{s:.1f}s"
    m, s2 = divmod(s, 60)
    if m < 60:
        return f"{int(m)}m {s2:.0f}s"
    h, m = divmod(m, 60)
    return f"{int(h)}h {int(m)}m {s2:.0f}s"


def pctl(sv: List[float], p: float) -> float:
    if not sv:
        return 0.0
    k = (len(sv) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sv) - 1)
    return sv[f] + (k - f) * (sv[c] - sv[f])


def _fcol(cols: List[str], cands: List[str]) -> Optional[str]:
    m = {c.lower(): c for c in cols}
    for c in cands:
        if c.lower() in m:
            return m[c.lower()]
    return None


# ── Steam session helpers ──────────────────────────────────────────────


def _resolve_game_name(name: str, steam_app_names: Dict[str, str]) -> str:
    """Match an extracted game name against known Steam app names.

    Strips all non-alphanumeric characters from both sides before comparing,
    so 'HorizonZeroDawnRemastered' matches 'Horizon Zero Dawn Remastered'.
    Returns the canonical Steam app name on a match, or the original name.
    """
    normalized = re.sub(r"[^a-z0-9]", "", name.lower())
    for app_name in steam_app_names.values():
        if re.sub(r"[^a-z0-9]", "", app_name.lower()) == normalized:
            return app_name
    return name


def _sanitize_game_name(name: str) -> str:
    """Strip filesystem-unsafe characters from a Steam game name."""
    safe = re.sub(r'[\\/:*?"<>|™®©]', "", name)
    safe = re.sub(r"\s+", " ", safe).strip()
    return safe[:64] if safe else "UnknownGame"


def load_steam_app_names() -> Dict[str, str]:
    """Return {app_id: sanitized_name} from steamapps/*.acf files."""
    apps_dir = STEAM_APPS_DIR if STEAM_APPS_DIR.is_dir() else STEAM_FLATPAK_APPS_DIR
    names: Dict[str, str] = {}
    if not apps_dir.is_dir():
        return names
    for acf in apps_dir.glob("appmanifest_*.acf"):
        app_id = app_name = None
        for line in acf.read_text(errors="replace").splitlines():
            m = re.match(r'\s*"appid"\s+"(\d+)"', line)
            if m:
                app_id = m.group(1)
            m = re.match(r'\s*"name"\s+"(.+)"', line)
            if m:
                app_name = m.group(1)
            if app_id and app_name:
                break
        if app_id and app_name:
            names[app_id] = _sanitize_game_name(app_name)
    return names


def parse_steam_game_sessions() -> (
    List[Tuple[str, datetime.datetime, Optional[datetime.datetime]]]
):
    """Parse Steam content_log for game run sessions.

    Returns list of (app_id, start_dt, end_dt_or_None), oldest first.
    Reads content_log.previous.txt then content_log.txt so the full
    history is covered even after Steam rotates the log.
    """
    log_dir = STEAM_LOG_DIR if STEAM_LOG_DIR.is_dir() else STEAM_FLATPAK_LOG_DIR
    sessions: List[Tuple[str, datetime.datetime, Optional[datetime.datetime]]] = []
    active: Dict[str, datetime.datetime] = {}
    ts_re = re.compile(
        r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] AppID (\d+) state changed : (.+)"
    )
    for log_name in ("content_log.previous.txt", "content_log.txt"):
        log_path = log_dir / log_name
        if not log_path.exists():
            continue
        for line in log_path.read_text(errors="replace").splitlines():
            m = ts_re.match(line)
            if not m:
                continue
            ts_str, app_id, state = m.group(1), m.group(2), m.group(3)
            try:
                ts = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            if "App Running" in state and "Terminating" not in state:
                active[app_id] = ts
            elif app_id in active and "App Running" not in state:
                sessions.append((app_id, active.pop(app_id), ts))
    for app_id, start in active.items():
        sessions.append((app_id, start, None))
    return sessions


def find_game_for_timestamp(
    ts: datetime.datetime,
    sessions: List[Tuple[str, datetime.datetime, Optional[datetime.datetime]]],
    app_names: Dict[str, str],
    pre_tolerance_secs: int = 180,
    csv_end: Optional[datetime.datetime] = None,
) -> Optional[str]:
    """Return the game name whose Steam session overlaps the CSV time range, or None.

    pre_tolerance_secs: how many seconds before "App Running" to consider
    the game already active (covers long load times before Steam reports it).
    csv_end: mtime of the CSV file. When provided, a session matches if it
    overlaps the interval [ts, csv_end], catching games that take longer to
    report "App Running" than pre_tolerance_secs allows.
    """
    for app_id, start, end in sessions:
        window_start = start - datetime.timedelta(seconds=pre_tolerance_secs)
        window_end = end if end is not None else datetime.datetime.max
        # Point-in-time match (original behaviour)
        if window_start <= ts <= window_end:
            return app_names.get(app_id)
        # Overlap match: CSV ran from ts→csv_end; session ran from start→end.
        # They overlap if ts < window_end and csv_end > window_start.
        if csv_end is not None and ts < window_end and csv_end > window_start:
            return app_names.get(app_id)
    return None
