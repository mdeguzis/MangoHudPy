"""Tests for Worker and WorkerSignals — no display server needed."""
from contextlib import redirect_stdout
from io import StringIO


def test_stdout_capture_basic():
    """redirect_stdout captures print() output correctly."""
    buf = StringIO()
    with redirect_stdout(buf):
        print("hello worker")
        print("second line")
    lines = buf.getvalue().splitlines()
    assert "hello worker" in lines
    assert "second line" in lines


def test_worker_signals_exist():
    """WorkerSignals has output, finished, and error signals."""
    from mangohudpy.gui.worker import WorkerSignals
    s = WorkerSignals()
    assert hasattr(s, "output")
    assert hasattr(s, "finished")
    assert hasattr(s, "error")


def test_worker_has_signals_attribute():
    """Worker exposes a .signals WorkerSignals instance."""
    from mangohudpy.gui.worker import Worker, WorkerSignals

    def noop():
        pass

    w = Worker(noop)
    assert isinstance(w.signals, WorkerSignals)


def test_worker_captures_stdout():
    """Worker.run() captures print output and emits via signals.output."""
    from mangohudpy.gui.worker import Worker

    collected = []

    def fn_with_output():
        print("line one")
        print("line two")

    w = Worker(fn_with_output)
    w.signals.output.connect(collected.append)
    w.run()  # run synchronously in test (no thread pool needed)

    assert "line one" in collected
    assert "line two" in collected


def test_worker_emits_finished():
    """Worker.run() always emits finished signal."""
    from mangohudpy.gui.worker import Worker

    finished = []

    def fn():
        pass

    w = Worker(fn)
    w.signals.finished.connect(lambda: finished.append(True))
    w.run()

    assert finished == [True]


def test_worker_emits_error_on_exception():
    """Worker.run() emits error signal with traceback on exception."""
    from mangohudpy.gui.worker import Worker

    errors = []
    finished = []

    def bad_fn():
        raise ValueError("test error")

    w = Worker(bad_fn)
    w.signals.error.connect(errors.append)
    w.signals.finished.connect(lambda: finished.append(True))
    w.run()

    assert len(errors) == 1
    assert "ValueError" in errors[0]
    assert "test error" in errors[0]
    assert finished == [True]  # finished still fires
