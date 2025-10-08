"""Consolidated visualization model."""

from PySide6.QtCore import QObject

from .image_model import ImageCacheModel
from .project_model import ProjectModel
from .trace_feature_model import TraceFeatureModel
from .trace_selection_model import TraceSelectionModel
from .trace_table_model import TraceTableModel


class VisualizationModel(QObject):
    """Consolidated model for visualization functionality."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.project_model = ProjectModel()
        self.image_model = ImageCacheModel()
        self.trace_table_model = TraceTableModel()
        self.trace_feature_model = TraceFeatureModel()
        self.trace_selection_model = TraceSelectionModel()
