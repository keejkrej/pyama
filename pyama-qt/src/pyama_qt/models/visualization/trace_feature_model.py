"""Trace feature model for visualization."""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, Signal

from pyama_core.io.processing_csv import (
    extract_cell_feature_dataframe,
)

logger = logging.getLogger(__name__)


@dataclass
class FeatureData:
    """Data structure for cell feature time series."""

    time_points: np.ndarray
    features: dict[
        str, np.ndarray
    ]  # {"feature_name1": array, "feature_name2": array, ...}


class TraceFeatureModel(QObject):
    """Model for managing trace feature data."""

    availableFeaturesChanged = Signal(list)
    featureDataChanged = Signal(dict)  # trace_id -> FeatureData
    featureLoadError = Signal(str)
    activeTraceChanged = Signal(str)
    featureSelectionChanged = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self._feature_data: dict[str, FeatureData] = {}
        self._active_trace_id: str | None = None
        self._selected_features: list[str] = []

    def feature_data(self) -> dict[str, FeatureData]:
        return self._feature_data

    def active_trace_id(self) -> str | None:
        return self._active_trace_id

    def selected_features(self) -> list[str]:
        return self._selected_features

    def available_features(self) -> list[str]:
        """Get list of available feature names."""
        if not self._feature_data:
            return []
        # Get features from the first available trace
        first_trace_data = next(iter(self._feature_data.values()))
        return list(first_trace_data.features.keys())

    def set_active_trace(self, trace_id: str | None) -> None:
        if self._active_trace_id == trace_id:
            return
        self._active_trace_id = trace_id
        self.activeTraceChanged.emit(trace_id)

    def set_selected_features(self, features: list[str]) -> None:
        if self._selected_features == features:
            return
        self._selected_features = features
        self.featureSelectionChanged.emit(features)

    def get_feature_data(self, trace_id: str) -> FeatureData | None:
        """Get feature data for a specific trace."""
        return self._feature_data.get(trace_id)

    def set_feature_data(self, trace_id: str, feature_data: FeatureData) -> None:
        """Set feature data for a specific trace."""
        self._feature_data[trace_id] = feature_data
        self.featureDataChanged.emit({trace_id: feature_data})

    def load_feature_data(self, processing_df: pd.DataFrame, trace_id: str) -> bool:
        """Load feature data for a specific trace from processing dataframe.

        Args:
            processing_df: The processing dataframe
            trace_id: The trace ID to load data for

        Returns:
            True if successful, False otherwise
        """
        try:
            cell_id = int(trace_id)

            # Extract feature dataframe for this cell
            feature_df = extract_cell_feature_dataframe(processing_df, cell_id)

            if feature_df.empty:
                logger.warning(f"No feature data found for trace {trace_id}")
                return False

            # Sort by time to ensure proper order
            feature_df_sorted = feature_df.sort_values("time")

            # Extract time points
            time_points = feature_df_sorted["time"].values

            # Extract feature columns (exclude 'cell' and 'time')
            feature_columns = [
                col for col in feature_df_sorted.columns if col not in ["cell", "time"]
            ]
            features = {col: feature_df_sorted[col].values for col in feature_columns}

            # Create FeatureData object
            feature_data = FeatureData(time_points=time_points, features=features)

            # Set the feature data
            self.set_feature_data(trace_id, feature_data)
            return True

        except Exception as e:
            logger.error(f"Failed to load feature data for trace {trace_id}: {str(e)}")
            return False

    def clear_feature_data(self) -> None:
        """Clear all feature data."""
        self._feature_data.clear()
        self.featureDataChanged.emit({})
