"""Image cache model for visualization."""

import logging
from pathlib import Path
from typing import Any
from dataclasses import dataclass

import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, Signal

from pyama_core.io.processing_csv import (
    extract_cell_position_dataframe,
)

logger = logging.getLogger(__name__)


@dataclass
class PositionData:
    """Data structure for cell position information."""

    frames: np.ndarray
    position: dict[str, np.ndarray]  # {"x": array, "y": array}


class ImageCacheModel(QObject):
    """Model providing access to preprocessed image data per type."""

    cacheReset = Signal()
    dataTypeAdded = Signal(str)
    frameBoundsChanged = Signal(int, int)
    currentDataTypeChanged = Signal(str)
    currentFrameChanged = Signal(int)
    activeTraceChanged = Signal(object)
    tracePositionsChanged = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._image_cache: dict[str, np.ndarray] = {}
        self._current_data_type: str = ""
        self._current_frame_index = 0
        self._max_frame_index = 0
        self._trace_positions: dict[str, PositionData] = {}
        self._active_trace_id: str | None = None

    def available_types(self) -> list[str]:
        return list(self._image_cache.keys())

    def set_images(self, mapping: dict[str, np.ndarray]) -> None:
        self._image_cache = dict(mapping)
        self._max_frame_index = self._compute_max_frame()
        self._current_frame_index = 0
        next_type = next(iter(self._image_cache.keys()), "")
        if self._current_data_type != next_type:
            self._current_data_type = next_type
            self.currentDataTypeChanged.emit(self._current_data_type)
        self.frameBoundsChanged.emit(self._current_frame_index, self._max_frame_index)
        self.currentFrameChanged.emit(self._current_frame_index)
        self.cacheReset.emit()

    def update_image(self, key: str, data: np.ndarray) -> None:
        self._image_cache[key] = data
        if not self._current_data_type:
            self._current_data_type = key
            self.currentDataTypeChanged.emit(key)
        self._max_frame_index = self._compute_max_frame()
        self.frameBoundsChanged.emit(self._current_frame_index, self._max_frame_index)
        self.dataTypeAdded.emit(key)

    def remove_images(self) -> None:
        self._image_cache.clear()
        self._current_data_type = ""
        self._current_frame_index = 0
        self._max_frame_index = 0
        self.frameBoundsChanged.emit(0, 0)
        self.currentFrameChanged.emit(0)
        self.currentDataTypeChanged.emit("")
        self.cacheReset.emit()

    def current_data_type(self) -> str:
        return self._current_data_type

    def set_current_data_type(self, data_type: str) -> None:
        if self._current_data_type == data_type:
            return
        if data_type and data_type not in self._image_cache:
            return
        self._current_data_type = data_type
        self.currentDataTypeChanged.emit(data_type)

    def image_for_current_type(self) -> np.ndarray | None:
        if not self._current_data_type:
            return None
        return self._image_cache.get(self._current_data_type)

    def frame_bounds(self) -> tuple[int, int]:
        return (self._current_frame_index, self._max_frame_index)

    def set_current_frame(self, index: int) -> None:
        index = max(0, min(index, self._max_frame_index))
        if index == self._current_frame_index:
            return
        self._current_frame_index = index
        self.currentFrameChanged.emit(index)

    def set_max_frame_index(self, index: int) -> None:
        index = max(index, 0)
        if index == self._max_frame_index:
            return
        self._max_frame_index = index
        self.frameBoundsChanged.emit(self._current_frame_index, index)

    def trace_positions(self) -> dict[str, PositionData]:
        return self._trace_positions

    def set_trace_positions(self, positions: dict[str, PositionData]) -> None:
        self._trace_positions = positions
        self.tracePositionsChanged.emit(positions)

    def get_position_data(self, trace_id: str) -> PositionData | None:
        """Get position data for a specific trace."""
        return self._trace_positions.get(trace_id)

    def set_active_trace(self, trace_id: str | None) -> None:
        if self._active_trace_id == trace_id:
            return
        self._active_trace_id = trace_id
        self.activeTraceChanged.emit(trace_id)

    def active_trace_id(self) -> str | None:
        return self._active_trace_id

    def _compute_max_frame(self) -> int:
        max_index = 0
        for array in self._image_cache.values():
            if array is None:
                continue
            if array.ndim >= 3:
                max_index = max(max_index, array.shape[0] - 1)
        return max_index

    def load_trace_positions(self, processing_df: pd.DataFrame) -> bool:
        """Load trace positions from processing dataframe.

        Args:
            processing_df: The processing dataframe containing cell position data

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get unique trace IDs from the dataframe
            unique_cells = processing_df["cell"].unique()

            # Build position data for each trace
            positions = {}
            for cell_id in unique_cells:
                trace_id = str(int(cell_id))
                try:
                    # Extract position dataframe for this cell
                    pos_df = extract_cell_position_dataframe(
                        processing_df, int(cell_id)
                    )

                    if pos_df.empty:
                        continue

                    # Sort by frame to ensure proper order
                    pos_df_sorted = pos_df.sort_values("frame")

                    # Extract data as numpy arrays
                    frames = pos_df_sorted["frame"].values
                    x_positions = pos_df_sorted["position_x"].values
                    y_positions = pos_df_sorted["position_y"].values

                    # Create PositionData object
                    position_data = PositionData(
                        frames=frames, position={"x": x_positions, "y": y_positions}
                    )

                    positions[trace_id] = position_data

                except ValueError:
                    # Skip cells that don't have position data
                    continue

            # Update the model
            self.set_trace_positions(positions)
            return True

        except Exception as e:
            logger.error(f"Failed to load trace positions: {str(e)}")
            return False
