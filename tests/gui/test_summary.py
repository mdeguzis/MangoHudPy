"""Tests for SummaryPage data logic."""
from pathlib import Path
import pytest


def _make_csv(tmp_path: Path) -> Path:
    p = tmp_path / "TestGame_2026-01-01_12-00-00.csv"
    p.write_text(
        "os,cpu,gpu,ram,kernel,driver,cpuscheduler\n"
        "Linux,AMD,AMD,8192,6.1,Mesa,none\n"
        "fps,frametime,cpu_temp,gpu_temp\n"
        "60.0,16.6,65.0,70.0\n"
        "58.0,17.2,66.0,71.0\n"
        "62.0,16.1,64.0,69.0\n"
    )
    return p


def test_build_summary_rows_has_fps(tmp_path):
    from mangohudpy.gui.pages.summary import _build_summary_rows
    rows = _build_summary_rows(_make_csv(tmp_path))
    labels = [r[0] for r in rows]
    assert "FPS" in labels


def test_build_summary_rows_fps_avg(tmp_path):
    from mangohudpy.gui.pages.summary import _build_summary_rows
    rows = _build_summary_rows(_make_csv(tmp_path))
    fps_row = next(r for r in rows if r[0] == "FPS")
    assert abs(float(fps_row[1]) - 60.0) < 1.0


def test_build_summary_rows_has_thermals(tmp_path):
    from mangohudpy.gui.pages.summary import _build_summary_rows
    rows = _build_summary_rows(_make_csv(tmp_path))
    labels = [r[0] for r in rows]
    assert "CPU Temp" in labels
    assert "GPU Temp" in labels


def test_build_summary_rows_column_count(tmp_path):
    from mangohudpy.gui.pages.summary import _build_summary_rows
    rows = _build_summary_rows(_make_csv(tmp_path))
    for row in rows:
        assert len(row) == 9  # Metric + 7 stats + Unit


def test_build_summary_rows_empty_csv(tmp_path):
    from mangohudpy.gui.pages.summary import _build_summary_rows
    p = tmp_path / "empty_2026-01-01.csv"
    p.write_text(
        "os,cpu,gpu,ram,kernel,driver,cpuscheduler\n"
        "Linux,AMD,AMD,8192,6.1,Mesa,none\n"
        "fps,frametime\n"
    )
    rows = _build_summary_rows(p)
    assert rows == []
