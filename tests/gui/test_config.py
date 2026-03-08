"""Tests for ConfigPage data logic."""
import pytest


def test_preset_rows_returns_sorted_pairs():
    from mangohudpy.gui.pages.config import _preset_rows
    rows = _preset_rows("logging")
    keys = [r[0] for r in rows]
    assert keys == sorted(keys)


def test_preset_rows_contains_required_keys():
    from mangohudpy.gui.pages.config import _preset_rows
    rows = _preset_rows("logging")
    keys = [r[0] for r in rows]
    assert "fps" in keys
    assert "output_folder" in keys
    assert "frametime" in keys


def test_preset_rows_values_are_strings():
    from mangohudpy.gui.pages.config import _preset_rows
    rows = _preset_rows("logging")
    for key, val in rows:
        assert isinstance(val, str), f"Value for {key!r} is not a string: {val!r}"


def test_all_presets_load():
    from mangohudpy.gui.pages.config import _preset_rows
    from mangohudpy.constants import CONFIG_PRESETS
    for name in CONFIG_PRESETS:
        rows = _preset_rows(name)
        assert len(rows) > 0, f"Preset {name!r} returned no rows"


def test_battery_preset_has_battery_keys():
    from mangohudpy.gui.pages.config import _preset_rows
    rows = _preset_rows("battery")
    keys = [r[0] for r in rows]
    assert "battery" in keys
    assert "battery_power" in keys
