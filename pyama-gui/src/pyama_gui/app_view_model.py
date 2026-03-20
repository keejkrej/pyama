"""Shared application state for the PyAMA Qt shell."""

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from pyama_gui.constants import DEFAULT_DIR
from pyama_gui.services import FileDialogService
from pyama_gui.types import AppState

class AppViewModel(QObject):
    """Central app-level state shared by all tabs."""

    state_changed = Signal()
    workspace_changed = Signal(object)
    status_changed = Signal(str)
    busy_changed = Signal(bool)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        dialog_service: FileDialogService | None = None,
    ) -> None:
        super().__init__(parent)
        self._dialog_service = dialog_service
        self._workspace_dir: Path | None = None
        self._status_message = "Ready"
        self._busy_count = 0

    @property
    def dialog_service(self) -> FileDialogService | None:
        return self._dialog_service

    @property
    def state(self) -> AppState:
        return AppState(
            workspace_dir=self._workspace_dir,
            status_message=self._status_message,
            busy=self.busy,
        )

    @property
    def workspace_dir(self) -> Path | None:
        return self._workspace_dir

    def set_workspace_dir(self, path: Path | None) -> None:
        if self._workspace_dir == path:
            return
        self._workspace_dir = path
        self.workspace_changed.emit(path)
        self.state_changed.emit()

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
        self.state_changed.emit()

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
            self.state_changed.emit()

    def end_busy(self) -> None:
        was_busy = self.busy
        self._busy_count = max(0, self._busy_count - 1)
        if was_busy != self.busy:
            self.busy_changed.emit(self.busy)
            self.state_changed.emit()

    def select_workspace(self) -> None:
        if self._dialog_service is None:
            raise RuntimeError("No dialog service configured.")

        start_dir = str(self._workspace_dir or DEFAULT_DIR)
        workspace_dir = self._dialog_service.select_directory(
            "Select Workspace Folder", start_dir
        )
        if workspace_dir is None:
            return

        self.set_workspace_dir(workspace_dir)
        self.set_status_message(f"Workspace folder set to {workspace_dir}")
