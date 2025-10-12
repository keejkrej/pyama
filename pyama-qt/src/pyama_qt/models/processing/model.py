"""Consolidated processing model."""

from PySide6.QtCore import QObject

from .merge_model import MergeModel
from .workflow_model import WorkflowModel


class ProcessingModel(QObject):
    """Consolidated model for processing functionality."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.workflow_model = WorkflowModel()
        self.merge_model = MergeModel()
