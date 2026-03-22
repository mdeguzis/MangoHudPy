# Graph Feature Parity with FlightlessSomething

**Date:** 2026-03-22
**Status:** Approved
**Scope:** MangoHudPy GUI graphs area + Dashboard system info

---

## Goal

Bring the MangoHudPy GUI graph area to full feature parity with the FlightlessSomething benchmark website, plus add a system information panel to the Dashboard page.

## Out of Scope

- Dual calculation methods (Linear vs MangoHud)
- Debug/verification tool
- Audio, storage, disk info from protondb script

---

## Section 1: Data Layer

### CSV Spec Parsing

`_RunData` in `mangohudpy/gui/pages/graphs.py` is extended to read **line 2** of each MangoHud CSV (positional fields):

| Index | Field | Notes |
|---|---|---|
| 0 | `spec_os` | OS name |
| 1 | `spec_cpu` | CPU model |
| 2 | `spec_gpu` | GPU name |
| 3 | `spec_ram` | Raw kB → converted to human-readable (e.g. `16 GB`) |
| 4 | `spec_kernel` | Linux kernel version |
| 5 | _(skipped)_ | GPU driver version |
| 6 | `spec_scheduler` | CPU scheduler |

Falls back to `—` for missing/empty fields.

### New Metrics

`_RunData` adds extraction for these CSV columns (flexible column-matching, same pattern as existing):

- `cpu_load` — CPU load (%)
- `gpu_load` — GPU load (%)
- `gpu_core_clock` — GPU core clock (MHz)
- `gpu_mem_clock` — GPU memory clock (MHz)
- `swap` — Swap used (MB)

### Data Downsampling

For CSVs with > 2000 samples, all time-series are stride-sampled to 2000 points (`data[::stride]`). Applied uniformly so all metrics remain time-aligned across runs within a session.

### Extended Statistics

`_RunData.fps_stats()` extended to compute and return:

- Existing: p01, avg, p97
- New: median, p05, p10, p25, p75, p90, p95, p99, std dev, variance, IQR (P75−P25)

Computed via `numpy.percentile`. Used by the extended Summary page stats table.

---

## Section 2: Graphs Page Restructure

The existing 8-tab `QTabWidget` is replaced with **4 top-level tabs**.

### Tab 1 — FPS

Three stacked `_MplCanvas` widgets:

1. **Line chart** — FPS over samples, all runs overlaid, filled area (alpha=0.15)
2. **Bar chart** — 1%, AVG, 97th per run; supports comparison diff modes
3. **Density histogram** — FPS value distribution (numpy, 60 bins)

Subtitle: *"More is better"*

### Tab 2 — Frametime

Three stacked `_MplCanvas` widgets (currently only line chart exists — density + bar are new):

1. **Line chart** — frametime over samples
2. **Bar chart** — 1%, AVG, 97th frametime per run; supports comparison diff modes
3. **Density histogram** — frametime distribution

Subtitle: *"Less is better"*

### Tab 3 — Summary

One horizontal bar chart per metric showing **average value per run**. Metrics: CPU load, GPU load, CPU temp, GPU temp, CPU power, GPU power, RAM, VRAM, GPU core clock, GPU mem clock, swap. Rendered compactly in a single scrollable canvas. Each bar chart has a "More/Less is better" subtitle.

### Tab 4 — All Data

A 2-column grid of line charts — one mini-chart per metric. Conditionally rendered: if no loaded run has data for a metric, that chart is omitted. No per-chart toolbar (too many canvases). Each chart has a "More/Less is better" subtitle.

---

## Section 3: Comparison Controls

### Specs Table

A `QTableWidget` placed **above** the tab widget. Columns = one per loaded run (run label as header). Rows: OS, CPU, GPU, RAM, Kernel, Scheduler. Data sourced from CSV line 2. Hidden when no runs loaded.

### Comparison Toolbar

Placed between specs table and tabs:

```
Baseline: [Run dropdown ▼]   View: (•) Numbers  ( ) +/- Diff  ( ) % Diff
```

- **Baseline dropdown:** populated with loaded run labels; defaults to slowest run (lowest avg FPS)
- **View radio buttons:** Numbers (raw) / +/- Diff (absolute delta from baseline) / % Diff (percentage delta)
- Switching mode re-renders bar charts only; line charts and density always show raw values
- In diff modes: delta bars use green (positive) / red (negative); zero reference line added
- Hidden when fewer than 2 runs are loaded

---

## Section 4: Dashboard System Info

A `QGroupBox` titled **"System Information"** at the top of the Dashboard page (`mangohudpy/gui/pages/dashboard.py`). Collapsible. Shows **current machine** specs gathered once at app startup:

| Field | Source |
|---|---|
| CPU | `/proc/cpuinfo` → `model name`, `cpu cores` |
| GPU | `glxinfo` output → `OpenGL renderer string` (fallback: `/sys/class/drm/*/device/uevent`) |
| RAM | `/proc/meminfo` → `MemTotal` (kB → GB) |
| OS | `/etc/os-release` → `PRETTY_NAME` |
| Kernel | `platform.uname().release` |
| Resolution | `QApplication.primaryScreen().size()` |

All reads are non-blocking (gathered in a `QThreadPool` worker at startup). No shell script dependency.

---

## Section 5: "More / Less is Better" Subtitles

Each chart gets a dimmed subtitle rendered via matplotlib `ax.text()` immediately below the chart title.

| "More is better" | "Less is better" |
|---|---|
| FPS, CPU load, GPU load, GPU core clock, GPU mem clock | Frametime, CPU temp, GPU temp, CPU power, GPU power, RAM, VRAM, Swap |

---

## Section 6: Extended Stats on Summary Page

The existing Summary page (`mangohudpy/gui/pages/summary.py`) stats table is extended to show additional rows:

- Median, Standard Deviation, Variance, IQR (P75−P25)
- Additional percentiles: P05, P10, P25, P75, P90, P95, P99

No new UI required — additional rows in the existing `QTableWidget`.

---

## Files to Modify

| File | Changes |
|---|---|
| `mangohudpy/gui/pages/graphs.py` | Major: `_RunData` (spec + new metrics + downsampling + extended stats), 4-tab restructure, specs table, comparison toolbar, "more/less is better" |
| `mangohudpy/gui/pages/dashboard.py` | Add system info `QGroupBox` with startup worker |
| `mangohudpy/gui/pages/summary.py` | Add extended stats rows |
| `mangohudpy/utils.py` | Possibly expose new percentile helpers |

---

## Key Constraints

- Target resolution: 1280×800 (Steam Deck); UI must remain usable at this size
- All chart rendering stays on matplotlib (no new charting dependencies)
- Comparison diff rendering: bar charts only, not line/density charts
- Specs table and comparison toolbar are hidden (not just disabled) when < 2 runs loaded
