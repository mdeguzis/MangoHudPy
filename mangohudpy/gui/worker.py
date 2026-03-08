"""QThread worker for running blocking CLI functions without freezing the UI."""
from __future__ import annotations
import traceback
from contextlib import redirect_stdout
from io import StringIO
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    """Signals emitted by Worker during and after execution."""
    output = Signal(str)    # one line of captured stdout
    finished = Signal()     # emitted when fn completes (success or error)
    error = Signal(str)     # emitted on exception with traceback string


class Worker(QRunnable):
    """Run a callable in the global thread pool, streaming stdout to signals.

    Usage:
        worker = Worker(cmd_organize, args)
        worker.signals.output.connect(log_widget.append_line)
        worker.signals.finished.connect(on_done)
        QThreadPool.globalInstance().start(worker)
    """

    def __init__(self, fn: Callable, *args: Any, **kwargs: Any):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        buf = StringIO()
        try:
            with redirect_stdout(buf):
                self.fn(*self.args, **self.kwargs)
        except Exception:
            # Flush any partial output before emitting error
            output = buf.getvalue()
            for line in output.splitlines():
                if line.strip():
                    self.signals.output.emit(line)
            self.signals.error.emit(traceback.format_exc())
        else:
            output = buf.getvalue()
            for line in output.splitlines():
                if line.strip():
                    self.signals.output.emit(line)
        finally:
            self.signals.finished.emit()
