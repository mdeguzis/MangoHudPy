import subprocess
import sys


def test_gui_entry_point_help():
    """mangohud-py-gui --help should print MangoHudPy and exit 0."""
    result = subprocess.run(
        [sys.executable, "-c",
         "from mangohudpy.gui.app import main; import sys; sys.exit(main(['--help']))"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "MangoHudPy" in result.stdout + result.stderr


def test_gui_entry_point_help_short():
    """-h should also work."""
    result = subprocess.run(
        [sys.executable, "-c",
         "from mangohudpy.gui.app import main; import sys; sys.exit(main(['-h']))"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "MangoHudPy" in result.stdout + result.stderr
