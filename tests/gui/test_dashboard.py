"""Tests for DashboardPage — focuses on data logic, not Qt widgets."""
import pytest
from pathlib import Path


def _make_csv(tmp_path: Path, name: str, fps_vals: list, ft_vals: list) -> Path:
    """Create a minimal MangoHud CSV with given fps and frametime values."""
    p = tmp_path / f"{name}_2026-01-01_12-00-00.csv"
    fps_lines = "\n".join(f"{fps},{ft}" for fps, ft in zip(fps_vals, ft_vals))
    p.write_text(
        "os,cpu,gpu,ram,kernel,driver,cpuscheduler\n"
        "Linux,AMD,AMD,8192,6.1,Mesa,none\n"
        "fps,frametime\n"
        + fps_lines + "\n"
    )
    return p


def test_build_game_stats_avg_fps(tmp_path):
    """_build_game_stats computes correct avg FPS."""
    from mangohudpy.gui.pages.dashboard import _build_game_stats
    csv = _make_csv(tmp_path, "TestGame", [60.0, 59.0, 61.0], [16.6, 16.9, 16.4])
    stats = _build_game_stats(csv)
    assert abs(stats["avg_fps"] - 60.0) < 0.5


def test_build_game_stats_low1(tmp_path):
    """_build_game_stats 1% low is less than or equal to average."""
    from mangohudpy.gui.pages.dashboard import _build_game_stats
    csv = _make_csv(tmp_path, "TestGame", [60.0, 30.0, 61.0], [16.6, 33.0, 16.4])
    stats = _build_game_stats(csv)
    assert stats["low1"] <= stats["avg_fps"]


def test_build_game_stats_empty_csv(tmp_path):
    """_build_game_stats handles CSV with no data rows gracefully."""
    from mangohudpy.gui.pages.dashboard import _build_game_stats
    p = tmp_path / "empty_2026-01-01_12-00-00.csv"
    p.write_text(
        "os,cpu,gpu,ram,kernel,driver,cpuscheduler\n"
        "Linux,AMD,AMD,8192,6.1,Mesa,none\n"
        "fps,frametime\n"
    )
    stats = _build_game_stats(p)
    assert stats["avg_fps"] == 0.0
    assert stats["low1"] == 0.0
    assert stats["jitter"] == 0.0


def test_build_game_stats_sessions_default(tmp_path):
    """_build_game_stats returns sessions=1 (caller sets actual count)."""
    from mangohudpy.gui.pages.dashboard import _build_game_stats
    csv = _make_csv(tmp_path, "TestGame", [60.0], [16.6])
    stats = _build_game_stats(csv)
    assert stats["sessions"] == 1
