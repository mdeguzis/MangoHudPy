"""Organize command: sort MangoHud logs into per-game folders with rotation."""
from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import shutil
from typing import List, Optional

from .constants import BENCH_LOG_DIR, MANGOHUD_ALT_LOG, MANGOHUD_LOG_DIR, MANGOHUD_TMP_LOG, MAX_LOGS_PER_GAME
from .utils import (
    _extract_game_name,
    find_game_for_timestamp,
    find_logs,
    load_steam_app_names,
    log,
    parse_steam_game_sessions,
)


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
    csvs = sorted(game_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime)
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

    # Load Steam session data once for mangoapp CSV renaming.
    steam_sessions = parse_steam_game_sessions()
    steam_app_names = load_steam_app_names() if steam_sessions else {}

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

    for src in raw_logs:
        if src.stem.startswith("mangoapp"):
            csv_ts = _parse_mangoapp_timestamp(src.stem)
            if csv_ts and steam_sessions:
                detected = find_game_for_timestamp(csv_ts, steam_sessions, steam_app_names)
                game = detected or "mangoapp"
            else:
                game = "mangoapp"
            if game != "mangoapp":
                # Rename: swap "mangoapp" prefix for the detected game name.
                suffix = src.name[len("mangoapp"):]  # e.g. "_2026-03-07_16-15-37.csv"
                target_name = game + suffix
                log.info("mangoapp CSV matched to '%s' via Steam session", game)
            else:
                target_name = src.name
        else:
            game = _extract_game_name(src.stem)
            target_name = src.name
        game_dir = dest / game
        target = game_dir / target_name

        if target.exists():
            skipped += 1
            originals_to_delete.append(src)
            continue

        if dry:
            print(f"    [dry-run] {src.name} -> {game_dir}/")
            moved += 1
            continue

        game_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(target))
        moved += 1
        originals_to_delete.append(src)
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

    print(f"  Organize complete: {dest}")
    print(f"    Copied  : {moved} log(s)")
    print(f"    Skipped : {skipped} (already exist)")
    print(f"    Deleted : {deleted} original(s) from source")
    print(f"    Rotated : {rotated} old log(s) deleted (max {max_logs}/game)")

    for game_dir in sorted(dest.iterdir()):
        if not game_dir.is_dir():
            continue
        csvs = sorted(game_dir.glob("*.csv"))
        gn = game_dir.name
        real_csvs = [c for c in csvs if not c.name.endswith("-current-mangohud.csv")]
        cur = game_dir / f"{gn}-current-mangohud.csv"
        cur_target = cur.resolve().name if cur.is_symlink() else "none"
        print(f"    {game_dir.name}/  ({len(real_csvs)} logs, current -> {cur_target})")
    return 0
