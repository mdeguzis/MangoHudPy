"""Bundle command: create a zip of logs for FlightlessSomething upload."""
from __future__ import annotations

import argparse
import datetime
import pathlib
import zipfile
from typing import List, Optional

from .constants import BENCH_LOG_DIR, FLIGHTLESS_URL, PROG_NAME
from .utils import _extract_game_name, find_logs, log


def cmd_bundle(args: argparse.Namespace) -> int:
    """Create a zip of selected logs for upload to FlightlessSomething."""
    game = getattr(args, "game", None)
    src_dir = pathlib.Path(args.source) if args.source else BENCH_LOG_DIR
    out: Optional[pathlib.Path] = pathlib.Path(args.output) if args.output else None

    csvs: List[pathlib.Path] = []
    if game:
        game_dir = src_dir / game
        if game_dir.is_dir():
            csvs = sorted(
                [f for f in game_dir.glob("*.csv") if f.name != "current.csv"],
                key=lambda p: p.stat().st_mtime,
            )
        else:
            csvs = find_logs(src_dir, game=game)
    else:
        if src_dir.is_dir():
            for gd in sorted(src_dir.iterdir()):
                if not gd.is_dir():
                    continue
                cur = gd / "current.csv"
                if cur.is_symlink() or cur.exists():
                    csvs.append(cur.resolve())
                else:
                    latest = sorted(
                        [f for f in gd.glob("*.csv")], key=lambda p: p.stat().st_mtime
                    )
                    if latest:
                        csvs.append(latest[-1])

    if not csvs:
        print("  No logs found to bundle.")
        print(f"    Source: {src_dir}")
        if game:
            print(f"    Game filter: {game}")
        print(f"\n    Run '{PROG_NAME} organize' first to sort logs into game folders.")
        return 1

    limit = args.limit
    if limit and len(csvs) > limit:
        csvs = csvs[-limit:]

    if not out:
        tag = game if game else "all-games"
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        out = src_dir / f"benchmark_{tag}_{ts}.zip"

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(out), "w", zipfile.ZIP_DEFLATED) as zf:
        for csv in csvs:
            zf.write(str(csv), csv.name)

    total_kb = sum(c.stat().st_size for c in csvs) / 1024
    zip_kb = out.stat().st_size / 1024

    print(f"  Bundle created: {out}")
    print(
        f"    Files : {len(csvs)} CSV(s) ({total_kb:.0f} KB -> {zip_kb:.0f} KB zipped)"
    )
    print("    Upload to FlightlessSomething:")
    print(f"      {FLIGHTLESS_URL}")
    print("      Select all CSVs from the zip (or upload the individual files).")
    print("\n    Included logs:")
    for c in csvs:
        print(f"      {c.name}  ({c.stat().st_size/1024:.1f} KB)")
    return 0
