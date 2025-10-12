"""Controller for trace inspection interactions within the visualization tab."""

import logging
from pathlib import Path
import pandas as pd
from PySide6.QtCore import QObject


from pyama_qt.models.visualization import (
    FeatureData,
    PositionData,
    VisualizationModel,
)
from pyama_qt.views.visualization.view import VisualizationView

logger = logging.getLogger(__name__)


class TraceController(QObject):
    """Manages trace selection state, QC markers, and trace panel rendering."""

    def __init__(
        self,
        view: VisualizationView,
        model: VisualizationModel,
        *,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._model = model

        self._connect_view_signals()
        self._connect_model_signals()

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------
    def _connect_view_signals(self) -> None:
        panel = self._view.trace_view
        panel.active_trace_changed.connect(self._on_active_trace_selected)
        panel.good_state_changed.connect(self._on_good_state_changed)
        panel.save_requested.connect(self._on_save_requested)

    def _connect_model_signals(self) -> None:
        self._model.trace_selection_model.goodCellsChanged.connect(
            self._handle_good_cells_changed
        )
        self._model.trace_feature_model.featureDataCellsChanged.connect(
            self._handle_feature_data_changed
        )
        self._model.trace_selection_model.selectedCellsChanged.connect(
            self._handle_selected_cells_changed
        )

    # ------------------------------------------------------------------
    # View → Controller handlers
    # ------------------------------------------------------------------
    def _on_active_trace_selected(self, trace_id: str) -> None:
        self._model.trace_selection_model.set_active_trace(trace_id)
        self._model.image_model.set_active_trace(trace_id)

    def _on_good_state_changed(self, trace_id: str, is_good: bool) -> None:
        current_good = self._model.trace_selection_model.goodCells or {}
        current_good[trace_id] = is_good
        self._model.trace_selection_model.goodCells = current_good

    def _on_save_requested(
        self, good_map: dict[str, bool], target: Path | None
    ) -> None:
        if target is None:
            logger.warning("Save requested without a target path")
            return
        for trace_id, state in good_map.items():
            current_good = self._model.trace_selection_model.goodCells or {}
            current_good[trace_id] = state
            self._model.trace_selection_model.goodCells = current_good
        message = f"Saved inspected data to {target.name}"
        self._view.status_bar.showMessage(message)

    # ------------------------------------------------------------------
    # Model → Controller handlers
    # ------------------------------------------------------------------
    def _handle_feature_data_changed(self, _: dict[str, FeatureData]) -> None:
        available_features = self._model.trace_feature_model.available_features()
        self._view.trace_view.set_available_features(available_features)
        self._refresh_trace_panel()

    def _handle_good_cells_changed(self, good_cells: dict[str, bool]) -> None:
        self._trace_good_status = good_cells or {}
        self._refresh_trace_panel()

    def _handle_selected_cells_changed(self, selected_cells: dict[str, bool]) -> None:
        active_trace = next(iter(selected_cells)) if selected_cells else None
        self._view.trace_view.set_active_trace(active_trace)
        self._model.image_model.set_active_trace(active_trace)
        self._refresh_trace_panel()

    # ------------------------------------------------------------------
    # External API
    # ------------------------------------------------------------------
    def clear_trace_data(self) -> None:
        self._trace_features = None
        self._trace_good_status = {}
        self._trace_source_path = None
        self._view.trace_view.clear()

    def set_trace_source_path(self, path: Path | None) -> None:
        self._trace_source_path = path

    def load_traces_from_path(self, fov_idx: int, traces_path: Path) -> str:
        """Load trace data from CSV, updating the models and view.

        Returns a status message suitable for the project status bar.
        """
        self._trace_source_path = traces_path

        try:
            processing_df = get_dataframe(traces_path)
        except Exception as exc:
            logger.error("Failed to load trace data from %s: %s", traces_path, exc)
            self._reset_trace_models()
            return "Failed to load trace data"

        if processing_df is None:
            logger.error("Processing dataframe is empty for %s", traces_path)
            self._reset_trace_models()
            return "Failed to load trace data"

        try:
            quality_df = extract_cell_quality_dataframe(processing_df)
        except Exception as exc:
            logger.error("Failed to extract quality dataframe: %s", exc)
            self._reset_trace_models()
            return "Failed to load trace data"

        if quality_df.empty:
            logger.warning("No cell quality data found in %s", traces_path)
            self._model.trace_selection_model.goodCells = {}
        else:
            good_cells = {
                str(row["cell_id"]): row["good"] for _, row in quality_df.iterrows()
            }
            self._model.trace_selection_model.goodCells = good_cells

        self._model.trace_selection_model.selectedCells = {}

        special_cols = {"cell_id", "time", "good", "centroid_x", "centroid_y"}
        feature_columns = [
            col
            for col in processing_df.columns
            if col not in special_cols
            and pd.api.types.is_numeric_dtype(processing_df[col])
        ]

        feature_data_cells: dict[str, FeatureData] = {}
        trace_positions: dict[str, PositionData] = {}
        df_sorted = processing_df.sort_values(["cell_id", "time"])

        for cell_id_int, group in df_sorted.groupby("cell_id"):
            cell_id = str(cell_id_int)
            group_df = group.sort_values("time")
            time_points = group_df["time"].values
            features = {
                col: group_df[col].values
                for col in feature_columns
                if col in group_df.columns
            }
            feature_data_cells[cell_id] = FeatureData(
                time_points=time_points,
                features=features,
            )
            x = group_df["centroid_x"].values
            y = group_df["centroid_y"].values
            trace_positions[cell_id] = PositionData(
                frames=time_points,
                position={"x": x, "y": y},
            )

        self._trace_features = feature_data_cells
        self._trace_good_status = self._model.trace_selection_model.goodCells or {}
        self._model.trace_feature_model.featureDataCells = feature_data_cells
        self._model.image_model.set_trace_positions(trace_positions)
        self._refresh_trace_panel()

        return (
            f"FOV {fov_idx:03d} ready with trace data ({len(feature_data_cells)} cells)"
        )

    def handle_missing_trace_data(self, fov_idx: int) -> str:
        """Reset trace state when no trace data is available."""
        self._trace_features = None
        self._trace_good_status = {}
        self._trace_source_path = None
        self._model.trace_selection_model.goodCells = {}
        self._model.trace_selection_model.selectedCells = {}
        self._model.trace_feature_model.featureDataCells = {}
        self._model.image_model.set_trace_positions({})
        self._refresh_trace_panel()
        return f"FOV {fov_idx:03d} ready (no trace data)"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _reset_trace_models(self) -> None:
        self._trace_features = None
        self._trace_good_status = {}
        self._trace_source_path = None
        self._model.trace_selection_model.goodCells = {}
        self._model.trace_selection_model.selectedCells = {}
        self._model.trace_feature_model.featureDataCells = {}
        self._model.image_model.set_trace_positions({})
        self._refresh_trace_panel()

    def _refresh_trace_panel(self) -> None:
        if self._trace_features is None:
            self._view.trace_view.clear()
            return

        features = self._model.trace_feature_model.available_features()
        self._view.trace_view.set_trace_dataset(
            traces=self._trace_features,
            good_status=self._trace_good_status,
            features=features,
            source_path=self._trace_source_path,
        )
        self._view.trace_view.set_active_trace(
            self._model.trace_selection_model.active_trace()
        )


# class VisualizationTraceController(QObject):
#     """Manages trace selection state, QC markers, and trace panel rendering."""

#     def __init__(
#         self,
#         view: VisualizationView,
#         model: VisualizationModel,
#         *,
#         parent: QObject | None = None,
#     ) -> None:
#         super().__init__(parent)
#         self._view = view
#         self._model = model

#         self._trace_features: dict[str, FeatureData] | None = None
#         self._trace_good_status: dict[str, bool] = {}
#         self._trace_source_path: Path | None = None

#         self._connect_view_signals()
#         self._connect_model_signals()

#     # ------------------------------------------------------------------
#     # Signal wiring
#     # ------------------------------------------------------------------
#     def _connect_view_signals(self) -> None:
#         panel = self._view.trace_view
#         panel.active_trace_changed.connect(self._on_active_trace_selected)
#         panel.good_state_changed.connect(self._on_good_state_changed)
#         panel.save_requested.connect(self._on_save_requested)

#     def _connect_model_signals(self) -> None:
#         self._model.trace_selection_model.goodCellsChanged.connect(
#             self._handle_good_cells_changed
#         )
#         self._model.trace_feature_model.featureDataCellsChanged.connect(
#             self._handle_feature_data_changed
#         )
#         self._model.trace_selection_model.selectedCellsChanged.connect(
#             self._handle_selected_cells_changed
#         )

#     # ------------------------------------------------------------------
#     # View → Controller handlers
#     # ------------------------------------------------------------------
#     def _on_active_trace_selected(self, trace_id: str) -> None:
#         self._model.trace_selection_model.set_active_trace(trace_id)
#         self._model.image_model.set_active_trace(trace_id)

#     def _on_good_state_changed(self, trace_id: str, is_good: bool) -> None:
#         current_good = self._model.trace_selection_model.goodCells or {}
#         current_good[trace_id] = is_good
#         self._model.trace_selection_model.goodCells = current_good

#     def _on_save_requested(
#         self, good_map: dict[str, bool], target: Path | None
#     ) -> None:
#         if target is None:
#             logger.warning("Save requested without a target path")
#             return
#         for trace_id, state in good_map.items():
#             current_good = self._model.trace_selection_model.goodCells or {}
#             current_good[trace_id] = state
#             self._model.trace_selection_model.goodCells = current_good
#         message = f"Saved inspected data to {target.name}"
#         self._view.status_bar.showMessage(message)

#     # ------------------------------------------------------------------
#     # Model → Controller handlers
#     # ------------------------------------------------------------------
#     def _handle_feature_data_changed(self, _: dict[str, FeatureData]) -> None:
#         available_features = self._model.trace_feature_model.available_features()
#         self._view.trace_view.set_available_features(available_features)
#         self._refresh_trace_panel()

#     def _handle_good_cells_changed(self, good_cells: dict[str, bool]) -> None:
#         self._trace_good_status = good_cells or {}
#         self._refresh_trace_panel()

#     def _handle_selected_cells_changed(self, selected_cells: dict[str, bool]) -> None:
#         active_trace = next(iter(selected_cells)) if selected_cells else None
#         self._view.trace_view.set_active_trace(active_trace)
#         self._model.image_model.set_active_trace(active_trace)
#         self._refresh_trace_panel()

#     # ------------------------------------------------------------------
#     # External API
#     # ------------------------------------------------------------------
#     def clear_trace_data(self) -> None:
#         self._trace_features = None
#         self._trace_good_status = {}
#         self._trace_source_path = None
#         self._view.trace_view.clear()

#     def set_trace_source_path(self, path: Path | None) -> None:
#         self._trace_source_path = path

#     def load_traces_from_path(self, fov_idx: int, traces_path: Path) -> str:
#         """Load trace data from CSV, updating the models and view.

#         Returns a status message suitable for the project status bar.
#         """
#         self._trace_source_path = traces_path

#         try:
#             processing_df = get_dataframe(traces_path)
#         except Exception as exc:
#             logger.error("Failed to load trace data from %s: %s", traces_path, exc)
#             self._reset_trace_models()
#             return "Failed to load trace data"

#         if processing_df is None:
#             logger.error("Processing dataframe is empty for %s", traces_path)
#             self._reset_trace_models()
#             return "Failed to load trace data"

#         try:
#             quality_df = extract_cell_quality_dataframe(processing_df)
#         except Exception as exc:
#             logger.error("Failed to extract quality dataframe: %s", exc)
#             self._reset_trace_models()
#             return "Failed to load trace data"

#         if quality_df.empty:
#             logger.warning("No cell quality data found in %s", traces_path)
#             self._model.trace_selection_model.goodCells = {}
#         else:
#             good_cells = {
#                 str(row["cell_id"]): row["good"] for _, row in quality_df.iterrows()
#             }
#             self._model.trace_selection_model.goodCells = good_cells

#         self._model.trace_selection_model.selectedCells = {}

#         special_cols = {"cell_id", "time", "good", "centroid_x", "centroid_y"}
#         feature_columns = [
#             col
#             for col in processing_df.columns
#             if col not in special_cols
#             and pd.api.types.is_numeric_dtype(processing_df[col])
#         ]

#         feature_data_cells: dict[str, FeatureData] = {}
#         trace_positions: dict[str, PositionData] = {}
#         df_sorted = processing_df.sort_values(["cell_id", "time"])

#         for cell_id_int, group in df_sorted.groupby("cell_id"):
#             cell_id = str(cell_id_int)
#             group_df = group.sort_values("time")
#             time_points = group_df["time"].values
#             features = {
#                 col: group_df[col].values
#                 for col in feature_columns
#                 if col in group_df.columns
#             }
#             feature_data_cells[cell_id] = FeatureData(
#                 time_points=time_points,
#                 features=features,
#             )
#             x = group_df["centroid_x"].values
#             y = group_df["centroid_y"].values
#             trace_positions[cell_id] = PositionData(
#                 frames=time_points,
#                 position={"x": x, "y": y},
#             )

#         self._trace_features = feature_data_cells
#         self._trace_good_status = self._model.trace_selection_model.goodCells or {}
#         self._model.trace_feature_model.featureDataCells = feature_data_cells
#         self._model.image_model.set_trace_positions(trace_positions)
#         self._refresh_trace_panel()

#         return (
#             f"FOV {fov_idx:03d} ready with trace data ({len(feature_data_cells)} cells)"
#         )

#     def handle_missing_trace_data(self, fov_idx: int) -> str:
#         """Reset trace state when no trace data is available."""
#         self._trace_features = None
#         self._trace_good_status = {}
#         self._trace_source_path = None
#         self._model.trace_selection_model.goodCells = {}
#         self._model.trace_selection_model.selectedCells = {}
#         self._model.trace_feature_model.featureDataCells = {}
#         self._model.image_model.set_trace_positions({})
#         self._refresh_trace_panel()
#         return f"FOV {fov_idx:03d} ready (no trace data)"

#     # ------------------------------------------------------------------
#     # Internal helpers
#     # ------------------------------------------------------------------
#     def _reset_trace_models(self) -> None:
#         self._trace_features = None
#         self._trace_good_status = {}
#         self._trace_source_path = None
#         self._model.trace_selection_model.goodCells = {}
#         self._model.trace_selection_model.selectedCells = {}
#         self._model.trace_feature_model.featureDataCells = {}
#         self._model.image_model.set_trace_positions({})
#         self._refresh_trace_panel()

#     def _refresh_trace_panel(self) -> None:
#         if self._trace_features is None:
#             self._view.trace_view.clear()
#             return

#         features = self._model.trace_feature_model.available_features()
#         self._view.trace_view.set_trace_dataset(
#             traces=self._trace_features,
#             good_status=self._trace_good_status,
#             features=features,
#             source_path=self._trace_source_path,
#         )
#         self._view.trace_view.set_active_trace(
#             self._model.trace_selection_model.active_trace()
#         )
