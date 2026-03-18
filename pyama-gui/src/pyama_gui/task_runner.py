"""Shared helpers for running QObject tasks in background threads."""

from PySide6.QtCore import QObject, Signal

from pyama_gui.utils import WorkerHandle, start_worker


class TaskWorker(QObject):
    """Base worker with common success, error, and cancel helpers."""

    finished = Signal(bool, object, str)
    progress = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def emit_success(self, result=None, message: str = "") -> None:
        self.finished.emit(True, result, message)

    def emit_failure(self, message: str, result=None) -> None:
        self.finished.emit(False, result, message)


def run_task(
    worker: QObject,
    *,
    start_method: str = "run",
    finished_callback=None,
) -> WorkerHandle:
    """Start a QObject worker in a dedicated thread."""

    return start_worker(
        worker,
        start_method=start_method,
        finished_callback=finished_callback,
    )


__all__ = ["TaskWorker", "WorkerHandle", "run_task"]
