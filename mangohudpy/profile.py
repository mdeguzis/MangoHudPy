"""Profile command: launch a timed MangoHud profiling session."""
from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import time

from .constants import MANGOHUD_LOG_DIR
from .utils import find_logs, hdur, log, mangohud_installed


def cmd_profile(args: argparse.Namespace) -> int:
    if not mangohud_installed():
        log.error("MangoHud not found.")
        return 1
    cmd = args.command
    dur = args.duration
    ld = pathlib.Path(args.log_dir) if args.log_dir else MANGOHUD_LOG_DIR
    ld.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["MANGOHUD"] = "1"
    env["MANGOHUD_LOG"] = "1"
    env["MANGOHUD_OUTPUT"] = str(ld)
    if args.config:
        env["MANGOHUD_CONFIGFILE"] = str(args.config)
    full = ["mangohud"] + cmd.split()
    print(
        f"  Profiling for {hdur(dur)}:\n    Command: mangohud {cmd}\n    Log dir: {ld}\n"
    )
    before = set(find_logs(ld))
    try:
        proc = subprocess.Popen(full, env=env)
    except FileNotFoundError:
        log.error("Launch failed.")
        return 1
    t0 = time.monotonic()
    try:
        proc.wait(timeout=dur)
        el = time.monotonic() - t0
        print(f"\n  Exited after {hdur(el)}")
    except subprocess.TimeoutExpired:
        el = time.monotonic() - t0
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        print(f"\n  Session ended after {hdur(el)}")
    except KeyboardInterrupt:
        el = time.monotonic() - t0
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        print(f"\n  Interrupted after {hdur(el)}")
    time.sleep(0.5)
    new = sorted(set(find_logs(ld)) - before)
    if new:
        print("\n  New log file(s):")
        for f in new:
            print(f"    {f}  ({f.stat().st_size/1024:.1f} KB)")
        if args.auto_summary:
            from .summary import _print_summary
            print()
            for logf in new:
                _print_summary(logf)
        if args.auto_graph:
            from .graph import _gen_graphs
            print()
            od = pathlib.Path(args.graph_output) if args.graph_output else new[0].parent
            for logf in new:
                _gen_graphs(logf, od, fmt=args.graph_format)
    else:
        print(f"\n  No new logs found. Check config. Expected dir: {ld}")
    return 0
