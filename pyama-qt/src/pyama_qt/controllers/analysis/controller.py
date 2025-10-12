"""Facade controller coordinating analysis sub-controllers."""

from __future__ import annotations

from PySide6.QtCore import QObject

from pyama_qt.models.analysis import AnalysisModel
from pyama_qt.views.analysis.view import AnalysisView

from .data_controller import AnalysisDataController
from .fitting_controller import AnalysisFittingController
from .results_controller import AnalysisResultsController


class AnalysisController(QObject):
    """Compose data, fitting, and results controllers for the analysis tab."""

    def __init__(self, view: AnalysisView, model: AnalysisModel) -> None:
        super().__init__()
        self._view = view
        self._model = model

        self._results_controller = AnalysisResultsController(view, model, parent=self)
        self._data_controller = AnalysisDataController(view, model, parent=self)
        self._fitting_controller = AnalysisFittingController(view, model, parent=self)

    @property
    def data_controller(self) -> AnalysisDataController:
        return self._data_controller

    @property
    def fitting_controller(self) -> AnalysisFittingController:
        return self._fitting_controller

    @property
    def results_controller(self) -> AnalysisResultsController:
        return self._results_controller
