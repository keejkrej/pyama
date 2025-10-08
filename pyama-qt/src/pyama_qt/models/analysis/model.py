"""Consolidated analysis model."""

from dataclasses import dataclass, field
from typing import Dict
from PySide6.QtCore import QObject

from .data_model import AnalysisDataModel
from .fitting_model import FittingModel
from .results_model import FittedResultsModel


@dataclass(slots=True)
class FittingRequest:
    """Parameters for triggering a fitting job."""

    model_type: str
    model_params: Dict[str, float] = field(default_factory=dict)
    model_bounds: Dict[str, tuple[float, float]] = field(default_factory=dict)


class AnalysisModel(QObject):
    """Consolidated model for analysis functionality."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.data_model = AnalysisDataModel()
        self.fitting_model = FittingModel()
        self.results_model = FittedResultsModel()
