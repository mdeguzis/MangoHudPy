"""Organize command: sort MangoHud logs into per-game folders with rotation."""
from __future__ import annotations

import argparse
import datetime
import os
import pathlib
import re
import shutil
from typing import List, Optional

from .constants import BENCH_LOG_DIR, MANGOHUD_ALT_LOG, MANGOHUD_LOG_DIR, MANGOHUD_TMP_LOG, MAX_LOGS_PER_GAME
from .utils import (
    _extract_game_name,
    _resolve_game_name,
    find_game_for_timestamp,
    find_logs,
    load_steam_app_names,
    log,
    parse_steam_game_sessions,
)


def _is_file_open(path: pathlib.Path) -> bool:
    """Return True if any process currently has this file open."""
    try:
        target_ino = path.stat().st_ino
    except OSError:
        return False
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        fd_dir = pathlib.Path(f"/proc/{pid}/fd")
        try:
            for fd in fd_dir.iterdir():
                try:
                    if fd.stat().st_ino == target_ino:
                        return True
                except OSError:
                    continue
        except PermissionError:
            continue
    return False


def _parse_mangoapp_timestamp(stem: str) -> Optional[datetime.datetime]:
    """Extract datetime from a mangoapp CSV stem like mangoapp_2026-03-07_16-15-37."""
    m = re.match(r"^mangoapp_(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})$", stem)
    if not m:
        return None
    try:
        return datetime.datetime.strptime(
            f"{m.group(1)} {m.group(2)}:{m.group(3)}:{m.group(4)}",
            "%Y-%m-%d %H:%M:%S",
        )
    except ValueError:
        return None


def _rotate_game_logs(game_dir: pathlib.Path, max_logs: int = MAX_LOGS_PER_GAME) -> int:
    """Delete oldest logs if game folder exceeds max_logs. Returns deleted count."""
    csvs = sorted(
        (p for p in game_dir.glob("*.csv") if not p.is_symlink()),
        key=lambda p: p.stat().st_mtime,
    )
    removed = 0
    while len(csvs) > max_logs:
        oldest = csvs.pop(0)
        oldest.unlink()
        removed += 1
        log.info("Rotated (deleted): %s", oldest)
    return removed


def cmd_organize(args: argparse.Namespace) -> int:
    """Sort MangoHud logs into per-game/date folders with rotation.

    Layout created:
        ~/Documents/MangoBench_Logs/
          <GameName>/
            <GameName>_YYYY-MM-DD_HH-MM-SS.csv
            current.csv  -> symlink to today's newest log
    """
    src_dir = pathlib.Path(args.source) if args.source else None
    dest = pathlib.Path(args.dest) if args.dest else BENCH_LOG_DIR
    max_logs = args.max_logs
    dry = args.dry_run

    raw_logs = [
        p for p in find_logs(src_dir)
        if not p.name.endswith("_summary.csv")
        and not p.name.endswith("-current-mangohud.csv")
    ]

    # Load Steam session data once for mangoapp CSV renaming and name resolution.
    steam_sessions = parse_steam_game_sessions()
    steam_app_names = load_steam_app_names()

    dest.mkdir(parents=True, exist_ok=True)
    dest_has_games = dest.exists() and any(p.is_dir() for p in dest.iterdir())

    if not raw_logs and not dest_has_games:
        print("  No MangoHud CSV logs found to organize.")
        print(f"    Searched: {MANGOHUD_LOG_DIR}, {MANGOHUD_ALT_LOG}")
        return 1
    moved = 0
    rotated = 0
    skipped = 0
    deleted = 0
    today = datetime.date.today().isoformat()
    originals_to_delete: List[pathlib.Path] = []
    file_log: List[str] = []  # per-file action lines printed in summary

    for src in raw_logs:
        if _is_file_open(src):
            file_log.append(f"  skip   {src.name}  (in use — skipping active log)")
            continue

        if src.stem.startswith("mangoapp"):
            csv_ts = _parse_mangoapp_timestamp(src.stem)
            if csv_ts and steam_sessions:
                csv_mtime = datetime.datetime.fromtimestamp(src.stat().st_mtime)
                detected = find_game_for_timestamp(
                    csv_ts, steam_sessions, steam_app_names, csv_end=csv_mtime
                )
                game = detected or "mangoapp"
            else:
                game = "mangoapp"
            if game != "mangoapp":
                suffix = src.name[len("mangoapp"):]
                target_name = game + suffix
                log.info("mangoapp CSV matched to '%s' via Steam session", game)
            else:
                target_name = src.name
        else:
            game = _resolve_game_name(_extract_game_name(src.stem), steam_app_names)
            target_name = src.name
        game_dir = dest / game
        target = game_dir / target_name

        if target.exists():
            skipped += 1
            file_log.append(f"  skip   {src.name}")
            # Only delete the original if it's not the same file as the target
            if src.resolve() != target.resolve():
                originals_to_delete.append(src)
            continue

        if dry:
            file_log.append(f"  copy   {src.name}  →  {game}/")
            moved += 1
            continue

        game_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(target))
        moved += 1
        originals_to_delete.append(src)
        renamed = target_name != src.name
        arrow = f"{src.name}  →  {game}/{target_name}" if renamed else f"{src.name}  →  {game}/"
        file_log.append(f"  copy   {arrow}")
        log.info("Copied: %s -> %s", src, target)

    if not dry:
        for src in originals_to_delete:
            try:
                src.unlink()
                deleted += 1
                log.info("Deleted original: %s", src)
            except OSError as e:
                log.warning("Could not delete %s: %s", src, e)

        # Delete MangoHud auto-generated summary CSVs from source dirs -- they
        # are noise (we compute our own summaries) and pile up indefinitely.
        for search_dir in ([pathlib.Path(args.source)] if args.source else
                           [MANGOHUD_LOG_DIR, MANGOHUD_TMP_LOG, MANGOHUD_ALT_LOG]):
            if not search_dir or not search_dir.is_dir():
                continue
            for p in search_dir.glob("*_summary.csv"):
                try:
                    p.unlink()
                    deleted += 1
                    log.info("Deleted summary file: %s", p)
                except OSError as e:
                    log.warning("Could not delete %s: %s", p, e)

    # Merge any misnamed game folders into their canonical Steam names.
    if not dry:
        for game_dir in sorted(dest.iterdir()):
            if not game_dir.is_dir():
                continue
            canonical = _resolve_game_name(game_dir.name, steam_app_names)
            if canonical == game_dir.name:
                continue
            canon_dir = dest / canonical
            canon_dir.mkdir(parents=True, exist_ok=True)
            for f in game_dir.iterdir():
                if f.is_symlink():
                    f.unlink()  # stale symlinks are rebuilt below
                    continue
                target = canon_dir / f.name
                if target.exists():
                    log.info("Merge skip (exists): %s", f)
                else:
                    f.rename(target)
                    log.info("Merged: %s -> %s", f, target)
            try:
                game_dir.rmdir()  # only removes if now empty
                print(f"  Merged folder: {game_dir.name}/ -> {canonical}/")
            except OSError:
                log.warning("Could not remove %s (not empty after merge)", game_dir)

    if not dry:
        for game_dir in sorted(dest.iterdir()):
            if not game_dir.is_dir():
                continue
            rotated += _rotate_game_logs(game_dir, max_logs)

            day_logs = sorted(
                [
                    f
                    for f in game_dir.glob("*.csv")
                    if today in f.name
                    and not f.name.endswith("_summary.csv")
                    and not f.name.endswith("-current-mangohud.csv")
                    and f.name != "current.csv"
                ],
                key=lambda p: p.stat().st_mtime,
            )
            game_name = game_dir.name
            current_name = f"{game_name}-current-mangohud.csv"
            current_link = game_dir / current_name
            non_link_csvs = [
                f
                for f in game_dir.glob("*.csv")
                if not f.name.endswith("-current-mangohud.csv")
                and not f.name.endswith("_summary.csv")
                and f.name != "current.csv"
            ]
            if day_logs:
                if current_link.is_symlink() or current_link.exists():
                    current_link.unlink()
                current_link.symlink_to(day_logs[-1].name)
                log.info("%s -> %s", current_name, day_logs[-1].name)
            elif not current_link.exists():
                all_csvs = sorted(non_link_csvs, key=lambda p: p.stat().st_mtime)
                if all_csvs:
                    current_link.symlink_to(all_csvs[-1].name)

    W = 72
    print(f"┌─ MangoHud Organize {'─' * (W - 20)}┐")
    print(f"│  {str(dest):<{W - 2}}│")
    print(f"└{'─' * W}┘")

    # ── Per-file actions ──────────────────────────────────────────────────
    if file_log:
        print()
        for line in file_log:
            print(line)

    # ── Totals ────────────────────────────────────────────────────────────
    print()
    print(f"  ─── Summary {'─' * (W - 12)}")
    parts = [
        f"Copied {moved}",
        f"Skipped {skipped}",
        f"Deleted {deleted}",
        f"Rotated {rotated}",
    ]
    print("  " + "  │  ".join(parts))

    # ── Per-game folder summary ───────────────────────────────────────────
    game_dirs = [p for p in sorted(dest.iterdir()) if p.is_dir()]
    if game_dirs:
        print()
        print(f"  ─── Games {'─' * (W - 10)}")
        name_w = max(len(p.name) for p in game_dirs)
        for game_dir in game_dirs:
            gn = game_dir.name
            real_csvs = sorted(
                [c for c in game_dir.glob("*.csv")
                 if not c.name.endswith("-current-mangohud.csv")
                 and not c.name.endswith("_summary.csv")
                 and not c.is_symlink()],
                key=lambda p: p.stat().st_mtime,
            )
            cur = game_dir / f"{gn}-current-mangohud.csv"
            if cur.is_symlink():
                cur_resolved = cur.resolve()
                cur_target = cur_resolved.name if cur_resolved.exists() else f"{cur.readlink().name} (missing)"
            else:
                cur_target = "—"
            count = len(real_csvs)
            label = f"{count} log{'s' if count != 1 else ''}"
            print(f"  {gn:<{name_w}}  {label:<8}  current: {cur_target}")

    print()
    return 0
