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

On Bazzite, `gamescope-session` sets `MANGOHUD_CONFIGFILE` to a temp file owned by
`mangoapp`. This means `MangoHud.conf` and `presets.conf` are **not respected** for
games in Game Mode — `mangoapp` controls the visual overlay exclusively via the Steam
Performance slider.

**The only supported logging method on Bazzite is the `launch-option` TUI.**

```bash
mangohud-py launch-option
```

This sets a per-game Steam launch option that runs MangoHud silently in the background:

```
MANGOHUD_CONFIG="autostart_log=1,output_folder=~/mangologs,log_interval=100,
log_versioning=1,log_duration=0,no_display=1" mangohud %command%
```

- `no_display=1` — no overlay; the Steam Performance slider still controls display via `mangoapp`
- `autostart_log=1` — logging starts immediately on game launch, no keypress needed
- Logs saved to `~/mangologs/` and named by game automatically

The TUI connects live to Steam's CEF debugger (no restart needed). Changes take effect
the next time the game is launched.

TUI keys: `SPACE` toggle, `a` toggle all, `s` show/hide current launch option, `u` apply + quit, `q` quit.

**Bazzite workflow:**

```bash
# 1. Set per-game launch options (run once, update any time)
mangohud-py launch-option

# 2. After gaming — sort logs into per-game folders
mangohud-py organize

# 3. Upload to FlightlessSomething
mangohud-py upload
```

---

### Steam Deck (SteamOS — Game Mode)

The Steam Deck uses the same `gamescope-session` + `mangoapp` mechanism as Bazzite,
but differs in one important way: **SteamOS auto-injects MangoHud into games** when the
Performance overlay is active. This means `presets.conf` is read by the game process and
logging works without any per-game launch option.

**Two methods are available — use either or both:**

#### Method 1: `presets.conf` (simplest — works system-wide)

```bash
mangohud-py configure
```

This writes `~/.config/MangoHud/presets.conf` with logging keys injected into all 4
Valve preset levels. With the Performance slider at position 1–4, MangoHud logs
automatically for every game — no per-game setup needed.

#### Method 2: `launch-option` TUI (per-game, silent logging)

Same as Bazzite — sets `no_display=1` + `autostart_log=1` per game so logging runs
silently regardless of the slider position.

```bash
mangohud-py launch-option
```

Run from Desktop Mode (CEF is typically available there). If Steam is not running,
changes are written to `localconfig.vdf` and take effect on next Steam restart.

**To set launch options manually** (without the TUI):
1. Switch to Desktop Mode
2. Right-click a game in Steam → Properties → Launch Options
3. Paste:
   ```
   MANGOHUD_CONFIG="autostart_log=1,output_folder=~/mangologs,log_interval=100,log_versioning=1,log_duration=0,no_display=1" mangohud %command%
   ```

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

> On Bazzite Game Mode, `presets.conf` is not used for games — MangoHud is not auto-injected there. Use `launch-option` instead. On Steam Deck (SteamOS), auto-injection means `presets.conf` does work.

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

## Requirements

- Python 3.9+
- MangoHud installed (`mangohud` in PATH)
- `vdf` — required for `launch-option` (`pip install vdf`)
- `websocket-client` — required for CEF live injection in `launch-option` (`pip install websocket-client`)
- `matplotlib` — optional, for graph generation (`pip install "mangohudpy[graphs]"`)
- `mangoplot` — optional, preferred for graphs (ships with MangoHud on Bazzite)
- `PySide6` — optional, for the desktop GUI (`pip install "mangohudpy[gui]"`)
