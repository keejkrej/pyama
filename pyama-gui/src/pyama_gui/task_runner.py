"""Shared helpers for running QObject tasks in background threads."""

from PySide6.QtCore import QObject, Signal

from pyama.tasks import TaskStatus, cancel_task, subscribe, unsubscribe
from pyama_gui.utils import WorkerHandle, start_worker

TERMINAL_TASK_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
}


class TaskWorker(QObject):
    """Base worker with common success, error, and cancel helpers."""

    finished = Signal(bool, object, str)
    progress = Signal(object)
    progress_value = Signal(int, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cancelled = False
        self._task_ids: list[str] = []

    def cancel(self) -> None:
        self._cancelled = True
        for task_id in self._task_ids:
            cancel_task(task_id)

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def emit_success(self, result=None, message: str = "") -> None:
        self.finished.emit(True, result, message)

    def emit_failure(self, message: str, result=None) -> None:
        self.finished.emit(False, result, message)

    def forward_progress(self, percent: int, message: str) -> None:
        self.progress_value.emit(percent, message)

    def wait_for_task(
        self,
        record,
        *,
        progress_handler=None,
    ):
        self._task_ids.append(record.id)
        queue = subscribe(record.id)
        try:
            while True:
                snapshot = queue.get()
                if progress_handler and snapshot.progress is not None:
                    progress_handler(snapshot.progress)
                if snapshot.status in TERMINAL_TASK_STATUSES:
                    return snapshot
        finally:
            unsubscribe(record.id, queue)


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


__all__ = ["TERMINAL_TASK_STATUSES", "TaskWorker", "WorkerHandle", "run_task"]
