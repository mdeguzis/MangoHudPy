"""Global constants: paths, preset definitions, config keys."""
from __future__ import annotations

import os
import pathlib
from typing import Any, Dict

PROG_NAME = "mangohud-py"
VERSION = "1.0.3"

XDG_CONFIG = pathlib.Path(
    os.environ.get("XDG_CONFIG_HOME", pathlib.Path.home() / ".config")
)
XDG_DATA = pathlib.Path(
    os.environ.get("XDG_DATA_HOME", pathlib.Path.home() / ".local/share")
)

MANGOHUD_CONF_DIR = XDG_CONFIG / "MangoHud"
MANGOHUD_CONF_FILE = MANGOHUD_CONF_DIR / "MangoHud.conf"

# Standard MangoHud log/output paths for Bazzite/SteamOS
MANGOHUD_LOG_DIR = pathlib.Path.home() / "mangologs"
MANGOHUD_TMP_LOG = pathlib.Path("/tmp/MangoHud")
MANGOHUD_ALT_LOG = XDG_DATA / "MangoHud"
BENCH_LOG_DIR = MANGOHUD_LOG_DIR  # organized logs live alongside raw logs
CHART_BASE_DIR = pathlib.Path.home() / "mangohud-perf"
MAX_LOGS_PER_GAME = 15

# On Bazzite/SteamOS the gamescope session sets MANGOHUD_CONFIGFILE to a temp
# file managed by mangoapp.  This completely overrides MangoHud.conf and
# presets.conf (MANGOHUD_CONFIGFILE is highest priority).  mangoapp only writes
# display keys to that temp file -- logging keys are never applied.
# Fix: write MANGOHUD_CONFIG (applied on top of MANGOHUD_CONFIGFILE) with the
# logging keys to ~/.config/environment.d/ which gamescope-session-plus sources
# at startup before Steam launches.
MANGOHUD_ENV_CONF = XDG_CONFIG / "environment.d" / "mangohud-logging.conf"

# MangoHud config search order (highest priority first)
MANGOHUD_CONF_PATHS = [
    MANGOHUD_CONF_DIR / "MangoHud.conf",
    pathlib.Path.home()
    / ".var/app/com.valvesoftware.Steam/config/MangoHud/MangoHud.conf",
]

# Keys that MUST be in config for useful bottleneck analysis with mangoplot
BOTTLENECK_KEYS = {
    "cpu_stats": 1,
    "gpu_stats": 1,
    "core_load": 1,
    "gpu_core_clock": 1,
    "frametime": 1,
    "frame_timing": 1,
}

# Logging keys that must be present for CSV output
LOGGING_REQUIRED_KEYS = {
    "output_folder": str(MANGOHUD_LOG_DIR),
    "toggle_logging": "Shift_L+F2",
    "log_duration": 0,
    "log_interval": 100,
    "log_versioning": 1,
}

# FlightlessSomething web viewer
FLIGHTLESS_URL = "https://flightlesssomething.com/benchmarks/new"
FLIGHTLESS_BASE = "https://flightlesssomething.ambrosia.one"
FLIGHTLESS_UPLOAD_ENDPOINT = f"{FLIGHTLESS_BASE}/api/benchmarks"
FLIGHTLESS_TOKEN_FILE = pathlib.Path.home() / ".flightless-token"

WEB_VIEWERS = [
    {
        "name": "FlightlessMango Log Viewer",
        "url": "https://flightlessmango.com/games/new",
        "note": "Upload the CSV directly. Supports all MangoHud log columns.",
    },
    {
        "name": "CapFrameX Web Analysis",
        "url": "https://www.capframex.com/analysis",
        "note": "Accepts MangoHud CSVs since v1.7.",
    },
]

_LOGGING_VALS: Dict[str, Any] = {
    **LOGGING_REQUIRED_KEYS,
    "autostart_log": 0,
    "fps": 1,
    "frametime": 1,
    "frame_timing": 1,
    **BOTTLENECK_KEYS,
    "cpu_temp": 1,
    "cpu_power": 1,
    "cpu_mhz": 1,
    "gpu_stats": 1,
    "gpu_temp": 1,
    "gpu_power": 1,
    "gpu_mem_clock": 1,
    "gpu_mem_temp": 1,
    "vram": 1,
    "ram": 1,
    "swap": 1,
    "battery": 1,
    "battery_power": 1,
    "gamepad_battery": 1,
    "throttling_status": 1,
    "io_read": 0,
    "io_write": 0,
    "wine": 1,
    "winesync": 1,
    "procmem": 1,
    "engine_version": 1,
    "vulkan_driver": 1,
    "gpu_name": 1,
    "no_display": 0,
    "position": "top-left",
    "background_alpha": "0.4",
    "font_size": 20,
}

CONFIG_PRESETS: Dict[str, Dict[str, Any]] = {
    "logging": {
        "description": "Full CSV logging, minimal OSD -- best for data collection.",
        "values": dict(_LOGGING_VALS),
    },
    "minimal": {
        "description": "Lightweight HUD -- FPS + frametime only, no logging.",
        "values": {
            "fps": 1,
            "frametime": 1,
            "frame_timing": 1,
            "cpu_stats": 0,
            "gpu_stats": 0,
            "no_display": 0,
            "position": "top-left",
            "background_alpha": "0.3",
            "font_size": 18,
        },
    },
    "full": {
        "description": "Everything on OSD and all logging enabled.",
        "values": {
            **_LOGGING_VALS,
            "autostart_log": 1,
            "io_read": 1,
            "io_write": 1,
            "background_alpha": "0.5",
            "font_size": 22,
        },
    },
    "battery": {
        "description": "Power / battery metrics -- ideal for Steam Deck / handheld.",
        "values": {
            "output_folder": str(MANGOHUD_LOG_DIR),
            "log_duration": 0,
            "log_interval": 500,
            "log_versioning": 1,
            "autostart_log": 0,
            "fps": 1,
            "frametime": 1,
            "battery": 1,
            "battery_power": 1,
            "gamepad_battery": 1,
            "cpu_temp": 1,
            "cpu_power": 1,
            "gpu_temp": 1,
            "gpu_power": 1,
            "throttling_status": 1,
            "no_display": 0,
            "position": "top-right",
            "background_alpha": "0.35",
            "font_size": 18,
        },
    },
}

# ── Valve / SteamOS preset definitions ─────────────────────────────────
# mangoapp writes preset=N to MANGOHUD_CONFIGFILE when the Steam Performance
# slider changes.  The mapping is:
#   Slider Off  → preset=0  (MangoHud built-in: no display, no preset lookup)
#   Slider 1    → preset=1  (FPS only)
#   Slider 2    → preset=2  (Extended horizontal bar)
#   Slider 3    → preset=3  (Full detail)
#   Slider 4    → preset=4  (Full detail + extras, Bazzite extra level)
# preset=0 is handled internally by MangoHud (no_display).  We only need
# [preset 1]–[preset 4] in presets.conf.
_PRESET_LOGGING_KEYS: Dict[str, Any] = {
    "output_folder": str(MANGOHUD_LOG_DIR),
    "toggle_logging": "Shift_L+F2",
    "log_duration": 0,
    "log_interval": 100,
    "log_versioning": 1,
    "autostart_log": 1,
}

VALVE_PRESETS: Dict[int, Dict[str, Any]] = {
    1: {
        "description": "Valve preset 1 (FPS only) + logging",
        "values": {
            "legacy_layout": 0,
            "cpu_stats": 0,
            "gpu_stats": 0,
            "fps": 1,
            "fps_only": 1,
            "frametime": 0,
            **_PRESET_LOGGING_KEYS,
        },
    },
    2: {
        "description": "Valve preset 2 (extended) + logging",
        "values": {
            "legacy_layout": 0,
            "horizontal": 1,
            "hud_compact": 1,
            "gpu_stats": 1,
            "cpu_stats": 1,
            "fps": 1,
            "frametime": 1,
            "frame_timing": 1,
            "battery": 1,
            **_PRESET_LOGGING_KEYS,
        },
    },
    3: {
        "description": "Valve preset 3 (full detail) + logging",
        "values": {
            "legacy_layout": 0,
            "gpu_stats": 1,
            "cpu_stats": 1,
            "cpu_temp": 1,
            "gpu_temp": 1,
            "cpu_power": 1,
            "gpu_power": 1,
            "cpu_mhz": 1,
            "gpu_core_clock": 1,
            "gpu_mem_clock": 1,
            "vram": 1,
            "ram": 1,
            "fps": 1,
            "frametime": 1,
            "frame_timing": 1,
            "battery": 1,
            "battery_power": 1,
            "gamepad_battery": 1,
            "fan": 1,
            "throttling_status": 1,
            "wine": 1,
            "engine_version": 1,
            "vulkan_driver": 1,
            "gpu_name": 1,
            "core_load": 1,
            **_PRESET_LOGGING_KEYS,
        },
    },
    4: {
        "description": "Valve preset 4 (full detail + extras) + logging",
        "values": {
            "legacy_layout": 0,
            "gpu_stats": 1,
            "cpu_stats": 1,
            "cpu_temp": 1,
            "gpu_temp": 1,
            "cpu_power": 1,
            "gpu_power": 1,
            "cpu_mhz": 1,
            "gpu_core_clock": 1,
            "gpu_mem_clock": 1,
            "gpu_mem_temp": 1,
            "vram": 1,
            "ram": 1,
            "swap": 1,
            "fps": 1,
            "frametime": 1,
            "frame_timing": 1,
            "battery": 1,
            "battery_power": 1,
            "gamepad_battery": 1,
            "fan": 1,
            "throttling_status": 1,
            "wine": 1,
            "winesync": 1,
            "engine_version": 1,
            "vulkan_driver": 1,
            "gpu_name": 1,
            "core_load": 1,
            "procmem": 1,
            **_PRESET_LOGGING_KEYS,
        },
    },
}

STEAM_LOG_DIR = pathlib.Path.home() / ".local/share/Steam/logs"
STEAM_APPS_DIR = pathlib.Path.home() / ".local/share/Steam/steamapps"
# Flatpak Steam fallbacks
STEAM_FLATPAK_LOG_DIR = (
    pathlib.Path.home() / ".var/app/com.valvesoftware.Steam/.local/share/Steam/logs"
)
STEAM_FLATPAK_APPS_DIR = (
    pathlib.Path.home()
    / ".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps"
)

LOG_FMT = "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"

# Upload history file
UPLOAD_HISTORY_FILE = (
    pathlib.Path.home() / ".local" / "share" / "mango-hud-profiler" / "uploads.json"
)
