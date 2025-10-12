"""Controller for image panel interactions within the visualization tab."""

from __future__ import annotations

from PySide6.QtCore import QObject

from pyama_qt.models.visualization import VisualizationModel
from pyama_qt.views.visualization.view import VisualizationView


class VisualizationImageController(QObject):
    """Handles image navigation, rendering, and overlay updates."""

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

        self._current_frame_index: int = 0
        self._current_data_type: str = ""

        self._connect_view_signals()
        self._connect_model_signals()

    # ------------------------------------------------------------------
    # External API
    # ------------------------------------------------------------------
    def clear_images(self) -> None:
        self._model.image_model.remove_images()
        self._current_frame_index = 0
        self._current_data_type = ""

    def load_images(self, image_map: dict[str, object]) -> None:
        self._model.image_model.set_images(image_map)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------
    def _connect_view_signals(self) -> None:
        panel = self._view.image_view
        panel.data_type_selected.connect(self._on_data_type_selected)
        panel.frame_delta_requested.connect(self._on_frame_delta_requested)

    def _connect_model_signals(self) -> None:
        image_model = self._model.image_model
        image_model.cacheReset.connect(self._handle_image_cache_reset)
        image_model.currentDataTypeChanged.connect(
            self._handle_current_data_type_changed
        )
        image_model.frameBoundsChanged.connect(self._handle_frame_bounds_changed)
        image_model.currentFrameChanged.connect(self._handle_frame_changed)
        image_model.tracePositionsChanged.connect(self._handle_trace_positions_changed)
        image_model.activeTraceChanged.connect(self._handle_image_active_trace_changed)

    # ------------------------------------------------------------------
    # View → Controller handlers
    # ------------------------------------------------------------------
    def _on_data_type_selected(self, data_type: str) -> None:
        self._model.image_model.set_current_data_type(data_type)

    def _on_frame_delta_requested(self, delta: int) -> None:
        self._model.image_model.set_current_frame(self._current_frame_index + delta)

    # ------------------------------------------------------------------
    # Model → Controller handlers
    # ------------------------------------------------------------------
    def _handle_image_cache_reset(self) -> None:
        types = self._model.image_model.available_types()
        current = self._model.image_model.current_data_type()
        self._view.image_view.set_available_data_types(types, current)
        self._render_current_frame()

    def _handle_current_data_type_changed(self, data_type: str) -> None:
        self._current_data_type = data_type or ""
        if data_type:
            self._view.image_view.set_current_data_type(data_type)
        self._render_current_frame()

    def _handle_frame_bounds_changed(self, current: int, maximum: int) -> None:
        self._current_frame_index = current
        self._view.image_view.set_frame_info(current, maximum)

    def _handle_frame_changed(self, frame: int) -> None:
        self._current_frame_index = frame
        self._view.image_view.set_frame_info(
            frame, self._model.image_model.frame_bounds()[1]
        )
        self._render_current_frame()

    def _handle_trace_positions_changed(self, positions: dict) -> None:
        self._view.image_view.set_trace_positions(positions)
        self._render_current_frame()

    def _handle_image_active_trace_changed(self, trace_id: str | None) -> None:
        self._view.image_view.set_active_trace(trace_id)
        self._render_current_frame()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _render_current_frame(self) -> None:
        image = self._model.image_model.image_for_current_type()
        if image is None:
            return
        frame = image
        if hasattr(image, "ndim") and image.ndim == 3:
            index = max(0, min(self._current_frame_index, image.shape[0] - 1))
            frame = image[index]
        self._view.image_view.render_image(frame, data_type=self._current_data_type)
