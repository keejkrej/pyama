"""Controller for project loading and FOV visualization workflow."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, Signal

from pyama_core.io.results_yaml import discover_processing_results

from pyama_qt.models.visualization import VisualizationModel
from pyama_qt.services import WorkerHandle, start_worker
from pyama_qt.views.visualization.view import VisualizationView

from .image_controller import VisualizationImageController
from .trace_controller import VisualizationTraceController

logger = logging.getLogger(__name__)


class VisualizationProjectController(QObject):
    """Coordinates project panel actions and background FOV loading."""

    def __init__(
        self,
        view: VisualizationView,
        model: VisualizationModel,
        image_controller: VisualizationImageController,
        trace_controller: VisualizationTraceController,
        *,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._model = model
        self._image_controller = image_controller
        self._trace_controller = trace_controller

        self._project_data: dict | None = None
        self._worker: WorkerHandle | None = None

        self._connect_view_signals()
        self._connect_model_signals()

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------
    def _connect_view_signals(self) -> None:
        panel = self._view.project_view
        panel.project_load_requested.connect(self._on_project_load_requested)
        panel.visualization_requested.connect(self._on_visualization_requested)

    def _connect_model_signals(self) -> None:
        project_model = self._model.project_model
        project_model.projectDataChanged.connect(self._handle_project_data)
        project_model.availableChannelsChanged.connect(self._handle_available_channels)
        project_model.statusMessageChanged.connect(self._handle_status_message)
        project_model.errorMessageChanged.connect(self._handle_error_message)
        project_model.isLoadingChanged.connect(self._handle_loading_state)

    # ------------------------------------------------------------------
    # View → Controller handlers
    # ------------------------------------------------------------------
    def _on_project_load_requested(self, project_path: Path) -> None:
        logger.info("Loading project from %s", project_path)
        self._model.project_model.set_is_loading(True)
        self._model.project_model.set_error_message("")
        self._model.project_model.set_status_message(
            f"Loading project: {project_path.name}"
        )
        try:
            project_results = discover_processing_results(project_path)
            project_data = project_results.to_dict()
            self._project_data = project_data
            self._model.project_model.set_project_path(project_path)
            self._model.project_model.set_project_data(project_data)
            channels = self._extract_available_channels(project_data)
            self._model.project_model.set_available_channels(channels)
            self._model.project_model.set_status_message(
                self._format_project_status(project_data)
            )
        except Exception as exc:
            message = self._format_project_error(project_path, exc)
            logger.exception("Failed to load project")
            self._model.project_model.set_error_message(message)
            self._view.status_bar.showMessage(message)
        finally:
            self._model.project_model.set_is_loading(False)

    def _on_visualization_requested(
        self, fov_idx: int, selected_channels: list[str]
    ) -> None:
        if not self._project_data:
            self._view.status_bar.showMessage("Load a project before visualizing")
            return

        self._cancel_worker()
        self._trace_controller.clear_trace_data()
        self._image_controller.clear_images()
        self._model.project_model.set_is_loading(True)
        self._model.project_model.set_status_message(f"Loading FOV {fov_idx:03d}…")
        self._view.project_view.set_visualize_button_text("Loading...")

        worker = _VisualizationWorker(
            project_data=self._project_data,
            fov_idx=fov_idx,
            selected_channels=selected_channels,
        )
        worker.progress_updated.connect(self._handle_worker_progress)
        worker.fov_data_loaded.connect(self._handle_worker_fov_loaded)
        worker.error_occurred.connect(self._handle_worker_error)
        worker.finished.connect(self._handle_worker_finished)

        self._worker = start_worker(
            worker,
            start_method="process_fov_data",
            finished_callback=self._cleanup_worker,
        )

    # ------------------------------------------------------------------
    # Worker callbacks
    # ------------------------------------------------------------------
    def _handle_worker_progress(self, message: str) -> None:
        self._model.project_model.set_status_message(message)

    def _handle_worker_fov_loaded(
        self,
        fov_idx: int,
        image_map: dict[str, np.ndarray],
        traces_path: Path | None,
    ) -> None:
        logger.info("FOV %s data loaded (%d image types)", fov_idx, len(image_map))
        self._image_controller.load_images(image_map)

        status_message: str
        if traces_path and traces_path.exists():
            self._model.project_model.set_status_message(
                f"Loading trace data for FOV {fov_idx:03d}..."
            )
            try:
                status_message = self._trace_controller.load_traces_from_path(
                    fov_idx, traces_path
                )
            except Exception as exc:
                logger.error("Failed to process trace data: %s", exc)
                status_message = self._trace_controller.handle_missing_trace_data(
                    fov_idx
                )
        else:
            status_message = self._trace_controller.handle_missing_trace_data(fov_idx)

        self._model.project_model.set_status_message(status_message)
        self._model.project_model.set_is_loading(False)

    def _handle_worker_error(self, message: str) -> None:
        logger.error("Visualization worker error: %s", message)
        self._model.project_model.set_is_loading(False)
        self._model.project_model.set_error_message(message)

    def _handle_worker_finished(self) -> None:
        self._model.project_model.set_is_loading(False)

    def _cleanup_worker(self) -> None:
        self._worker = None
        self._view.project_view.set_visualize_button_text("Start Visualization")

    def _cancel_worker(self) -> None:
        if self._worker:
            self._worker.stop()
            self._worker = None

    # ------------------------------------------------------------------
    # Model → Controller handlers
    # ------------------------------------------------------------------
    def _handle_project_data(self, project_data: dict) -> None:
        if project_data:
            self._view.project_view.set_project_details(project_data)

    def _handle_available_channels(self, channels: list[str]) -> None:
        self._view.project_view.set_available_channels(channels)
        self._view.project_view.reset_channel_selection()

    def _handle_status_message(self, message: str) -> None:
        self._view.project_view.set_status_message(message)
        if message:
            self._view.status_bar.showMessage(message)

    def _handle_error_message(self, message: str) -> None:
        if message:
            self._view.status_bar.showMessage(message)

    def _handle_loading_state(self, is_loading: bool) -> None:
        self._view.project_view.set_loading(is_loading)
        if not is_loading:
            self._view.project_view.set_visualize_button_text("Start Visualization")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_available_channels(project_data: dict) -> list[str]:
        if not project_data.get("fov_data"):
            return []
        first_fov = next(iter(project_data["fov_data"].values()))
        channels = list(first_fov.keys())
        if "traces" in channels:
            channels.remove("traces")
        return sorted(channels)

    @staticmethod
    def _format_project_status(project_data: dict) -> str:
        has_project_file = project_data.get("has_project_file", False)
        status = project_data.get("processing_status", "unknown")
        n_fov = project_data.get("n_fov", 0)
        if has_project_file:
            status_msg = f"Project loaded: {n_fov} FOVs, Status: {status.title()}"
            if status != "completed":
                status_msg += " ⚠"
            return status_msg
        return f"Project loaded: {n_fov} FOVs"

    @staticmethod
    def _format_project_error(project_path: Path, exc: Exception) -> str:
        message = str(exc)
        if "No FOV directories found" in message:
            return (
                f"No data found in {project_path}.\n"
                "Ensure the directory contains FOV subdirectories."
            )
        return message


class _VisualizationWorker(QObject):
    """Worker for loading and preprocessing FOV data in background."""

    progress_updated = Signal(str)
    fov_data_loaded = Signal(int, dict, object)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(
        self,
        *,
        project_data: dict,
        fov_idx: int,
        selected_channels: list[str],
    ) -> None:
        super().__init__()
        self._project_data = project_data
        self._fov_idx = fov_idx
        self._selected_channels = selected_channels

    def process_fov_data(self) -> None:
        try:
            self.progress_updated.emit(f"Loading data for FOV {self._fov_idx:03d}…")
            if self._fov_idx not in self._project_data["fov_data"]:
                self.error_occurred.emit(
                    f"FOV {self._fov_idx} not found in project data"
                )
                return

            fov_data = self._project_data["fov_data"][self._fov_idx]
            image_types = [
                channel for channel in self._selected_channels if channel in fov_data
            ]

            if not image_types:
                self.error_occurred.emit("No image data found for selected channels")
                return

            image_map: dict[str, np.ndarray] = {}

            for idx, image_type in enumerate(image_types, start=1):
                self.progress_updated.emit(
                    f"Loading {image_type} ({idx}/{len(image_types)})…"
                )
                image_path = Path(fov_data[image_type])
                if not image_path.exists():
                    logger.warning("Image file not found: %s", image_path)
                    continue
                image_data = np.load(image_path)
                processed = self._preprocess_for_visualization(image_data, image_type)
                image_map[image_type] = processed

            traces_value = fov_data.get("traces")
            traces_path = Path(traces_value) if traces_value else None
            self.fov_data_loaded.emit(self._fov_idx, image_map, traces_path)
            self.finished.emit()
        except Exception as exc:
            logger.exception("Error processing FOV data")
            self.error_occurred.emit(str(exc))

    def _preprocess_for_visualization(
        self, image_data: np.ndarray, data_type: str
    ) -> np.ndarray:
        if data_type.startswith("seg"):
            return image_data.astype(np.uint8, copy=False)

        if image_data.ndim == 3:
            frames = [self._normalize_frame(frame) for frame in image_data]
            return np.stack(frames, axis=0)
        return self._normalize_frame(image_data)

    def _normalize_frame(self, frame: np.ndarray) -> np.ndarray:
        if frame.dtype == np.uint8:
            return frame
        frame_float = frame.astype(np.float32)
        max_val = np.max(frame_float)
        if max_val <= 0:
            return np.zeros_like(frame, dtype=np.uint8)
        p1 = np.percentile(frame_float, 1)
        p99 = np.percentile(frame_float, 99)
        if p99 > p1:
            normalized = (frame_float - p1) / (p99 - p1)
            normalized = np.clip(normalized, 0, 1)
            return (normalized * 255).astype(np.uint8)
        normalized = frame_float / max_val
        normalized = np.clip(normalized, 0, 1)
        return (normalized * 255).astype(np.uint8)
