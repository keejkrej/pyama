"""Shared application state for the PyAMA Qt shell."""

from pathlib import Path

from PySide6.QtCore import QObject, Signal


class AppViewModel(QObject):
    """Central app-level state shared by all tabs."""

    workspace_changed = Signal(object)
    status_changed = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._workspace_dir: Path | None = None
        self._status_message = "Ready"
        self._busy_count = 0

    @property
    def workspace_dir(self) -> Path | None:
        return self._workspace_dir

    def set_workspace_dir(self, path: Path | None) -> None:
        if self._workspace_dir == path:
            return
        self._workspace_dir = path
        self.workspace_changed.emit(path)

    @property
    def status_message(self) -> str:
        return self._status_message

    def set_status_message(self, message: str) -> None:
        if not message:
            message = "Ready"
        if self._status_message == message:
            return
        self._status_message = message
        self.status_changed.emit(message)

    def clear_status(self) -> None:
        self.set_status_message("Ready")

    @property
    def busy(self) -> bool:
        return self._busy_count > 0

    def begin_busy(self) -> None:
        was_busy = self.busy
        self._busy_count += 1
        if was_busy != self.busy:
            self.busy_changed.emit(self.busy)

    def end_busy(self) -> None:
        was_busy = self.busy
        self._busy_count = max(0, self._busy_count - 1)
        if was_busy != self.busy:
            self.busy_changed.emit(self.busy)
