"""Consolidated analysis model."""

from dataclasses import dataclass, field
from typing import Dict
from PySide6.QtCore import QObject

from .data_model import DataModel
from .fitting_model import FittingModel
from .results_model import ResultsModel


@dataclass(slots=True)
class FittingRequest:
    """Parameters for triggering a fitting job."""

    model_type: str
    model_params: Dict[str, float] = field(default_factory=dict)
    model_bounds: Dict[str, tuple[float, float]] = field(default_factory=dict)


class AnalysisModel(QObject):
    """Consolidated model for analysis functionality."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.data_model = DataModel()
        self.fitting_model = FittingModel()
        self.results_model = ResultsModel()
