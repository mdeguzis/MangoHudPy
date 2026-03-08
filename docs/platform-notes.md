# MangoHud Platform Notes

> **MAINTAINER NOTE**: Keep this document in sync with the code.
> Any time platform-specific behavior changes (new env var, new workaround,
> new OS version), update this file in the same commit.

Last verified: 2026-03-08

---

## Platform Comparison

| Feature                     | Steam Deck (SteamOS) | Bazzite (Game Mode) | Desktop Linux |
|-----------------------------|----------------------|---------------------|---------------|
| HUD engine                  | mangoapp             | mangoapp            | mangohud      |
| CSV written by              | mangohud (injected)  | mangohud (injected) | mangohud      |
| `STEAM_USE_MANGOAPP`        | `1`                  | `1`                 | unset         |
| `MANGOHUD_CONFIGFILE`       | set by mangopeel     | set by mangopeel    | unset         |
| `LD_PRELOAD` shim           | `libMangoHud_shim.so`| `libMangoHud_shim.so`| `libMangoHud.so`|
| `presets.conf` respected    | NO                   | NO                  | YES           |
| `MANGOHUD_CONFIG` overrides | YES (on top of file) | YES (on top of file)| YES           |
| Immutable OS                | YES                  | YES                 | NO            |
| Package manager             | pacman               | rpm-ostree          | dnf/apt/pacman|

---

## Steam Deck (SteamOS)

### MangoHud Stack
SteamOS ships with the **mangoapp** HUD stack:

```
gamescope
  └─ mangoapp          (HUD renderer, Valve-maintained)
       └─ mangopeel    (config writer: MANGOHUD_CONFIGFILE=/tmp/mangohud.XXXXXX)

game process
  └─ libMangoHud_shim.so  (LD_PRELOAD, IPC bridge → mangoapp)
```

`libMangoHud_shim.so` is **not** the full MangoHud library. It is an IPC-only
bridge that feeds telemetry to mangoapp. It **cannot** write CSV logs.

### CSV Logging
Two ways to get CSV logs on SteamOS:

1. **Hotkey** (native): Press `Right Ctrl + F12` during gameplay. mangoapp writes
   a CSV to `~/mangologs/mangoapp_YYYY-MM-DD_HH-MM-SS.csv`.

2. **Auto-log** (via MangoHudPy launch option): Inject `mangohud %command%` so a
   full mangohud instance runs alongside the shim. This instance reads
   `MANGOHUD_CONFIG` (which overrides values from the mangopeel temp config) and
   writes CSV automatically.

### `MANGOHUD_CONFIG` vs `MANGOHUD_CONFIGFILE`
- `MANGOHUD_CONFIGFILE` = path to config file (set by mangopeel before game launch)
- `MANGOHUD_CONFIG` = comma-separated `key=value` overrides applied ON TOP of the
  config file — takes effect even when `MANGOHUD_CONFIGFILE` is set

**Do NOT** unset `MANGOHUD_CONFIGFILE`. The shim uses it to locate the mangoapp
IPC socket. Unsetting it breaks the overlay and prevents CSV writing.

### Launch Option Format
```
MANGOHUD_CONFIG="autostart_log=1,output_folder=/home/deck/mangologs,log_interval=100,log_versioning=1,log_duration=0,alpha=0.0,background_alpha=0.0" mangohud %command%
```

- **`mangohud %command%` IS required** — it hooks into the render loop so CSVs write
  continuously (one row per `log_interval` ms). Without it, `autostart_log=1` only
  produces a 1-frame exit-dump via the shim.
- **`alpha=0.0,background_alpha=0.0`** makes the injected overlay fully transparent
  while keeping the render hook active. This is the correct way to hide the overlay.
- **No `no_display=1`** — this disables the render loop entirely (not just the overlay
  visuals), resulting in 1-frame CSVs. Do not use it.
- `output_folder` — **must not contain spaces** (MANGOHUD_CONFIG is comma-split; spaces corrupt the path)
- CSV filenames use the game executable name, e.g. `GameName_YYYY-MM-DD_HH-MM-SS.csv`

### File Paths
| Resource           | Path |
|--------------------|------|
| Steam userdata     | `~/.local/share/Steam/userdata/` |
| Steam apps         | `~/.local/share/Steam/steamapps/` |
| Steam content log  | `~/.local/share/Steam/logs/content_log.txt` |
| MangoHud logs      | `~/mangologs/` |

---

## Bazzite

Bazzite ships its own build of the mangoapp stack. The architecture is identical
to SteamOS. All SteamOS notes apply equally to Bazzite.

### Differences from SteamOS
- **Base OS**: Immutable Fedora (rpm-ostree) instead of Arch
- **Package install**: `sudo rpm-ostree install <pkg>` → reboot required
  - Python packages can be installed user-level with `pip install --user` (no reboot)
- **Desktop Mode**: standard KDE/GNOME, no gamescope; `STEAM_USE_MANGOAPP` may
  still be set depending on launch context
- **SSH access**: `xauth` must be installed via rpm-ostree for X11 forwarding

### Launch Option Format
Same as SteamOS — `mangohud %command%` required, `alpha=0.0,background_alpha=0.0` to hide the overlay:
```
MANGOHUD_CONFIG="autostart_log=1,output_folder=/home/gamer/mangologs,log_interval=100,log_versioning=1,log_duration=0,alpha=0.0,background_alpha=0.0" mangohud %command%
```

### File Paths
| Resource           | Path |
|--------------------|------|
| Steam userdata     | `~/.local/share/Steam/userdata/` |
| Steam apps         | `~/.local/share/Steam/steamapps/` |
| Steam content log  | `~/.local/share/Steam/logs/content_log.txt` |
| MangoHud logs      | `~/mangologs/` |

### Installing MangoHudPy on Bazzite
```bash
# GUI support requires PySide6
pip install --user -e ".[gui]"

# To run gui from SSH session (Wayland):
# mangohud-py-gui auto-detects WAYLAND_DISPLAY and sets QT_QPA_PLATFORM=wayland
mangohud-py-gui
```

---

## Desktop Linux (Fedora, Ubuntu, Arch, etc.)

### MangoHud Stack
Standard mangohud installation — no mangoapp stack:

```
game process
  └─ libMangoHud.so  (LD_PRELOAD, full MangoHud)
       ├─ renders HUD overlay
       └─ writes CSV logs
```

### CSV Logging
MangoHud handles both HUD rendering and CSV writing directly. No shim or IPC.

`presets.conf` is respected. `MangoHud.conf` is read from `$XDG_CONFIG_HOME/MangoHud/`.

### Launch Option Format
```
MANGOHUD_CONFIG="autostart_log=1,output_folder=/home/user/mangologs,log_interval=100,log_versioning=1,log_duration=0" mangohud %command%
```

- No `no_display=1` needed (no duplicate HUD risk on desktop)
- Game name in `output_folder` is safe (no mangoapp/comma-parse issue) but
  MangoHudPy uses flat dir + `organize` for cross-platform consistency

### File Paths
| Resource           | Path |
|--------------------|------|
| Steam userdata     | `~/.local/share/Steam/userdata/` |
| MangoHud config    | `~/.config/MangoHud/MangoHud.conf` |
| MangoHud logs      | `~/mangologs/` (or custom `output_folder`) |

---

## Known Gotchas

### MANGOHUD_CONFIG space-splitting
MANGOHUD_CONFIG is parsed as comma-separated `key=value` pairs. **Spaces in
values break parsing.** Example:
```
# BROKEN — "Zero" and "Dawn" etc. become separate unknown keys
output_folder=/home/gamer/mangologs/Horizon Zero Dawn Remastered

# CORRECT — use flat dir, let organize sort by game
output_folder=/home/gamer/mangologs
```

### `no_display=1` disables the render loop (produces 1-frame CSVs)
`no_display=1` kills MangoHud's render loop hook — it no longer intercepts frames,
so only 1 frame is recorded on process exit. **Do not use it** when continuous CSV
logging is needed.

To hide the overlay without losing frame collection, use:
```
alpha=0.0,background_alpha=0.0
```
This makes the overlay fully transparent while keeping the render hook active, so
CSVs continue writing one row per `log_interval` ms throughout gameplay.

### `env -u MANGOHUD_CONFIGFILE` breaks Bazzite logging
On Bazzite/SteamOS, `MANGOHUD_CONFIGFILE` points to the mangoapp IPC socket
config. Unsetting it with `env -u MANGOHUD_CONFIGFILE` in the launch option
destroys the shim's ability to connect → mangohud fails to initialize → no CSV
is written. Never include `env -u MANGOHUD_CONFIGFILE` in launch options.

### mangoapp CSV filenames vs mangohud CSV filenames
- mangoapp-originated: `mangoapp_YYYY-MM-DD_HH-MM-SS.csv`
- mangohud-originated: `GameName_YYYY-MM-DD_HH-MM-SS.csv`

`mangohud-py organize` matches `mangoapp_*.csv` files to their game via Steam's
`content_log.txt` session timestamps.

### Game detection timing (Horizon Zero Dawn, long-load games)
Some games start MangoHud logging 10+ minutes before Steam reports "App Running"
in `content_log.txt`. MangoHudPy uses overlap detection: the CSV time range
`[csv_start_time, csv_mtime]` is checked against the Steam session window
`[session_start - 180s, session_end]`.

### `find_logs` symlink ordering
On Linux, `-` < `_` lexicographically. The symlink `Game-current-mangohud.csv`
sorts before `Game_2026-03-08.csv`, which would make `find_logs` return the
symlink instead of real log files. Fixed by skipping symlinks in all glob loops.
