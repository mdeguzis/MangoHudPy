"""Summary and games commands: parse CSV logs and print statistics."""
from __future__ import annotations

import argparse
import json
import pathlib
from typing import Any, Dict, List, Optional

from .constants import MANGOHUD_ALT_LOG, MANGOHUD_LOG_DIR, WEB_VIEWERS
from .utils import (
    _fcol,
    detect_os,
    discover_games,
    find_logs,
    is_bazzite,
    is_steamos,
    log,
    newest_log,
    parse_csv,
    pctl,
    sf,
)


def _print_summary(path: pathlib.Path) -> None:
    cols, rows = parse_csv(path)
    if not rows:
        print(f"  Summary: {path.name} -- no data rows.")
        return

    n = len(rows)
    info = detect_os()
    print("=" * 72)
    print(f"  MANGOHUD LOG SUMMARY: {path.name}")
    print("=" * 72)
    print(f"  File       : {path}")
    print(f"  Size       : {path.stat().st_size / 1024:.1f} KB")
    print(f"  Samples    : {n}")
    print(f"  OS         : {info.get('PRETTY_NAME', 'Unknown')}")
    if is_bazzite():
        print("  Platform   : Bazzite (SteamOS derivative)")
    elif is_steamos():
        print("  Platform   : SteamOS derivative")
    print()

    def _stat(key_cands: List[str], label: str, unit: str = "") -> None:
        k = _fcol(cols, key_cands)
        if not k:
            return
        vs = sorted([sf(r.get(k, "0")) for r in rows])
        if not vs or max(vs) == 0:
            return
        avg = sum(vs) / len(vs)
        print(
            f"  {label:20s}  avg={avg:8.1f}{unit}  "
            f"min={vs[0]:.1f}  max={vs[-1]:.1f}  "
            f"1%={pctl(vs,1):.1f}  5%={pctl(vs,5):.1f}  "
            f"95%={pctl(vs,95):.1f}  99%={pctl(vs,99):.1f}"
        )

    print("  --- Performance ---")
    _stat(["fps", "FPS"], "FPS", " fps")
    _stat(["frametime", "frametime_ms", "Frametime"], "Frame Time", " ms")
    print("\n  --- Thermals ---")
    _stat(["cpu_temp", "CPU_Temp"], "CPU Temp", " C")
    _stat(["gpu_temp", "GPU_Temp"], "GPU Temp", " C")
    print("\n  --- Power ---")
    _stat(["cpu_power", "CPU_Power"], "CPU Power", " W")
    _stat(["gpu_power", "GPU_Power"], "GPU Power", " W")
    _stat(["battery_power"], "Battery Power", " W")
    print("\n  --- Memory ---")
    _stat(["ram", "RAM"], "RAM", " MB")
    _stat(["vram", "VRAM"], "VRAM", " MB")
    _stat(["swap"], "Swap", " MB")

    fk = _fcol(cols, ["fps", "FPS"])
    if fk:
        fv = [sf(r.get(fk, "0")) for r in rows]
        avg = sum(fv) / len(fv) if fv else 0
        if avg > 0:
            stab = (1 - (sum((v - avg) ** 2 for v in fv) / len(fv)) ** 0.5 / avg) * 100
            print(f"\n  FPS Stability : {max(0,stab):.1f}%  (100%=perfectly stable)")

    ftk = _fcol(cols, ["frametime", "frametime_ms", "Frametime"])
    if ftk:
        tv = sorted([sf(r.get(ftk, "0")) for r in rows])
        if tv:
            p99 = pctl(tv, 99)
            p1 = pctl(tv, 1)
            jitter = p99 - p1
            print(f"  Frametime Jitter (P99-P1): {jitter:.2f} ms")

    print("\n  --- Upload to Web Viewers ---")
    print(f"  Log file for upload: {path}")
    for v in WEB_VIEWERS:
        print(f"    * {v['name']}: {v['url']}")
        print(f"      {v['note']}")
    print("=" * 72)
    print()


def _write_json_summary(paths: List[pathlib.Path], out: pathlib.Path) -> None:
    results = []
    for path in paths:
        cols, rows = parse_csv(path)
        if not rows:
            continue
        entry: Dict[str, Any] = {"file": str(path), "samples": len(rows)}
        for cands, key in [
            (["fps", "FPS"], "fps"),
            (["frametime", "frametime_ms"], "frametime"),
            (["cpu_temp", "CPU_Temp"], "cpu_temp"),
            (["gpu_temp", "GPU_Temp"], "gpu_temp"),
            (["cpu_power", "CPU_Power"], "cpu_power"),
            (["gpu_power", "GPU_Power"], "gpu_power"),
            (["ram", "RAM"], "ram"),
            (["vram", "VRAM"], "vram"),
        ]:
            k = _fcol(cols, cands)
            if k:
                vs = sorted([sf(r.get(k, "0")) for r in rows])
                if vs and max(vs) > 0:
                    entry[key] = {
                        "avg": round(sum(vs) / len(vs), 2),
                        "min": round(vs[0], 2),
                        "max": round(vs[-1], 2),
                        "p1": round(pctl(vs, 1), 2),
                        "p99": round(pctl(vs, 99), 2),
                    }
        results.append(entry)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"  JSON summary written: {out}")


def cmd_summary(args: argparse.Namespace) -> int:
    game = getattr(args, "game", None)
    paths: List[pathlib.Path] = []
    if args.input:
        for p in args.input:
            pp = pathlib.Path(p)
            if pp.is_file():
                paths.append(pp)
            elif pp.is_dir():
                paths.extend(find_logs(pp, game=game))
            else:
                log.warning("Not found: %s", pp)
    else:
        if game:
            paths = find_logs(game=game)
        else:
            nl = newest_log()
            if nl:
                paths.append(nl)
    if not paths:
        log.error(
            "No log files found.%s", f" (filtered by game '{game}')" if game else ""
        )
        return 1
    for p in paths:
        _print_summary(p)
    if args.json_output:
        _write_json_summary(paths, pathlib.Path(args.json_output))
    return 0


def cmd_games(args: argparse.Namespace) -> int:
    """List unique game names discovered from MangoHud log filenames."""
    d = pathlib.Path(args.log_dir) if args.log_dir else None
    names = discover_games(d)
    if not names:
        print("  No MangoHud logs found.")
        print(f"    Searched: {MANGOHUD_LOG_DIR}, {MANGOHUD_ALT_LOG}")
        return 1
    print(f"  Games found in MangoHud logs ({len(names)}):\n")
    for n in names:
        count = len(find_logs(d, game=n))
        print(f"    {n:30s}  ({count} log{'s' if count != 1 else ''})")
    print("\n  Use --game NAME with configure/graph/summary to target a specific game.")
    return 0
