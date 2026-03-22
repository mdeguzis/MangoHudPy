# Development Guide

## Prerequisites

- [uv](https://astral.sh/uv) — used for all dependency management and running commands
- Python 3.9+
- MangoHud installed (for profiling features; not required for GUI/tests)

## Setup

Run the setup script to create a virtualenv and install all dependencies in editable mode:

```bash
./dev-setup.sh
```

This installs the package with all optional extras (`gui`, `graphs`) so every feature is available locally.

### Manual setup (alternative)

```bash
uv venv
uv pip install -e ".[gui,graphs]"
```

## Running

**Option A — activate the venv:**
```bash
source .venv/bin/activate
mangohud-py --help
mangohud-py-gui
```

**Option B — run without activating:**
```bash
uv run mangohud-py --help
uv run mangohud-py-gui
```

## Running Tests

```bash
uv run pytest tests/ -v
```

GUI tests run headless via `QT_QPA_PLATFORM=offscreen` (set automatically in the test files). No display required.

## Building

```bash
uv build
```

Outputs a wheel and source distribution to `dist/`.

## Releasing

Releasing is fully automated via CI:

1. Bump `version = "x.y.z"` in `pyproject.toml`
2. Commit and push to `main`

CI will: run tests → create a `vx.y.z` git tag → build wheel + sdist → publish to GitHub Releases and PyPI.

See `.github/workflows/ci.yml` for the full pipeline.

---

## Project Structure

```
MangoHudPy/
├── mangohudpy/                 # Main package
│   ├── cli.py                  # CLI entry point (mangohud-py)
│   ├── constants.py            # Paths, preset definitions, config keys
│   ├── config.py               # MangoHud.conf read/write helpers
│   ├── profile.py              # Profiling session management
│   ├── summary.py              # CSV log summarisation
│   ├── graph.py                # Matplotlib graph generation
│   ├── organize.py             # Log file organisation (rename, move, clean)
│   ├── bundle.py               # Multi-log bundle creation
│   ├── upload.py               # FlightlessSomething upload client
│   ├── launch.py               # Steam launch option helpers
│   ├── desktop.py              # XDG .desktop entry + icon installation
│   ├── utils.py                # Shared utilities (logging, platform detection)
│   ├── test_cmd.py             # mangohud test command helpers
│   ├── data/
│   │   └── mangohudpy.svg      # Bundled app icon
│   └── gui/                    # PySide6 desktop GUI (mangohud-py-gui)
│       ├── app.py              # QApplication entry point, theme management
│       ├── main_window.py      # Top-level window: sidebar + page stack
│       ├── widgets.py          # Shared reusable widgets
│       ├── worker.py           # QThread worker for background tasks
│       └── pages/              # One file per sidebar page
│           ├── dashboard.py    # Per-game stats overview
│           ├── organize.py     # Log file browser and organiser
│           ├── summary.py      # Session summary table
│           ├── graphs.py       # Matplotlib graph viewer
│           ├── config.py       # MangoHud.conf editor with presets
│           ├── upload.py       # FlightlessSomething upload UI
│           ├── profile.py      # Profiling session launcher
│           ├── launch_option.py # Steam launch option generator
│           └── test_page.py    # MangoHud test overlay page
│
├── tests/
│   └── gui/                    # pytest test suite (offscreen Qt)
│       ├── test_app.py
│       ├── test_main_window.py
│       ├── test_widgets.py
│       ├── test_worker.py
│       ├── test_dashboard.py
│       ├── test_summary.py
│       └── test_config.py
│
├── .github/
│   └── workflows/
│       └── ci.yml              # CI: test → autotag → build → publish
│
├── docs/
│   └── platform-notes.md       # Bazzite / SteamOS specific notes
│
├── pyproject.toml              # Package metadata and dependencies
├── uv.lock                     # Pinned dependency lockfile
├── dev-setup.sh                # One-shot dev environment setup
└── upload-to-pypi.sh           # Manual PyPI upload (legacy; CI handles this now)
```

## Key Paths at Runtime

| Path | Purpose |
|---|---|
| `~/.config/MangoHud/MangoHud.conf` | Main MangoHud config |
| `~/mangologs/` | Raw and organised CSV logs |
| `~/.local/share/icons/hicolor/` | App icon (installed on first GUI launch) |
| `~/.local/share/applications/mangohud-py-gui.desktop` | Desktop entry (installed on first GUI launch) |
| `~/.flightless-token` | FlightlessSomething API token |

## Dependencies

| Extra | Packages | Required for |
|---|---|---|
| *(none)* | `vdf`, `websocket-client` | CLI core |
| `gui` | `PySide6>=6.6` | Desktop GUI |
| `graphs` | `matplotlib` | Graph generation |
| `dev` | `pytest>=8` | Running tests |
