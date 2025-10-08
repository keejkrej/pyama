"""Status model for processing workflow."""

from PySide6.QtCore import QObject, Signal


class WorkflowStatusModel(QObject):
    """Model for workflow execution status and progress."""

    isProcessingChanged = Signal(bool)
    statusMessageChanged = Signal(str)
    errorMessageChanged = Signal(str)
    mergeStatusChanged = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._is_processing: bool = False
        self._status_message: str = ""
        self._error_message: str = ""
        self._merge_status: str = ""

    def is_processing(self) -> bool:
        return self._is_processing

    def set_is_processing(self, value: bool) -> None:
        if self._is_processing == value:
            return
        self._is_processing = value
        self.isProcessingChanged.emit(value)

    def status_message(self) -> str:
        return self._status_message

    def set_status_message(self, message: str) -> None:
        if self._status_message == message:
            return
        self._status_message = message
        self.statusMessageChanged.emit(message)

    def error_message(self) -> str:
        return self._error_message

    def set_error_message(self, message: str) -> None:
        if self._error_message == message:
            return
        self._error_message = message
        self.errorMessageChanged.emit(message)

    def merge_status(self) -> str:
        return self._merge_status

    def set_merge_status(self, status: str) -> None:
        if self._merge_status == status:
            return
        self._merge_status = status
        self.mergeStatusChanged.emit(status)
