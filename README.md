# MangoHudPy

A MangoHud configurator, profiler, log manager, and uploader for Linux gaming.
Designed primarily for **Bazzite / SteamOS** but works on any Linux distro with Steam.

Upload your benchmark logs seamlessly to [FlightlessSomething](https://flightlesssomething.com)!

---

## Features

| Command | Description |
|---------|-------------|
| `configure` | Generate `MangoHud.conf` + `presets.conf` (with logging injected into all 4 Valve overlay presets) |
| `launch-option` | TUI to set per-game Steam launch options that enable silent background logging |
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

With optional graph support (matplotlib):

```bash
pip install "mangohudpy[graphs]"
```

The `mangohud-py` command is available immediately after install.

---

## Platform guide

MangoHud behaves differently depending on platform. Read the section for your setup.

---

### Bazzite (Game Mode) — recommended workflow

Bazzite's `gamescope-session` sets `MANGOHUD_CONFIGFILE` to a temp file managed by
`mangoapp`. This controls the **visual overlay** via the Steam Performance slider (positions 0–4)
and overrides `MangoHud.conf` at runtime. You cannot change what is *displayed* through
`MangoHud.conf` in Game Mode — only through `presets.conf` and the slider.

**Two complementary mechanisms are available:**

#### 1. `presets.conf` — logging at every slider position

Running `mangohud-py configure` writes `~/.config/MangoHud/presets.conf` with logging keys
(`autostart_log`, `output_folder`, `log_interval`, etc.) injected into all 4 Valve presets.
This means any slider position (1–4) will automatically capture a CSV log.

```
Steam Performance slider mapping:
  Off   → preset 0  (MangoHud built-in: no display)
  1     → preset 1  (FPS counter only)          + logging
  2     → preset 2  (compact horizontal bar)    + logging
  3     → preset 3  (full detail)               + logging
  4     → preset 4  (full detail + extras)      + logging
```

> After running `configure`, logs start automatically whenever the slider is on position 1–4.
> No per-game launch option needed.

#### 2. `launch-option` TUI — silent background logging, slider for display

For games where you want **full-detail logging with no overlay on screen**, use the
`launch-option` TUI. It sets a per-game Steam launch option that runs MangoHud with
`no_display=1` and `autostart_log=1`, so data is captured silently in the background
while the Steam Performance slider still controls what (if anything) is shown on screen.

```bash
mangohud-py launch-option
```

The TUI connects live to Steam's CEF debugger — no Steam restart needed. It sets:

```
MANGOHUD_CONFIG="autostart_log=1,output_folder=~/mangologs,log_interval=100,
log_versioning=1,log_duration=0,no_display=1" mangohud %command%
```

TUI keys: `SPACE` toggle, `a` toggle all visible, `s` show/hide launch option string, `u` apply + quit, `q` quit.

> **CEF availability:** The TUI auto-detects whether Steam's debug interface is reachable
> (localhost:8080). On Bazzite in Game Mode, Steam is always running and CEF is available —
> changes apply live. When CEF is unavailable (e.g. Steam not running), changes are written
> directly to `localconfig.vdf` and take effect on next Steam restart.

**Recommended Bazzite setup:**

```bash
# 1. Write MangoHud.conf + presets.conf (logging injected into all 4 Valve presets)
mangohud-py configure

# 2. Optionally: set per-game launch options for silent logging (no HUD shown)
mangohud-py launch-option

# 3. Organize logs after gaming sessions
mangohud-py organize

# 4. Upload to FlightlessSomething
mangohud-py upload
```

---

### Steam Deck (SteamOS — Game Mode)

The Steam Deck uses the same `gamescope-session` + `mangoapp` mechanism as Bazzite.
`presets.conf` works identically — run `configure` once and all slider positions log.

The `launch-option` TUI also works. In Game Mode, CEF availability depends on whether
Steam's remote debugging port is open; if not, the TUI falls back to writing `localconfig.vdf`
(requires Steam restart). Running the TUI from Desktop Mode is recommended — CEF is
typically available there.

**To set launch options manually** (without the TUI):
1. Switch to Desktop Mode
2. Right-click a game in Steam → Properties → Launch Options
3. Paste:
   ```
   MANGOHUD_CONFIG="autostart_log=1,output_folder=~/mangologs,log_interval=100,log_versioning=1,log_duration=0,no_display=1" mangohud %command%
   ```

`presets.conf` must be at `~/.config/MangoHud/presets.conf` — `configure` handles this.

---

### Desktop Linux (any distro)

On a standard desktop, `MANGOHUD_CONFIGFILE` is not set by gamescope, so `MangoHud.conf`
and `presets.conf` are respected normally.

```bash
# Generate a config with full logging
mangohud-py configure --preset logging

# Or: minimal HUD, no logging
mangohud-py configure --preset minimal

# Profile a specific binary for 2 minutes
mangohud-py profile --command "game-binary" --duration 120

# Set per-game Steam launch options via TUI
mangohud-py launch-option
```

The `launch-option` TUI works the same on desktop — CEF is used when Steam is running,
VDF fallback otherwise.

---

## Config presets

Used with `mangohud-py configure --preset <name>`:

| Preset    | Description |
|-----------|-------------|
| `logging` | Full CSV logging, minimal OSD — best for data collection |
| `minimal` | Lightweight HUD — FPS + frametime only, no logging |
| `full`    | Everything on OSD and all logging enabled (`autostart_log=1`) |
| `battery` | Power / battery metrics — ideal for Steam Deck / handheld |

```bash
# Global config
mangohud-py configure --preset logging

# Per-game config (Wine/Proton games)
mangohud-py configure --game Cyberpunk2077 --preset logging
# writes ~/.config/MangoHud/wine-Cyberpunk2077.conf

# Custom log output folder
mangohud-py configure --preset logging --log-dir /mnt/data/mangologs

# Overwrite an existing config
mangohud-py configure --preset logging --force
```

---

## `presets.conf` explained

`presets.conf` maps Steam's Performance slider positions (1–4) to MangoHud display +
logging configurations. MangoHudPy generates this file with logging keys in every section
so that **any slider position automatically captures a CSV log** to `~/mangologs/`.

Each slider position retains Valve's original OSD appearance while adding:

```ini
autostart_log=1
output_folder=~/mangologs
toggle_logging=Shift_L+F2
log_duration=0
log_interval=100
log_versioning=1
```

The file is written to `~/.config/MangoHud/presets.conf` by `mangohud-py configure`.
On Bazzite/SteamOS, `mangoapp` reads this file when applying the slider.

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
