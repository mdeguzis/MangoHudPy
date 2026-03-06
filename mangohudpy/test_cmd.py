"""Test command: verify MangoHud logging works by simulating the gamescope environment."""
from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import tempfile
import time

from .constants import MANGOHUD_ENV_CONF, MANGOHUD_LOG_DIR
from .utils import find_logs, is_steamos, log, mangohud_installed, parse_csv


def cmd_test(args: argparse.Namespace) -> int:
    """Simulate the gamescope MANGOHUD_CONFIGFILE override and verify logging.

    Reproduces exactly what gamescope-session-plus does:
      1. Create a temp MANGOHUD_CONFIGFILE containing only "no_display"
      2. Set MANGOHUD_CONFIG from our environment.d file (or build it live)
      3. Run a short renderer session with autostart_log so a CSV is written
      4. Confirm the log appeared in output_folder

    This validates the fix for Bazzite where MANGOHUD_CONFIGFILE overrides
    MangoHud.conf/presets.conf and logging keys would otherwise be lost.
    """
    if not mangohud_installed():
        log.error("MangoHud not found in PATH.")
        return 1

    display = os.environ.get("DISPLAY", "")
    if not display:
        for candidate in (":0", ":1"):
            xsock = pathlib.Path(f"/tmp/.X11-unix/X{candidate.lstrip(':')}")
            if xsock.exists():
                display = candidate
                break
    if not display:
        log.error(
            "No X display found. Run from within the gamescope session or set DISPLAY."
        )
        return 1

    renderer = None
    use_mangohud_wrapper = False
    for prog in ("vkcube", "vkcube-wayland"):
        if shutil.which(prog):
            renderer = prog
            break
    if not renderer and shutil.which("glxgears"):
        renderer = "glxgears"
        use_mangohud_wrapper = True
    if not renderer:
        log.error(
            "No test renderer found (tried: vkcube, glxgears). "
            "Install vulkan-tools or mesa-demos."
        )
        return 1

    log_dir = pathlib.Path(args.log_dir) if args.log_dir else MANGOHUD_LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)

    if MANGOHUD_ENV_CONF.exists() and not args.live:
        raw = MANGOHUD_ENV_CONF.read_text(encoding="utf-8")
        mangohud_config = ""
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("MANGOHUD_CONFIG="):
                mangohud_config = line.split("=", 1)[1].strip().strip('"')
                break
        if not mangohud_config:
            log.warning("Could not parse MANGOHUD_CONFIG from %s", MANGOHUD_ENV_CONF)
    else:
        mangohud_config = None

    if not mangohud_config:
        logging_keys = {
            "output_folder": str(log_dir),
            "toggle_logging": "Shift_L+F2",
            "log_duration": "0",
            "log_interval": "100",
            "log_versioning": "1",
        }
        mangohud_config = ",".join(f"{k}={v}" for k, v in logging_keys.items())

    dur = args.duration
    parts = [
        p for p in mangohud_config.split(",")
        if not p.startswith("output_folder=")
        and not p.startswith("autostart_log=")
        and not p.startswith("log_duration=")
    ]
    parts += [
        f"output_folder={log_dir}",
        "autostart_log=1",
        f"log_duration={dur}",
    ]
    mangohud_config = ",".join(parts)

    with tempfile.NamedTemporaryFile(
        prefix="mangohud.", dir="/tmp", mode="w", suffix="", delete=False
    ) as tf:
        tf.write("no_display\n")
        fake_configfile = tf.name

    cmd = (["mangohud", renderer] if use_mangohud_wrapper else [renderer])
    print("  MangoHud logging test")
    print(f"    Display         : {display}")
    print(f"    Renderer        : {' '.join(cmd)}")
    print(f"    Log dir         : {log_dir}")
    print(f"    Duration        : {dur}s")
    print(f"    Fake CONFIGFILE : {fake_configfile}  (no_display -- like gamescope)")
    print(f"    MANGOHUD_CONFIG : {mangohud_config}")
    print()

    env = dict(os.environ)
    env["DISPLAY"] = display
    env["MANGOHUD"] = "1"
    env["MANGOHUD_CONFIGFILE"] = fake_configfile
    env["MANGOHUD_CONFIG"] = mangohud_config

    before = set(find_logs(log_dir))
    try:
        proc = subprocess.Popen(
            cmd, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        log.error("Failed to launch %s", renderer)
        pathlib.Path(fake_configfile).unlink(missing_ok=True)
        return 1

    try:
        proc.wait(timeout=dur + 3)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    pathlib.Path(fake_configfile).unlink(missing_ok=True)
    time.sleep(0.5)

    new = sorted(set(find_logs(log_dir)) - before)
    if new:
        print("  PASS -- log file(s) created:")
        for f in new:
            _, rows = parse_csv(f)
            print(f"    {f}  ({f.stat().st_size / 1024:.1f} KB, {len(rows)} rows)")
        if not is_steamos():
            print("\n  Note: not a SteamOS/Bazzite system -- gamescope session fix")
            print("  not required, but the logging mechanism works correctly.")
        return 0
    else:
        print("  FAIL -- no log file appeared in:", log_dir)
        print("    Check that MangoHud is properly installed and DISPLAY is reachable.")
        if not MANGOHUD_ENV_CONF.exists():
            print(f"\n    {MANGOHUD_ENV_CONF} not found.")
            print("    Run: mango-hud-profiler configure --preset logging")
        return 1
