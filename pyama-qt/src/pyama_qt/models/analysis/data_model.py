"""Data model for analysis trace data and plotting."""

import logging
from pathlib import Path
from typing import Any, List, Tuple, Dict

import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, Signal

from pyama_core.io.analysis_csv import load_analysis_csv

logger = logging.getLogger(__name__)


class DataModel(QObject):
    """Model holding raw trace data and plot configuration."""

    rawDataChanged = Signal(pd.DataFrame)
    plotDataChanged = Signal(
        object
    )  # List[Tuple[np.ndarray, np.ndarray, Dict[str, Any]]]
    plotTitleChanged = Signal(str)
    selectedCellChanged = Signal(object)
    rawCsvPathChanged = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._raw_data: pd.DataFrame | None = None
        self._plot_data: List[Tuple[np.ndarray, np.ndarray, Dict[str, Any]]] | None = (
            None
        )
        self._plot_title: str = ""
        self._selected_cell: str | None = None
        self._raw_csv_path: Path | None = None

    def raw_data(self) -> pd.DataFrame | None:
        return self._raw_data

    def raw_csv_path(self) -> Path | None:
        return self._raw_csv_path

    def load_csv(self, path: Path) -> None:
        """Load CSV data and prepare initial plot."""
        logger.info("Loading analysis CSV from %s", path)
        try:
            # Use the analysis_csv loader which handles time unit parsing and conversion to hours
            df = load_analysis_csv(path)
            self._raw_data = df
            self.rawDataChanged.emit(df)
            self._raw_csv_path = path
            self.rawCsvPathChanged.emit(path)
            self._prepare_all_plot()
        except Exception:
            logger.exception("Failed to load analysis CSV")
            raise

    def prepare_all_plot(self) -> None:
        """Prepare plot data for all traces."""
        if self._raw_data is None:
            self._plot_data = None
            self._plot_title = ""
            self.plotDataChanged.emit(None)
            self.plotTitleChanged.emit("")
            return

        data = self._raw_data
        time_values = data.index.values
        lines: List[Tuple[np.ndarray, np.ndarray, Dict[str, Any]]] = []
        for col in data.columns:
            lines.append(
                (
                    time_values,
                    data[col].values,
                    {"color": "gray", "alpha": 0.2, "linewidth": 0.5},
                )
            )
        # Mean line
        if not data.empty:
            mean = data.mean(axis=1).values
            lines.append(
                (time_values, mean, {"color": "red", "linewidth": 2, "label": "Mean"})
            )
        self._plot_data = lines
        self._plot_title = f"All Sequences ({len(data.columns)} cells)"
        self.plotDataChanged.emit(lines)
        self.plotTitleChanged.emit(self._plot_title)

    def highlight_cell(self, cell_id: str) -> None:
        """Highlight a specific cell in the plot."""
        if self._raw_data is None or cell_id not in self._raw_data.columns:
            return
        self._selected_cell = cell_id
        self.selectedCellChanged.emit(cell_id)

        data = self._raw_data
        time_values = data.index.values
        lines: List[Tuple[np.ndarray, np.ndarray, Dict[str, Any]]] = []
        for other_id in data.columns:
            if other_id != cell_id:
                lines.append(
                    (
                        time_values,
                        data[other_id].values,
                        {"color": "gray", "alpha": 0.1, "linewidth": 0.5},
                    )
                )
        lines.append(
            (
                time_values,
                data[cell_id].values,
                {"color": "blue", "linewidth": 2, "label": f"Cell {cell_id}"},
            )
        )
        self._plot_data = lines
        self._plot_title = f"Cell {cell_id} Highlighted"
        self.plotDataChanged.emit(lines)
        self.plotTitleChanged.emit(self._plot_title)

    def get_random_cell(self) -> str | None:
        """Get a random cell ID."""
        if self._raw_data is None or self._raw_data.empty:
            return None
        return str(np.random.choice(self._raw_data.columns))

    def _prepare_all_plot(self) -> None:
        self.prepare_all_plot()
