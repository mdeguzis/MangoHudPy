"""CLI entry point: argument parser and main() function."""
from __future__ import annotations

import argparse
import sys
import textwrap
from typing import List, Optional

from .constants import (
    BENCH_LOG_DIR,
    CONFIG_PRESETS,
    MANGOHUD_CONF_FILE,
    MANGOHUD_LOG_DIR,
    MAX_LOGS_PER_GAME,
    FLIGHTLESS_BASE,
    PROG_NAME,
    VERSION,
)
from .utils import setup_logging, is_bazzite, is_steamos, mangohud_installed, log


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=PROG_NAME,
        description=(
            "MangoHud Performance Profiler for Bazzite / SteamOS.\n\n"
            "Configure MangoHud, launch profiling sessions, generate graphs\n"
            "from CSV logs, and produce summaries with web-viewer upload hints."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            f"""\
            examples:
              {PROG_NAME} configure --preset logging
              {PROG_NAME} profile --duration 120 --command "gamescope -- %command%"
              {PROG_NAME} graph --input /tmp/MangoHud/MyGame.csv
              {PROG_NAME} summary --input /tmp/MangoHud/MyGame.csv

            web viewers (upload your CSV):
              FlightlessMango : https://flightlessmango.com/games/new
              CapFrameX       : https://www.capframex.com/analysis

            version: {VERSION}
        """
        ),
    )
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {VERSION}")
    p.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v=INFO, -vv=DEBUG).",
    )
    p.add_argument(
        "--logfile", metavar="PATH", help="Also write log messages to this file."
    )
    sub = p.add_subparsers(
        dest="command",
        title="subcommands",
        description="Run '<subcommand> --help' for details.",
    )

    # ── configure ──────────────────────────────────────────────────────
    pc = sub.add_parser(
        "configure",
        help="Generate a MangoHud config file.",
        description=(
            "Generate or overwrite a MangoHud configuration file from a preset.\n"
            "Presets:\n"
            + "\n".join(
                f"  {k:10s} {v['description']}" for k, v in CONFIG_PRESETS.items()
            )
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pc.add_argument(
        "-p", "--preset",
        default="logging",
        choices=list(CONFIG_PRESETS.keys()),
        help="Config preset (default: logging).",
    )
    pc.add_argument(
        "-o", "--output",
        default=str(MANGOHUD_CONF_FILE),
        help=f"Output path (default: {MANGOHUD_CONF_FILE}).",
    )
    pc.add_argument(
        "--set",
        nargs="*",
        metavar="KEY=VAL",
        help="Override individual config keys (e.g. --set font_size=24 position=top-right).",
    )
    pc.add_argument(
        "--log-dir", metavar="DIR", help="Override the output_folder for CSV logs."
    )
    pc.add_argument(
        "-g", "--game",
        metavar="NAME",
        help="Generate a per-game config (writes to ~/.config/MangoHud/<NAME>.conf).",
    )
    pc.add_argument(
        "--check",
        action="store_true",
        help="Check existing config and add missing bottleneck/logging keys.",
    )
    pc.add_argument(
        "-f", "--force", action="store_true", help="Overwrite existing config file."
    )
    from .config import cmd_configure
    pc.set_defaults(func=cmd_configure)

    # ── profile ────────────────────────────────────────────────────────
    pp = sub.add_parser(
        "profile",
        help="Run a timed profiling session (launch, log, stop).",
        description=(
            "Launch a command with MangoHud, wait for the specified duration\n"
            "(or until the process exits / Ctrl-C), then stop and report.\n"
            "Optionally auto-generates graphs and/or a summary."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pp.add_argument("-c", "--command", required=True, help="The command to profile.")
    pp.add_argument(
        "-d", "--duration",
        type=float,
        default=60,
        help="Duration in seconds (default: 60).",
    )
    pp.add_argument(
        "--log-dir", metavar="DIR", help="Override the MangoHud log output directory."
    )
    pp.add_argument("--config", metavar="PATH", help="Path to a MangoHud config file.")
    pp.add_argument(
        "--auto-summary",
        action="store_true",
        default=True,
        help="Print summary after profiling (default: on).",
    )
    pp.add_argument(
        "--no-auto-summary",
        dest="auto_summary",
        action="store_false",
        help="Skip automatic summary.",
    )
    pp.add_argument(
        "--auto-graph",
        action="store_true",
        default=False,
        help="Generate graphs after profiling.",
    )
    pp.add_argument(
        "--graph-output", metavar="DIR", help="Directory for auto-generated graphs."
    )
    pp.add_argument(
        "--graph-format",
        default="png",
        choices=["png", "svg", "pdf"],
        help="Graph image format (default: png).",
    )
    from .profile import cmd_profile
    pp.set_defaults(func=cmd_profile)

    # ── graph ──────────────────────────────────────────────────────────
    pg = sub.add_parser(
        "graph",
        help="Generate graphs from MangoHud CSV logs (mangoplot or matplotlib).",
        description=textwrap.dedent(
            """\
            Generate performance charts from MangoHud CSV logs.

            By default uses mangoplot (ships with MangoHud on Bazzite/SteamOS)
            for the best bottleneck analysis. Falls back to matplotlib if
            mangoplot is unavailable.

            Charts are saved to ~/mangohud-perf/<GAME>/charts/
        """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pg.add_argument(
        "-i", "--input",
        metavar="CSV",
        help="Input CSV file (default: newest log in standard dirs).",
    )
    pg.add_argument(
        "-g", "--game",
        metavar="NAME",
        help="Filter: only use logs whose filename starts with NAME.",
    )
    pg.add_argument(
        "-o", "--output",
        metavar="DIR",
        help="Output directory for graphs (default: same as input).",
    )
    pg.add_argument(
        "-f", "--format",
        default="png",
        choices=["png", "svg", "pdf"],
        help="Image format (default: png).",
    )
    pg.add_argument("--dpi", type=int, default=150, help="Graph DPI (default: 150).")
    pg.add_argument(
        "--width", type=float, default=14.0, help="Graph width in inches (default: 14)."
    )
    pg.add_argument(
        "--height", type=float, default=6.0, help="Graph height in inches (default: 6)."
    )
    pg.add_argument(
        "--matplotlib",
        action="store_true",
        help="Force matplotlib backend even if mangoplot is available.",
    )
    from .graph import cmd_graph
    pg.set_defaults(func=cmd_graph)

    # ── summary ────────────────────────────────────────────────────────
    pm = sub.add_parser(
        "summary",
        help="Print a summary of MangoHud log file(s).",
        description=(
            "Parse one or more MangoHud CSV logs and print a human-readable\n"
            "summary with statistics (avg, min, max, percentiles) for FPS,\n"
            "frametime, thermals, power, and memory."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pm.add_argument(
        "-i", "--input",
        nargs="*",
        metavar="PATH",
        help="CSV file(s) or directory. Default: newest log.",
    )
    pm.add_argument(
        "-g", "--game",
        metavar="NAME",
        help="Filter: only summarise logs whose filename starts with NAME.",
    )
    pm.add_argument(
        "--json-output",
        metavar="PATH",
        help="Also write a machine-readable JSON summary to this file.",
    )
    from .summary import cmd_summary
    pm.set_defaults(func=cmd_summary)

    # ── games ──────────────────────────────────────────────────────────
    pl = sub.add_parser(
        "games",
        help="List game names found in MangoHud log files.",
        description=(
            "Scan the MangoHud log directory for CSV files and extract unique\n"
            "game names from filenames."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pl.add_argument(
        "--log-dir",
        metavar="DIR",
        help="Directory to scan (default: standard MangoHud log dirs).",
    )
    from .summary import cmd_games
    pl.set_defaults(func=cmd_games)

    # ── organize ───────────────────────────────────────────────────────
    po = sub.add_parser(
        "organize",
        help="Sort MangoHud logs into per-game folders with rotation.",
        description=textwrap.dedent(
            f"""\
            Copy MangoHud CSV logs from /tmp/MangoHud into an organised tree:

              ~/mangologs/
                Cyberpunk2077/
                  Cyberpunk2077_2026-02-22_14-30-00.csv
                  current.csv  ->  (symlink to today's newest)

            Rotation: keeps at most --max-logs per game (default {MAX_LOGS_PER_GAME}).
        """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    po.add_argument(
        "--source",
        metavar="DIR",
        help="Source directory for raw MangoHud logs (default: /tmp/MangoHud).",
    )
    po.add_argument(
        "--dest",
        metavar="DIR",
        default=str(BENCH_LOG_DIR),
        help=f"Destination root (default: {BENCH_LOG_DIR}).",
    )
    po.add_argument(
        "--max-logs",
        type=int,
        default=MAX_LOGS_PER_GAME,
        help=f"Max CSV files per game before oldest are deleted (default: {MAX_LOGS_PER_GAME}).",
    )
    po.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without copying/deleting.",
    )
    from .organize import cmd_organize
    po.set_defaults(func=cmd_organize)

    # ── launch-option ──────────────────────────────────────────────────
    plo = sub.add_parser(
        "launch-option",
        help="TUI to set per-game Steam mangohud launch options via localconfig.vdf.",
        description=textwrap.dedent(
            f"""\
            Interactive TUI: browse your Steam library, toggle mangohud auto-logging
            per game, and write the launch option directly into localconfig.vdf.

            The injected launch option sets autostart_log=1 scoped only to that
            game process — mangoapp is unaffected so the perf slider keeps working.

            Controls:
              Type      filter game list
              Up/Down   navigate
              Space     toggle mangohud for selected game
              u         apply changes and quit
              q         quit without saving
              Esc       clear filter

            Game Mode: changes take effect immediately but are lost when Steam restarts.
            Desktop Mode: changes persist across Steam restarts.
        """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    plo.add_argument(
        "--log-dir",
        metavar="DIR",
        help=f"Override log output directory (default: {MANGOHUD_LOG_DIR}).",
    )
    from .launch import cmd_launch_option
    plo.set_defaults(func=cmd_launch_option)

    # ── auto-organize ──────────────────────────────────────────────────
    pao = sub.add_parser(
        "auto-organize",
        help="Install/remove a systemd timer that runs organize automatically.",
        description=textwrap.dedent(
            """\
            Install a systemd user service + timer that runs 'organize'
            periodically to keep logs sorted and summary CSVs cleaned up.

            Runs 2 minutes after login, then on the configured interval.

            Examples:
              mangohud-py auto-organize            # enable (default: every 30 min)
              mangohud-py auto-organize --interval 15
              mangohud-py auto-organize --disable
        """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pao.add_argument(
        "--interval",
        type=int,
        default=30,
        metavar="MIN",
        help="How often to run organize, in minutes (default: 30).",
    )
    pao.add_argument(
        "--disable",
        action="store_true",
        help="Stop and remove the auto-organize timer.",
    )
    from .config import cmd_auto_organize
    pao.set_defaults(func=cmd_auto_organize)

    # ── bundle ─────────────────────────────────────────────────────────
    pb = sub.add_parser(
        "bundle",
        help="Create a zip of logs for FlightlessSomething upload.",
        description=textwrap.dedent(
            f"""\
            Package selected MangoHud CSV logs into a zip file ready for
            batch upload to FlightlessSomething.

            Workflow:
              1. Play games (MangoHud logs automatically)
              2. {PROG_NAME} organize
              3. {PROG_NAME} bundle
              4. Upload the zip to FlightlessSomething
        """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pb.add_argument("-g", "--game", metavar="NAME", help="Bundle only logs for this game.")
    pb.add_argument(
        "--source",
        metavar="DIR",
        default=str(BENCH_LOG_DIR),
        help=f"Source directory (default: {BENCH_LOG_DIR}).",
    )
    pb.add_argument(
        "-o", "--output",
        metavar="ZIP",
        help="Output zip path (default: auto-named in source dir).",
    )
    pb.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of CSVs to include (newest first).",
    )
    from .bundle import cmd_bundle
    pb.set_defaults(func=cmd_bundle)

    # ── upload ─────────────────────────────────────────────────────────
    pu = sub.add_parser(
        "upload",
        help="Upload logs to FlightlessSomething via API.",
        description=textwrap.dedent(
            f"""\
            Upload MangoHud CSV logs directly to FlightlessSomething.

            Requires an API token:
              1. Log in at {FLIGHTLESS_BASE}
              2. Go to /api-tokens and create a token
              3. Store it: echo YOUR_TOKEN > ~/.flightless-token && chmod 600 ~/.flightless-token
              Token lookup order: --token > FLIGHTLESS_TOKEN env > ~/.flightless-token
        """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pu.add_argument(
        "-t", "--token",
        metavar="TOKEN",
        help="FlightlessSomething API token.",
    )
    pu.add_argument(
        "--append",
        action="store_true",
        help="Append runs to an existing benchmark instead of creating a new one.",
    )
    pu.add_argument(
        "--force",
        action="store_true",
        help="Allow re-uploading files already present in the benchmark.",
    )
    pu.add_argument("-g", "--game", metavar="NAME", help="Upload only logs for this game.")
    pu.add_argument(
        "-i", "--input",
        nargs="*",
        metavar="PATH",
        help="Specific CSV file(s) or directories to upload.",
    )
    pu.add_argument(
        "--source",
        metavar="DIR",
        default=str(BENCH_LOG_DIR),
        help=f"Source directory for organized logs (default: {BENCH_LOG_DIR}).",
    )
    pu.add_argument("--title", metavar="TEXT", help="Benchmark title (default: auto-generated).")
    pu.add_argument("--description", metavar="TEXT", help="Benchmark description.")
    pu.add_argument(
        "--url",
        metavar="URL",
        help=f"FlightlessSomething base URL (default: {FLIGHTLESS_BASE}).",
    )
    pu.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of CSVs to upload (newest first).",
    )
    pu.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt.")
    from .upload import cmd_upload
    pu.set_defaults(func=cmd_upload)

    # ── test ───────────────────────────────────────────────────────────
    pt = sub.add_parser(
        "test",
        help="Verify MangoHud logging works (simulates gamescope MANGOHUD_CONFIGFILE override).",
        description=(
            "Simulate the gamescope-session environment and confirm that logging\n"
            "keys from MANGOHUD_CONFIG survive the MANGOHUD_CONFIGFILE override."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pt.add_argument(
        "--log-dir",
        metavar="DIR",
        help=f"Log output dir to test (default: {MANGOHUD_LOG_DIR}).",
    )
    pt.add_argument(
        "--duration",
        type=int,
        default=5,
        metavar="SECS",
        help="How long to run the renderer (default: 5s).",
    )
    pt.add_argument(
        "--live",
        action="store_true",
        help="Build MANGOHUD_CONFIG from constants rather than reading the installed env.d file.",
    )
    from .test_cmd import cmd_test
    pt.set_defaults(func=cmd_test)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose, getattr(args, "logfile", None))

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    log.debug(
        "OS detection: bazzite=%s steamos=%s mangohud=%s",
        is_bazzite(),
        is_steamos(),
        mangohud_installed(),
    )
    return args.func(args)
