"""Graph command: generate performance charts from MangoHud CSV logs."""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import shutil
from typing import Any, List, Optional, Tuple

from .constants import CHART_BASE_DIR
from .utils import _extract_game_name, _fcol, log, parse_csv, pctl, sf

_MPL = False
try:
    import matplotlib  # type: ignore[import-not-found]

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # type: ignore[import-not-found]

    _MPL = True
except ImportError:
    pass

# ── FlightlessSomething-style dark theme ───────────────────────────────
_FS_THEME = {
    "bg": "#212529",
    "text": "#FFFFFF",
    "grid": "rgba(255, 255, 255, 0.1)",
    "line": "#FFFFFF",
    "tooltip_bg": "#1E1E1E",
    "palette": [
        "#7cb5ec",
        "#434348",
        "#90ed7d",
        "#f7a35c",
        "#8085e9",
        "#f15c80",
        "#e4d354",
        "#2b908f",
        "#f45b5b",
        "#91e8e1",
    ],
}


def _apply_fs_theme(fig: Any, ax: Any, title: str, ylabel: str) -> None:
    """Apply FlightlessSomething dark theme to a matplotlib axes."""
    fig.patch.set_facecolor(_FS_THEME["bg"])
    ax.set_facecolor(_FS_THEME["bg"])
    ax.set_title(title, fontsize=16, fontweight="bold", color=_FS_THEME["text"])
    ax.set_ylabel(ylabel, color=_FS_THEME["text"], fontsize=12)
    ax.set_xlabel("Sample", color=_FS_THEME["text"], fontsize=12)
    ax.tick_params(colors=_FS_THEME["text"], which="both")
    ax.grid(True, color=_FS_THEME["text"], alpha=0.1, linewidth=0.5)
    for spine in ax.spines.values():
        spine.set_color(_FS_THEME["line"])
        spine.set_alpha(0.3)


def _plot(
    vals: List[float],
    title: str,
    ylabel: str,
    color: str,
    fa: float,
    out: pathlib.Path,
    dpi: int = 150,
    sz: Tuple[float, float] = (14, 6),
) -> None:
    fig, ax = plt.subplots(figsize=sz, dpi=dpi)
    x = list(range(len(vals)))
    ax.plot(x, vals, color=color, lw=1.2)
    ax.fill_between(x, vals, alpha=fa, color=color)
    _apply_fs_theme(fig, ax, title, ylabel)
    fig.tight_layout()
    fig.savefig(str(out), facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"    Graph: {out}")


def _gen_graphs(
    csv_path: pathlib.Path,
    out_dir: pathlib.Path,
    fmt: str = "png",
    dpi: int = 150,
    w: float = 14,
    h: float = 6,
) -> int:
    if not _MPL:
        log.warning("matplotlib unavailable.")
        return 1
    cols, rows = parse_csv(csv_path)
    if not rows:
        log.warning("No data in %s", csv_path)
        return 1
    s = csv_path.stem
    gen = []
    for cands, label, unit, clr, fa in [
        (["fps", "FPS"], "FPS", "Frames/s", "#2ecc71", 0.25),
        (["frametime", "frametime_ms", "Frametime"], "Frame Time", "ms", "#e74c3c", 0.20),
        (["cpu_temp", "CPU_Temp"], "CPU Temp", "C", "#e67e22", 0.15),
        (["gpu_temp", "GPU_Temp"], "GPU Temp", "C", "#9b59b6", 0.15),
        (["cpu_power", "CPU_Power"], "CPU Power", "W", "#f39c12", 0.15),
        (["gpu_power", "GPU_Power"], "GPU Power", "W", "#8e44ad", 0.15),
        (["battery", "Battery"], "Battery", "%", "#1abc9c", 0.20),
        (["ram", "RAM"], "RAM", "MB", "#3498db", 0.15),
        (["vram", "VRAM"], "VRAM", "MB", "#2980b9", 0.15),
    ]:
        k = _fcol(cols, cands)
        if k:
            vs = [sf(r.get(k, "0")) for r in rows]
            if any(v > 0 for v in vs):
                tag = cands[0].lower().replace(" ", "_")
                o = out_dir / f"{s}_{tag}.{fmt}"
                _plot(vs, f"{label} -- {s}", unit, clr, fa, o, dpi, (w, h))
                gen.append(o)

    # Combined FPS+Frametime overview
    fk = _fcol(cols, ["fps", "FPS"])
    ftk = _fcol(cols, ["frametime", "frametime_ms", "Frametime"])
    if fk and ftk and _MPL:
        fig, (a1, a2) = plt.subplots(2, 1, figsize=(w, h * 1.2), dpi=dpi, sharex=True)
        x = list(range(len(rows)))
        fv = [sf(r.get(fk, "0")) for r in rows]
        tv = [sf(r.get(ftk, "0")) for r in rows]
        a1.plot(x, fv, color="#7cb5ec", lw=1.2)
        a1.fill_between(x, fv, alpha=0.2, color="#7cb5ec")
        _apply_fs_theme(fig, a1, f"FPS -- {s}", "FPS")
        a1.set_xlabel("")
        a2.plot(x, tv, color="#f7a35c", lw=1.2)
        a2.fill_between(x, tv, alpha=0.15, color="#f7a35c")
        _apply_fs_theme(fig, a2, f"Frametime -- {s}", "ms")
        fig.tight_layout()
        o = out_dir / f"{s}_overview.{fmt}"
        fig.savefig(str(o), facecolor=fig.get_facecolor(), edgecolor="none")
        plt.close(fig)
        gen.append(o)
        print(f"    Graph: {o}")

    # Summary bar chart (FlightlessSomething "Summary" tab style)
    if fk and _MPL:
        fv_sorted = sorted([sf(r.get(fk, "0")) for r in rows])
        if fv_sorted and max(fv_sorted) > 0:
            avg_fps = sum(fv_sorted) / len(fv_sorted)
            p1_fps = pctl(fv_sorted, 1)
            p01_fps = pctl(fv_sorted, 0.1)
            labels = ["Average", "1% Low", "0.1% Low"]
            values = [avg_fps, p1_fps, p01_fps]
            bar_colors = ["#7cb5ec", "#90ed7d", "#f7a35c"]

            fig, ax = plt.subplots(figsize=(w, 3.5), dpi=dpi)
            fig.patch.set_facecolor(_FS_THEME["bg"])
            ax.set_facecolor(_FS_THEME["bg"])
            bars = ax.barh(
                labels,
                values,
                color=bar_colors,
                edgecolor=_FS_THEME["line"],
                linewidth=0.5,
                height=0.5,
            )
            for bar, val in zip(bars, values):
                ax.text(
                    bar.get_width() + max(values) * 0.02,
                    bar.get_y() + bar.get_height() / 2,
                    f"{val:.1f} fps",
                    va="center",
                    color=_FS_THEME["text"],
                    fontsize=12,
                    fontweight="bold",
                )
            ax.set_title(
                f"FPS Summary -- {s}",
                fontsize=16,
                fontweight="bold",
                color=_FS_THEME["text"],
            )
            ax.set_xlabel("FPS", color=_FS_THEME["text"], fontsize=12)
            ax.tick_params(colors=_FS_THEME["text"], which="both")
            ax.grid(True, axis="x", color=_FS_THEME["text"], alpha=0.1, linewidth=0.5)
            ax.set_xlim(0, max(values) * 1.15)
            for spine in ax.spines.values():
                spine.set_color(_FS_THEME["line"])
                spine.set_alpha(0.3)
            ax.invert_yaxis()
            fig.tight_layout()
            o = out_dir / f"{s}_summary.{fmt}"
            fig.savefig(str(o), facecolor=fig.get_facecolor(), edgecolor="none")
            plt.close(fig)
            gen.append(o)
            print(f"    Graph: {o}")

    if gen:
        print(f"  {len(gen)} graph(s) generated in {out_dir}")
    return 0


def _mangoplot_available() -> bool:
    return shutil.which("mangoplot") is not None


def _run_mangoplot(csv_path: pathlib.Path, out_dir: pathlib.Path) -> int:
    """Run mangoplot on a CSV, saving output to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["mangoplot", str(csv_path)]
    log.info("Running: %s (output -> %s)", " ".join(cmd), out_dir)
    try:
        result = subprocess.run(
            cmd,
            cwd=str(out_dir),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode == 0:
            pngs = list(out_dir.glob("*.png"))
            if pngs:
                print(f"    mangoplot generated {len(pngs)} chart(s) in {out_dir}")
                for p in sorted(pngs):
                    print(f"      {p.name}")
            else:
                print(f"    mangoplot completed but no PNGs found in {out_dir}")
            if result.stdout.strip():
                print(result.stdout.strip())
        else:
            log.warning("mangoplot exited with code %d", result.returncode)
            if result.stderr.strip():
                log.warning("mangoplot stderr: %s", result.stderr.strip())
        return result.returncode
    except FileNotFoundError:
        log.error("mangoplot not found in PATH.")
        return 1
    except subprocess.TimeoutExpired:
        log.error("mangoplot timed out after 60s.")
        return 1


def cmd_graph(args: argparse.Namespace) -> int:
    game = getattr(args, "game", None)
    ip = pathlib.Path(args.input) if args.input else None
    if ip is None:
        from .utils import newest_log
        ip = newest_log(game=game)
    if ip is None or not ip.exists():
        log.error("No input file.%s", f" (filtered by game '{game}')" if game else "")
        return 1

    if args.output:
        od = pathlib.Path(args.output)
    elif game:
        od = CHART_BASE_DIR / game / "charts"
    else:
        gn = _extract_game_name(ip.stem)
        od = CHART_BASE_DIR / gn / "charts"

    od.mkdir(parents=True, exist_ok=True)

    if _mangoplot_available() and not args.matplotlib:
        print(f"  Using mangoplot (system) for {ip.name}")
        ret = _run_mangoplot(ip, od)
        if ret == 0:
            return 0
        print("  mangoplot failed, falling back to matplotlib...")

    if not _MPL:
        log.error(
            "Neither mangoplot nor matplotlib available.\n"
            "  Install mangoplot (comes with MangoHud) or: pip install matplotlib"
        )
        return 1
    return _gen_graphs(
        ip, od, fmt=args.format, dpi=args.dpi, w=args.width, h=args.height
    )
