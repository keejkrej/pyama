"""Results model for fitted analysis results table."""

import logging
from pathlib import Path
from typing import Any, List

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal

logger = logging.getLogger(__name__)


class ResultsModel(QAbstractTableModel):
    """Table model for fitted results DataFrame."""

    resultsReset = Signal()
    resultsChanged = Signal()  # For incremental updates if needed

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._df: pd.DataFrame | None = None
        self._headers: List[str] = []

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

        if role in (Qt.DisplayRole, Qt.EditRole):
            value = self._df.iloc[index.row(), index.column()]
            return str(value) if pd.notna(value) else ""

        # Custom role for success (e.g., for coloring)
        if role == Qt.UserRole and index.column() == self._df.columns.get_loc(
            "success"
        ):
            return self._df.iloc[index.row()]["success"]

        # Custom role for r_squared
        if role == (Qt.UserRole + 1) and index.column() == self._df.columns.get_loc(
            "r_squared"
        ):
            return self._df.iloc[index.row()]["r_squared"]

        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        # Read-only for now; can add editing later if needed
        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

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

    def set_results(self, df: pd.DataFrame) -> None:
        """Set or update the fitted results DataFrame."""
        self.beginResetModel()
        self._df = df
        self._headers = list(df.columns) if df is not None else []
        self.endResetModel()
        self.resultsReset.emit()

    def results(self) -> pd.DataFrame | None:
        return self._df

    def load_from_csv(self, path: Path) -> None:
        """Load fitted results from CSV file."""
        try:
            df = pd.read_csv(path)
            self.set_results(df)
        except Exception as e:
            logger.warning("Failed to load fitted results: %s", e)

    def clear_results(self) -> None:
        """Clear all fitted results."""
        self.set_results(pd.DataFrame())
