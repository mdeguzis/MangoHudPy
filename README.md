# MangoHudPy

A MangoHud configurator, profiler, log manager, and uploader for Linux gaming.
Works on Bazzite, SteamOS (Steam Deck), and standard desktop Linux.

Upload benchmark logs to [FlightlessSomething](https://flightlesssomething.com)!

---

## Features

| Command | Description |
|---------|-------------|
| `launch-option` | TUI to set per-game Steam launch options for silent background logging (Bazzite / Steam Deck) |
| `configure` | Generate `MangoHud.conf` + `presets.conf` with logging keys (desktop Linux) |
| `profile` | Launch any command under MangoHud for a timed session with automatic summary |
| `graph` | Produce PNG/SVG charts from CSV logs (mangoplot preferred, matplotlib fallback) |
| `summary` | Human-readable stats: avg/min/max, percentiles, FPS stability score, frametime jitter |
| `games` | List unique game names found in your log files |
| `organize` | Sort raw logs into `~/mangologs/<GameName>/` with rotation and `current` symlinks |
| `bundle` | Zip logs for batch upload to FlightlessSomething |
| `upload` | Push CSVs to FlightlessSomething via API (interactive TUI file picker included) |
| `auto-organize` | Install a systemd timer to run `organize` automatically |
| `test` | Simulate the gamescope `MANGOHUD_CONFIGFILE` override and verify logging works |

---

## Installation

```bash
pip install mangohudpy
```

The `mangohud-py` command is available immediately after install.

With the optional desktop GUI (PySide6, dark-themed):

```bash
pip install "mangohudpy[gui]"
mangohud-py-gui
```

Or install everything at once:

```bash
pip install "mangohudpy[graphs,gui]"
```

---

## Desktop GUI

A PySide6 desktop companion app (`mangohud-py-gui`) complements the CLI.
Designed for **SteamOS / Bazzite desktop mode** at 1280×800 (Steam Deck native resolution).
Supports light and dark themes (File → Settings → Theme).

The GUI auto-detects Wayland when no `DISPLAY` is present (e.g. SSH sessions) and
sets `QT_QPA_PLATFORM=wayland` automatically.

### Pages

| Page | What it does |
|------|-------------|
| **Dashboard** | Per-game stat cards (avg FPS, 1% low, jitter, session count) with one-click Organize |
| **Organize** | Sort raw logs into `~/mangologs/<Game>/` — source/dest pickers, dry-run preview, systemd timer status |
| **Summary** | Pick a log file, view a full stats table (avg/min/max/percentiles) + FPS stability score |
| **Graphs** | Generate PNG/SVG charts inline — uses `mangoplot` if available, falls back to matplotlib; auto-loads existing charts; delete button |
| **Config** | Preset picker + editable key/value table, write `MangoHud.conf` or per-game configs |
| **Upload** | Token management, checkable file list with inferred titles, upload to FlightlessSomething |
| **Profile** | Launch any command under MangoHud with a timer and live output |
| **Launch Option** | Table of all Steam games — toggle MangoHud on/off per game, applies live via Steam CEF or writes `localconfig.vdf` |
| **Test** | Run `vkcube` or any command to verify MangoHud logging is working |

### Install & run

```bash
pip install "mangohudpy[gui]"
mangohud-py-gui
```

The GUI reuses the same logic as the CLI — no reimplemented code, no duplicated behaviour.

---

## Platform guide

---

### Bazzite (Game Mode)

On Bazzite, `gamescope-session` runs the **mangoapp** HUD stack. Before each game
launches, **mangopeel** writes a temp config to `MANGOHUD_CONFIGFILE=/tmp/mangohud.XXXXXX`
and `libMangoHud_shim.so` is LD_PRELOADed into the game — this shim is an IPC bridge
to mangoapp only; it **cannot write CSV logs**.

As a result:
- `MangoHud.conf` and `presets.conf` are **not respected** in Game Mode
- The Steam Performance slider controls display via mangoapp exclusively
- **The only supported logging method is the `launch-option` TUI**

```bash
mangohud-py launch-option
```

This injects a full MangoHud instance alongside the shim so frame data is written
continuously during gameplay. The injected overlay is made fully transparent so it
doesn't duplicate the mangoapp HUD:

```
MANGOHUD_CONFIG="autostart_log=1,output_folder=/home/gamer/mangologs,log_interval=100,log_versioning=1,log_duration=0,alpha=0.0,background_alpha=0.0" mangohud %command%
```

- `mangohud %command%` — required; hooks into the render loop for continuous frame capture
- `alpha=0.0,background_alpha=0.0` — makes the injected overlay fully invisible without
  disabling the render loop (the correct way to hide it; see pitfalls below)
- `autostart_log=1` — logging starts immediately on game launch, no keypress needed
- `output_folder` — flat path with **no spaces** (MANGOHUD_CONFIG is comma-parsed; spaces corrupt paths)
- Logs saved to `~/mangologs/` named by game exe, then sorted by `organize`

The TUI connects live to Steam's CEF debugger (no restart needed). Changes take effect
the next time the game is launched.

TUI keys: `SPACE` toggle, `a` toggle all, `u` apply + quit, `q` quit.

**Bazzite workflow:**

```bash
# 1. Set per-game launch options (run once, update any time)
mangohud-py launch-option

# 2. After gaming — sort logs into per-game folders
mangohud-py organize

# 3. Upload to FlightlessSomething
mangohud-py upload
```

#### How organize handles Bazzite logs

`organize` detects `mangoapp_*.csv` files (written by the hotkey logger) and matches
them to their game via Steam's `content_log.txt` session timestamps, with a 3-minute
pre-tolerance and overlap detection for games that take a long time to register as
"App Running". The file is then moved and renamed to the canonical Steam game name.

Files written by the injected `mangohud %command%` are named by the game executable
(e.g. `HorizonZeroDawnRemastered_2026-03-08_11-40-53.csv`) and are matched directly
without Steam session lookup.

---

### Steam Deck (SteamOS — Game Mode)

The Steam Deck uses the same `gamescope-session` + `mangoapp` mechanism as Bazzite.

**Two methods are available — use either or both:**

#### Method 1: `launch-option` TUI (per-game, works everywhere)

```bash
mangohud-py launch-option
```

Sets the same invisible MangoHud injection as Bazzite. Run from Desktop Mode
(CEF is available there). Changes take effect on next game launch.

**To set launch options manually** (without the TUI):
1. Switch to Desktop Mode
2. Right-click a game in Steam → Properties → Launch Options
3. Paste:
   ```
   MANGOHUD_CONFIG="autostart_log=1,output_folder=/home/deck/mangologs,log_interval=100,log_versioning=1,log_duration=0,alpha=0.0,background_alpha=0.0" mangohud %command%
   ```

#### Method 2: `presets.conf` (system-wide, simplest)

```bash
mangohud-py configure
```

On SteamOS, MangoHud is auto-injected into games when the Performance overlay is
active, which means `presets.conf` is read by the game process. This writes
`~/.config/MangoHud/presets.conf` with logging keys at all 4 preset levels — no
per-game setup needed.

---

### Desktop Linux (any distro)

On a standard desktop, `MangoHud.conf` and `presets.conf` are respected normally.
The `configure` command generates both files with logging keys pre-applied.

```bash
# Generate MangoHud.conf + presets.conf (logging at every Steam Performance slider position)
mangohud-py configure --preset logging

# Minimal HUD, no logging
mangohud-py configure --preset minimal

# Profile a specific binary for 2 minutes
mangohud-py profile --command "game-binary" --duration 120

# Set per-game Steam launch options via TUI (same as Bazzite)
mangohud-py launch-option
```

#### Config presets

| Preset    | Description |
|-----------|-------------|
| `logging` | Full CSV logging, minimal OSD — best for data collection |
| `minimal` | Lightweight HUD — FPS + frametime only, no logging |
| `full`    | Everything on OSD and all logging enabled (`autostart_log=1`) |
| `battery` | Power / battery metrics — ideal for handheld devices |

```bash
# Per-game config (Wine/Proton games)
mangohud-py configure --game Cyberpunk2077 --preset logging
# writes ~/.config/MangoHud/wine-Cyberpunk2077.conf

# Custom log output folder
mangohud-py configure --preset logging --log-dir /mnt/data/mangologs
```

#### `presets.conf` and the Steam Performance slider

`configure` also writes `~/.config/MangoHud/presets.conf`, which maps the Steam
Performance slider positions (1–4) to MangoHud display + logging configs. On desktop,
MangoHud reads this file normally, so logging activates at any slider position.

> On Bazzite Game Mode, `presets.conf` is not used — MangoHud is not auto-injected there. Use `launch-option` instead.

---

## Known pitfalls (Bazzite / SteamOS)

These were discovered through testing and caused regressions. Documented here so they
are not repeated.

### `no_display=1` kills the render loop → 1-frame CSVs

`no_display=1` does not merely hide the overlay — it disables MangoHud's render loop
hook entirely. The result is that only 1 frame of data is written (an exit-dump), no
matter how long the game ran.

**Do not use `no_display=1`.** To hide the injected overlay, use:
```
alpha=0.0,background_alpha=0.0
```
This makes the overlay fully transparent while keeping the render hook active, so CSVs
write one row per `log_interval` ms throughout the session.

### `mangohud %command%` is required — the shim cannot write CSVs

`libMangoHud_shim.so` (LD_PRELOADed by Steam on Bazzite/SteamOS) is an IPC bridge
to mangoapp only. Setting `autostart_log=1` via `MANGOHUD_CONFIG` without injecting
`mangohud %command%` only produces a 1-frame stats dump on game exit — not a
continuous frame log.

Always inject `mangohud %command%` in the launch option on mangoapp platforms.

### `env -u MANGOHUD_CONFIGFILE` breaks logging entirely

`MANGOHUD_CONFIGFILE` is set by mangopeel to the mangoapp IPC socket config path.
The shim uses this to connect. Unsetting it with `env -u MANGOHUD_CONFIGFILE`
destroys the IPC connection → MangoHud fails to initialize → no CSV is written at all.

Never include `env -u MANGOHUD_CONFIGFILE` in launch options.

### `output_folder` must have no spaces

`MANGOHUD_CONFIG` is parsed as comma-separated `key=value` pairs. A path containing
spaces (e.g. `output_folder=/home/gamer/mangologs/Horizon Zero Dawn Remastered`) is
split at the spaces, corrupting the path silently.

Always use the flat `~/mangologs/` as `output_folder`. The `organize` command handles
per-game sorting after the session.

---

## Summary and graphs

```bash
# Summarise the newest log
mangohud-py summary

# Summarise a specific log
mangohud-py summary --input ~/mangologs/MyGame_2026-03-05.csv

# JSON output (for scripting)
mangohud-py summary --input ~/mangologs/MyGame_2026-03-05.csv --json-output out.json

# Generate graphs (uses mangoplot if installed, otherwise matplotlib)
mangohud-py graph --input ~/mangologs/MyGame_2026-03-05.csv

# List all profiled games
mangohud-py games
```

---

## Organise and bundle

```bash
# Sort logs into ~/mangologs/<GameName>/ folders
mangohud-py organize

# Auto-organize on a systemd timer (every 30 min by default)
mangohud-py auto-organize

# Bundle a game's logs into a zip for upload
mangohud-py bundle --game Cyberpunk2077
```

---

## FlightlessSomething upload

```bash
# Store your API token once (get it from the site's /api-tokens page)
echo YOUR_TOKEN > ~/.flightless-token
chmod 600 ~/.flightless-token

# Interactive upload (TUI file picker)
mangohud-py upload

# Non-interactive upload for a specific game
mangohud-py upload --game Cyberpunk2077 -y

# Append runs to an existing benchmark
mangohud-py upload --append
```

---

## Log locations

| Path | Description |
|------|-------------|
| `~/mangologs/` | Default log output and organised per-game folders |
| `/tmp/MangoHud/` | MangoHud default temp log location |
| `~/.local/share/MangoHud/` | XDG data dir fallback |

---

## Development

### Quick setup

```bash
git clone https://github.com/mdeguzis/MangoHudPy
cd MangoHudPy
./dev-setup.sh
source .venv/bin/activate
```

`dev-setup.sh` installs [uv](https://astral.sh/uv) if needed, creates a `.venv`, and
installs the package in editable mode with all optional dependencies (`graphs` + `gui`).

### Manual setup (pip)

```bash
git clone https://github.com/mdeguzis/MangoHudPy
cd MangoHudPy

# CLI only
pip install -e .

# CLI + graphs
pip install -e ".[graphs]"

# CLI + GUI
pip install -e ".[gui]"

# Everything
pip install -e ".[graphs,gui]"
```

### Running from source

```bash
# Option A — activate the venv first
source .venv/bin/activate
mangohud-py --help
mangohud-py-gui

# Option B — run without activating (uv handles it)
uv run mangohud-py --help
uv run mangohud-py-gui

# Option C — run the entry point directly
python main.py --help
```

### Publishing to PyPI

```bash
./upload-to-pypi.sh           # build + upload to PyPI
./upload-to-pypi.sh --test    # build + upload to TestPyPI first
```

Requires `~/.pypirc` with a valid API token. See comments inside the script.

---

## Requirements

- Python 3.9+
- MangoHud installed (`mangohud` in PATH)
- `vdf` — required for `launch-option` (`pip install vdf`)
- `websocket-client` — required for CEF live injection in `launch-option` (`pip install websocket-client`)
- `matplotlib` — optional, for graph generation (`pip install "mangohudpy[graphs]"`)
- `mangoplot` — optional, preferred for graphs (ships with MangoHud on Bazzite)
- `PySide6` — optional, for the desktop GUI (`pip install "mangohudpy[gui]"`)
