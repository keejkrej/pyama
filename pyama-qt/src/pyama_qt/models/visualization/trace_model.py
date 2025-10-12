"""Trace table model for visualization."""

import logging
from dataclasses import dataclass
import numpy as np
import pandas as pd
from pathlib import Path
from PySide6.QtCore import QObject, Signal, Property, Slot

from pyama_core.io.processing_csv import extract_cell_quality_dataframe, get_dataframe

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

    good_cells_changed = Signal(dict)
    selected_cells_changed = Signal(dict)
    feature_data_cells_changed = Signal(dict)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._good_cells: dict[str, bool] | None = None
        self._selected_cells: dict[str, bool] | None = None
        self._feature_data_cells: dict[str, FeatureData] | None = None

    @Property(object, notify=good_cells_changed)
    def good_cells(self) -> dict[str, bool] | None:
        return self._good_cells

    @good_cells.setter
    def good_cells(self, good_cells: dict[str, bool] | None) -> None:
        if self._good_cells is not good_cells:
            self._good_cells = good_cells
            self.good_cells_changed.emit(good_cells or {})

    @Property(object, notify=selected_cells_changed)
    def selected_cells(self) -> dict[str, bool] | None:
        return self._selected_cells

    @selected_cells.setter
    def selected_cells(self, selected_cells: dict[str, bool] | None) -> None:
        if self._selected_cells is not selected_cells:
            self._selected_cells = selected_cells
            self.selected_cells_changed.emit(selected_cells or {})

    @Property(object, notify=feature_data_cells_changed)
    def feature_data_cells(self) -> dict[str, FeatureData] | None:
        return self._feature_data_cells

    @feature_data_cells.setter
    def feature_data_cells(self, feature_data: dict[str, FeatureData] | None) -> None:
        if self._feature_data_cells is not feature_data:
            self._feature_data_cells = feature_data
            self.feature_data_cells_changed.emit(feature_data or {})

    @Slot()
    def load_from_csv(self, path: Path) -> None:
        pass

    @Slot()
    def save_to_csv(self, path: Path) -> None:
        pass
