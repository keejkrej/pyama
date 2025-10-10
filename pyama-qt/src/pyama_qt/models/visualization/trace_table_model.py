"""Trace table model for visualization."""

import logging
from typing import Any
from dataclasses import dataclass

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal

from pyama_core.io.processing_csv import (
    extract_cell_quality_dataframe,
)

logger = logging.getLogger(__name__)


@dataclass
class CellQuality:
    """Data structure for cell quality information."""

    cell_id: int
    good: bool


class TraceTableModel(QAbstractTableModel):
    """Table model for displaying trace data."""

    GoodRole = Qt.ItemDataRole.UserRole + 1
    goodStateChanged = Signal(str, bool)
    tracesReset = Signal()
    csvLoadError = Signal(str)
    dataChanged = Signal()
    selectionChanged = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._df: pd.DataFrame | None = None
        self._selected_rows: set[int] = set()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if self._df is None:
            return 0
        return len(self._df)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if self._df is None:
            return 0
        return len(self._df.columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or self._df is None:
            return None

        if role == Qt.DisplayRole:
            value = self._df.iloc[index.row(), index.column()]
            return str(value) if pd.notna(value) else ""

        # Custom role for cell quality (good/bad)
        if role == Qt.UserRole and index.column() == self._df.columns.get_loc("good"):
            return self._df.iloc[index.row()]["good"]

        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        if not index.isValid() or self._df is None:
            return False

        if role == Qt.EditRole:
            try:
                self._df.iloc[index.row(), index.column()] = value
                self.dataChanged.emit(index, index, [role])
                return True
            except Exception:
                return False

        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Any:
        if self._df is None:
            return None
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._df.columns[section])
            elif orientation == Qt.Vertical:
                return str(section + 1)  # Row numbers
        return None

    def set_dataframe(self, df: pd.DataFrame) -> None:
        """Set the dataframe and reset the model."""
        self.beginResetModel()
        self._df = df
        self._selected_rows.clear()
        self.endResetModel()
        self.dataChanged.emit()

    def dataframe(self) -> pd.DataFrame | None:
        return self._df

    def selected_rows(self) -> list[int]:
        return sorted(self._selected_rows)

    def set_selected_rows(self, rows: list[int]) -> None:
        if self._selected_rows == set(rows):
            return
        self._selected_rows = set(rows)
        self.selectionChanged.emit(sorted(rows))

    def load_from_processing_data(self, processing_df: pd.DataFrame) -> bool:
        """Load trace data from processing dataframe.

        Args:
            processing_df: The processing dataframe

        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract cell quality dataframe
            quality_df = extract_cell_quality_dataframe(processing_df)

            if quality_df.empty:
                logger.warning("No cell quality data found in processing dataframe")
                self.set_dataframe(pd.DataFrame())
                return False

            # Set the dataframe
            self.set_dataframe(quality_df)
            return True

        except Exception as e:
            logger.error(f"Failed to load trace data: {str(e)}")
            return False
