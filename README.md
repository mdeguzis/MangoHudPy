# MangoHudPy

A fully-featured MangoHud configurator, profiler, grapher, and log manager for SteamOS / Bazzite.
Upload seamlessly to FlightlessSomething!

## Features

- **configure** — generate a `MangoHud.conf` from presets (`logging`, `minimal`, `full`, `battery`); injects logging keys into all 4 Valve overlay presets; fixes the Bazzite/SteamOS `MANGOHUD_CONFIGFILE` override via `~/.config/environment.d/`
- **profile** — launch any command under MangoHud for a timed session with automatic summary/graphs
- **graph** — produce PNG/SVG charts from CSV logs (uses `mangoplot` when available, falls back to `matplotlib`)
- **summary** — human-readable stats (avg, min, max, percentiles) with FPS stability score and frametime jitter
- **games** — list unique game names found in your log files
- **organize** — sort raw logs into `~/mangologs/<GameName>/` with rotation and `current` symlinks
- **bundle** — zip logs for batch upload to FlightlessSomething
- **upload** — push CSVs directly to FlightlessSomething via API (interactive TUI file picker included)
- **test** — simulate the gamescope `MANGOHUD_CONFIGFILE` override and confirm logging works

## Installation

```bash
pip install mangohudpy
```

With optional graph support (matplotlib):

```bash
pip install "mangohudpy[graphs]"
```

The `mangohud-py` command will be available immediately after install.

## Usage

```
mangohud-py --help
mangohud-py <subcommand> --help
```

### Quick examples

```bash
# Generate a MangoHud config with full logging enabled
mangohud-py configure --preset logging

# Profile a game for 2 minutes
mangohud-py profile --command "game-binary" --duration 120

# Summarise the newest log
mangohud-py summary

# Summarise a specific log with JSON output
mangohud-py summary --input ~/mangologs/MyGame_2026-03-05.csv --json-output out.json

# Generate graphs (uses mangoplot if installed, otherwise matplotlib)
mangohud-py graph --input ~/mangologs/MyGame_2026-03-05.csv

# List games that have been profiled
mangohud-py games

# Organise raw logs into per-game folders
mangohud-py organize

# Bundle current logs into a zip for upload
mangohud-py bundle --game Cyberpunk2077

# Upload to FlightlessSomething (interactive TUI picker)
mangohud-py upload

# Append runs to an existing benchmark
mangohud-py upload --append

# Verify logging works on Bazzite/SteamOS
mangohud-py test
```

### Config presets

| Preset    | Description |
|-----------|-------------|
| `logging` | Full CSV logging, minimal OSD — best for data collection |
| `minimal` | Lightweight HUD — FPS + frametime only, no logging |
| `full`    | Everything on OSD and all logging enabled |
| `battery` | Power / battery metrics — ideal for Steam Deck / handheld |

### Per-game configs

```bash
mangohud-py configure --game Cyberpunk2077 --preset logging
# writes ~/.config/MangoHud/wine-Cyberpunk2077.conf
```

### FlightlessSomething upload

```bash
# Store your API token once (get it from the site's /api-tokens page)
echo YOUR_TOKEN > ~/.flightless-token
chmod 600 ~/.flightless-token

# Upload (interactive: TUI picker lets you select files)
mangohud-py upload

# Non-interactive upload for a specific game
mangohud-py upload --game Cyberpunk2077 -y
```

## Bazzite / SteamOS note

On Bazzite, `gamescope-session-plus` sets `MANGOHUD_CONFIGFILE` to a temp file managed by
`mangoapp`, which overrides `MangoHud.conf` and `presets.conf`. The `configure` command works
around this by writing logging keys to `~/.config/environment.d/mangohud-logging.conf` via
`MANGOHUD_CONFIG`, which is applied *on top* of `MANGOHUD_CONFIGFILE`.

**Re-login to your gamescope session after running `configure` for the changes to take effect.**

## Log locations

| Path | Description |
|------|-------------|
| `~/mangologs/` | Default log output and organised game folders |
| `/tmp/MangoHud/` | MangoHud default temp log location |
| `~/.local/share/MangoHud/` | XDG data dir fallback |

## Requirements

- Python 3.9+
- MangoHud installed (`mangohud` in PATH)
- `matplotlib` — optional, for graph generation (`pip install -e ".[graphs]"`)
- `mangoplot` — optional, preferred for graphs (ships with MangoHud on Bazzite)
