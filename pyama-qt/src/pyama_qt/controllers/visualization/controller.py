"""Facade controller coordinating visualization sub-controllers."""

from __future__ import annotations

from PySide6.QtCore import QObject

from pyama_qt.models.visualization import VisualizationModel
from pyama_qt.views.visualization.view import VisualizationView

from .image_controller import VisualizationImageController
from .project_controller import VisualizationProjectController
from .trace_controller import VisualizationTraceController


class VisualizationController(QObject):
    """Compose project, image, and trace controllers for the visualization tab."""

    def __init__(self, view: VisualizationView, model: VisualizationModel) -> None:
        super().__init__()
        self._view = view
        self._model = model

        self._trace_controller = VisualizationTraceController(view, model, parent=self)
        self._image_controller = VisualizationImageController(view, model, parent=self)
        self._project_controller = VisualizationProjectController(
            view,
            model,
            image_controller=self._image_controller,
            trace_controller=self._trace_controller,
            parent=self,
        )

    @property
    def project_controller(self) -> VisualizationProjectController:
        return self._project_controller

    @property
    def image_controller(self) -> VisualizationImageController:
        return self._image_controller

    @property
    def trace_controller(self) -> VisualizationTraceController:
        return self._trace_controller
