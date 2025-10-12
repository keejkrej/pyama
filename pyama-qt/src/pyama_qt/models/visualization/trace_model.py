"""Trace table model for visualization."""

import logging
from PySide6.QtCore import QObject, Signal, Property
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FeatureData:
    """Data structure for cell feature time series."""

    time_points: np.ndarray
    features: dict[
        str, np.ndarray
    ]  # {"feature_name1": array, "feature_name2": array, ...}


class TraceModel(QObject):
    """Model for trace table state."""

    goodCellsChanged = Signal(dict)
    selectedCellsChanged = Signal(dict)
    featureDataCellsChanged = Signal(dict)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._good_cells: dict[str, bool] | None = None
        self._selected_cells: dict[str, bool] | None = None
        self._feature_data_cells: dict[str, FeatureData] | None = None

    @Property(object, notify=goodCellsChanged)
    def goodCells(self) -> dict[str, bool] | None:
        return self._good_cells

    @goodCells.setter
    def goodCells(self, good_cells: dict[str, bool] | None) -> None:
        if self._good_cells is not good_cells:
            self._good_cells = good_cells
            self.goodCellsChanged.emit(good_cells or {})

    @Property(object, notify=selectedCellsChanged)
    def selectedCells(self) -> dict[str, bool] | None:
        return self._selected_cells

    @selectedCells.setter
    def selectedCells(self, selected_cells: dict[str, bool] | None) -> None:
        if self._selected_cells is not selected_cells:
            self._selected_cells = selected_cells
            self.selectedCellsChanged.emit(selected_cells or {})

    @Property(object, notify=featureDataCellsChanged)
    def featureDataCells(self) -> dict[str, FeatureData] | None:
        return self._feature_data_cells

    @featureDataCells.setter
    def featureDataCells(self, feature_data: dict[str, FeatureData] | None) -> None:
        if self._feature_data_cells is not feature_data:
            self._feature_data_cells = feature_data
            self.featureDataCellsChanged.emit(feature_data or {})
