"""View-model for the visualization tab."""

import logging
from dataclasses import asdict, is_dataclass
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, Signal

from pyama.io.csv import extract_all_rois_data, get_dataframe, update_roi_quality, write_dataframe
from pyama.io.results import resolve_trace_path, scan_processing_results
from pyama.tasks import TaskStatus, VisualizationTaskRequest, submit_visualization
from pyama.types import RoiOverlay
from pyama_gui.app_view_model import AppViewModel
from pyama_gui.task_runner import TaskWorker, WorkerHandle, run_task
from pyama_gui.types.common import ListRowState, OverlaySpec, PageState, PlotSpec
from pyama_gui.types.visualization import VisualizationViewState

logger = logging.getLogger(__name__)


class ProjectLoaderWorker(TaskWorker):
    """Load workspace visualization metadata in the background."""

    def __init__(self, project_path: Path) -> None:
        super().__init__()
        self._project_path = project_path

    def run(self) -> None:
        try:
            project_results = scan_processing_results(self._project_path)
            if is_dataclass(project_results):
                payload = asdict(project_results)
            else:
                to_dict = getattr(project_results, "to_dict", None)
                if callable(to_dict):
                    payload = to_dict()
                else:
                    raise TypeError("Project results must be a dataclass or expose to_dict()")
            self.emit_success(payload)
        except Exception as exc:  # pragma: no cover - worker boundary
            logger.exception("Failed to load project")
            self.emit_failure(str(exc))


class VisualizationLoaderWorker(TaskWorker):
    """Load selected position image data in the background."""

    def __init__(
        self, *, project_data: dict, position_id: int, selected_channels: list[str]
    ) -> None:
        super().__init__()
        self._project_data = project_data
        self._position_id = position_id
        self._selected_channels = selected_channels

    def run(self) -> None:
        try:
            position_data = self._project_data["position_data"].get(self._position_id)
            if not position_data:
                self.emit_failure(f"Position {self._position_id} not found in project data")
                return

            image_map: dict[str, np.ndarray] = {}
            total_channels = max(len(self._selected_channels), 1)
            for index, channel in enumerate(self._selected_channels, start=1):
                if channel not in position_data:
                    continue
                path = Path(position_data[channel])
                if path.exists():
                    record = submit_visualization(
                        VisualizationTaskRequest(
                            source_path=path,
                            channel_id=channel,
                        )
                    )
                    snapshot = self.wait_for_task(
                        record,
                        progress_handler=lambda progress, idx=index: self.forward_progress(
                            int(
                                ((idx - 1) + (progress.percent or 0) / 100)
                                / total_channels
                                * 100
                            ),
                            progress.message,
                        ),
                    )
                    if snapshot.status != TaskStatus.COMPLETED:
                        self.emit_failure(
                            snapshot.error_message
                            or f"Visualization task failed for {channel}"
                        )
                        return
                    cached = snapshot.result
                    image_map[channel] = np.load(cached.path)

            if not image_map:
                self.emit_failure("No image data found for selected channels")
                return

            self.emit_success(
                {
                    "image_map": image_map,
                    "traces": self._get_trace_paths(position_data),
                }
            )
        except Exception as exc:  # pragma: no cover - worker boundary
            logger.exception("Error processing position data")
            self.emit_failure(str(exc))

    def _get_trace_paths(self, position_data: dict) -> dict[str, Path]:
        traces_paths: dict[str, Path] = {}
        combined_path = position_data.get("traces")
        if combined_path:
            original_path = Path(combined_path)
            trace_path = resolve_trace_path(original_path)
            if trace_path and trace_path.exists():
                channel_ids = {"0"}
                for channel_id in sorted(channel_ids, key=lambda value: int(value)):
                    traces_paths[channel_id] = trace_path
        else:
            for key, value in position_data.items():
                if key.startswith("traces_ch_"):
                    channel_id = key.split("_")[-1]
                    trace_path = Path(value)
                    if trace_path.exists():
                        traces_paths[channel_id] = trace_path
        return traces_paths


class VisualizationViewModel(QObject):
    """Tab-level state and commands for visualization."""

    state_changed = Signal()

    def __init__(
        self,
        app_view_model: AppViewModel,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_view_model = app_view_model
        self._workspace_dir = app_view_model.workspace_dir
        self._project_data: dict | None = None
        self._available_channels: list[str] = []
        self._selected_channels: list[str] = []
        self._selected_position = 0
        self._min_position = 0
        self._max_position = 0
        self._details_text = "Workspace: Not set"
        self._loading_project = False
        self._loading_visualization = False
        self._project_handle: WorkerHandle | None = None
        self._visualization_handle: WorkerHandle | None = None
        self._image_cache: dict[str, np.ndarray] = {}
        self._selected_data_type = ""
        self._current_frame_index = 0
        self._max_frame_index = 0
        self._trace_features: dict[str, dict[str, np.ndarray]] = {}
        self._trace_frames: dict[str, np.ndarray] = {}
        self._trace_positions: dict[str, dict[str, np.ndarray]] = {}
        self._good_status: dict[str, bool] = {}
        self._trace_ids: list[str] = []
        self._active_trace_id: str | None = None
        self._processing_df: pd.DataFrame | None = None
        self._traces_csv_path: Path | None = None
        self._inspected_path: Path | None = None
        self._trace_page = 0
        self._items_per_page = 10
        self._selected_feature = ""
        self.app_view_model.workspace_changed.connect(self._on_workspace_changed)
        self._sync_workspace_state()
        if self._workspace_dir is not None:
            self.load_workspace()

    @property
    def state(self) -> VisualizationViewState:
        return VisualizationViewState(
            details_text=self._details_text,
            available_channels=list(self._available_channels),
            selected_channels=list(self._selected_channels),
            min_position=self._min_position,
            max_position=self._max_position,
            selected_position=self._selected_position,
            loading_project=self._loading_project,
            loading_visualization=self._loading_visualization,
            data_types=list(self._image_cache),
            selected_data_type=self._selected_data_type,
            current_image=self._current_image(),
            frame_label=f"Frame {self._current_frame_index}/{self._max_frame_index}",
            trace_feature_options=self._trace_feature_options(),
            selected_feature=self._selected_feature,
            trace_rows=self._trace_rows(),
            trace_page=self._trace_page_state(),
            trace_plot=self._trace_plot(),
            overlays=self._overlay_specs(),
            can_visualize=bool(self._project_data and self._selected_channels),
            can_save=self._processing_df is not None
            and self._traces_csv_path is not None,
        )

    @property
    def workspace_dir(self) -> Path | None:
        return self._workspace_dir

    @property
    def details_text(self) -> str:
        return self._details_text

    @property
    def running(self) -> bool:
        return self._loading_project or self._loading_visualization

    def _on_workspace_changed(self, path: Path | None) -> None:
        self._workspace_dir = path
        self._sync_workspace_state()
        if path is not None:
            self.load_workspace()

    def _sync_workspace_state(self) -> None:
        self._project_data = None
        self._available_channels = []
        self._selected_channels = []
        self._selected_position = 0
        self._min_position = 0
        self._max_position = 0
        self._details_text = (
            "Workspace: Not set"
            if self._workspace_dir is None
            else f"Workspace: {self._workspace_dir}"
        )
        self._clear_visualization_state()
        self.state_changed.emit()

    def load_workspace(self) -> None:
        if self._loading_project:
            return
        if self._workspace_dir is None:
            self.app_view_model.set_status_message("Set a workspace folder first.")
            return

        worker = ProjectLoaderWorker(self._workspace_dir)
        worker.finished.connect(self._on_project_loaded)
        self._project_handle = run_task(
            worker,
            start_method="run",
            finished_callback=self._clear_project_handle,
        )
        self._loading_project = True
        self.state_changed.emit()
        self.app_view_model.begin_busy()
        self.app_view_model.set_status_message("Loading project data...")

    def set_selected_channels(self, channels: list[str]) -> None:
        self._selected_channels = list(channels)
        self.state_changed.emit()

    def set_selected_position(self, position_id: int) -> None:
        self._selected_position = int(position_id)
        self.state_changed.emit()

    def start_visualization(self) -> None:
        if self._loading_visualization:
            return
        if not self._project_data:
            self.app_view_model.set_status_message(
                "No project loaded. Please load a project first."
            )
            return
        if not self._selected_channels:
            self.app_view_model.set_status_message(
                "No channels selected for visualization."
            )
            return

        worker = VisualizationLoaderWorker(
            project_data=self._project_data,
            position_id=self._selected_position,
            selected_channels=self._selected_channels,
        )
        worker.progress_value.connect(self._on_visualization_progress)
        worker.finished.connect(self._on_visualization_loaded)
        self._visualization_handle = run_task(
            worker,
            start_method="run",
            finished_callback=self._clear_visualization_handle,
        )
        self._loading_visualization = True
        self.state_changed.emit()

    def set_selected_data_type(self, data_type: str) -> None:
        if not data_type or data_type == self._selected_data_type:
            return
        self._selected_data_type = data_type
        self.state_changed.emit()

    def set_selected_feature(self, feature_name: str) -> None:
        if not feature_name or feature_name == self._selected_feature:
            return
        self._selected_feature = feature_name
        self.state_changed.emit()

    def step_frame(self, delta: int) -> None:
        next_index = max(
            0, min(self._current_frame_index + delta, self._max_frame_index)
        )
        if next_index == self._current_frame_index:
            return
        self._current_frame_index = next_index
        self.state_changed.emit()

    def select_trace(self, trace_id: str) -> None:
        if trace_id not in self._trace_ids:
            return
        index = self._trace_ids.index(trace_id)
        page = index // self._items_per_page
        if page != self._trace_page:
            self._trace_page = page
        self._active_trace_id = trace_id
        self.state_changed.emit()

    def toggle_trace_quality(self, trace_id: str) -> None:
        if trace_id not in self._good_status:
            return
        self._good_status[trace_id] = not self._good_status[trace_id]
        if not self._good_status[trace_id] and self._active_trace_id == trace_id:
            self._active_trace_id = None
        self.state_changed.emit()

    def previous_trace_page(self) -> None:
        if self._trace_page <= 0:
            return
        self._trace_page -= 1
        self._active_trace_id = None
        self.state_changed.emit()

    def next_trace_page(self) -> None:
        total_pages = max(
            1, (len(self._trace_ids) + self._items_per_page - 1) // self._items_per_page
        )
        if self._trace_page >= total_pages - 1:
            return
        self._trace_page += 1
        self._active_trace_id = None
        self.state_changed.emit()

    def save_inspected_csv(self) -> None:
        if self._processing_df is None or self._traces_csv_path is None:
            self.app_view_model.set_status_message("No data to save.")
            return
        updated_quality = pd.DataFrame(
            self._good_status.items(),
            columns=pd.Index(["roi", "is_good"]),
        )
        updated_quality["roi"] = updated_quality["roi"].astype(int)
        updated_df = update_roi_quality(self._processing_df, updated_quality)
        if self._inspected_path and self._inspected_path.name.endswith(
            "_inspected.csv"
        ):
            save_path = self._inspected_path
        else:
            save_path = self._traces_csv_path.with_name(
                f"{self._traces_csv_path.stem}_inspected.csv"
            )
        try:
            write_dataframe(updated_df, save_path)
            self.app_view_model.set_status_message(
                f"{save_path.name} saved to {save_path.parent}"
            )
        except Exception as exc:
            self.app_view_model.set_status_message(f"Error saving data: {exc}")

    def _on_project_loaded(self, success: bool, result: object, message: str) -> None:
        self._loading_project = False
        self.state_changed.emit()
        self.app_view_model.end_busy()
        if not success:
            self.app_view_model.set_status_message(self._format_project_error(message))
            return

        if not isinstance(result, dict):
            self.app_view_model.set_status_message(
                "Project loader returned an invalid result."
            )
            return

        project_data = cast(dict[str, object], result)
        self._project_data = project_data
        self._available_channels = self._extract_available_channels(project_data)
        raw_position_data = project_data.get("position_data")
        position_data = raw_position_data if isinstance(raw_position_data, dict) else {}
        position_keys = list(position_data.keys())
        self._min_position, self._max_position = (
            (min(position_keys), max(position_keys)) if position_keys else (0, 0)
        )
        self._selected_position = self._min_position
        self._details_text = self._format_project_details(project_data)
        self.state_changed.emit()
        n_positions = project_data.get("n_positions", 0)
        project_path = project_data.get("project_path", "unknown folder")
        self.app_view_model.set_status_message(
            f"{n_positions} positions loaded from {project_path}"
        )

    def _on_visualization_loaded(
        self, success: bool, result: object, message: str
    ) -> None:
        self._loading_visualization = False
        self.state_changed.emit()
        if not success:
            self.app_view_model.set_status_message(f"Visualization error: {message}")
            return

        if not isinstance(result, dict):
            self.app_view_model.set_status_message(
                "Visualization loader returned an invalid result."
            )
            return

        payload = cast(dict[str, object], result)
        self._clear_visualization_state()
        image_map = payload.get("image_map")
        if not isinstance(image_map, dict):
            self.app_view_model.set_status_message(
                "Visualization payload is missing image data."
            )
            return
        self._image_cache = {
            str(channel): data
            for channel, data in image_map.items()
            if isinstance(data, np.ndarray)
        }
        self._selected_data_type = next(iter(self._image_cache), "")
        self._max_frame_index = max(
            (arr.shape[0] - 1 for arr in self._image_cache.values() if arr.ndim == 3),
            default=0,
        )
        self._current_frame_index = 0
        self._load_trace_data(payload.get("traces", {}))
        self.state_changed.emit()

    def _on_visualization_progress(self, percent: int, message: str) -> None:
        if message:
            self.app_view_model.set_status_message(f"{message} ({percent}%)")

    def _load_trace_data(self, traces_entry: object) -> None:
        candidate_paths: list[Path] = []
        if isinstance(traces_entry, dict):
            for value in traces_entry.values():
                if not isinstance(value, str | Path):
                    continue
                path_obj = Path(value)
                if path_obj not in candidate_paths:
                    candidate_paths.append(path_obj)
        elif isinstance(traces_entry, str | Path):
            candidate_paths.append(Path(traces_entry))
        if not candidate_paths:
            return
        csv_path = resolve_trace_path(candidate_paths[0])
        if csv_path is None:
            self.app_view_model.set_status_message(
                f"Invalid trace path: {candidate_paths[0]}"
            )
            return
        try:
            df = get_dataframe(csv_path)
            base_fields = ["position"] + [field.name for field in dataclass_fields(RoiOverlay)]
            missing = [col for col in base_fields if col not in df.columns]
            if missing:
                raise ValueError(
                    f"Trace CSV is missing required columns: {', '.join(sorted(missing))}"
                )
            base_cols = [col for col in base_fields if col in df.columns]
            base_set = set(base_fields)
            feature_cols = [col for col in df.columns if col not in base_set]
            if not feature_cols:
                raise ValueError("Trace CSV contains no feature columns.")
            ordered_columns = list(dict.fromkeys(base_cols + feature_cols))
            self._processing_df = df[ordered_columns].copy()
            self._traces_csv_path = candidate_paths[0]
            self._inspected_path = csv_path
            cells_data = extract_all_rois_data(self._processing_df)
            for cell_id, data in cells_data.items():
                self._good_status[cell_id] = data["quality"]
                frame = data["features"]["frame"]
                features = {
                    key: value
                    for key, value in data["features"].items()
                    if key != "frame"
                }
                self._trace_frames[cell_id] = frame
                self._trace_features[cell_id] = features
                self._trace_positions[cell_id] = {
                    "frames": data["positions"]["frames"],
                    "x": data["positions"]["x"],
                    "y": data["positions"]["y"],
                }
            self._trace_ids = [
                str(cell_id)
                for cell_id in sorted(
                    self._trace_features.keys(), key=lambda value: int(value)
                )
            ]
            self._trace_page = 0
            self._selected_feature = (
                self._trace_feature_options()[0]
                if self._trace_feature_options()
                else ""
            )
            self.app_view_model.set_status_message(
                f"{csv_path.name} loaded from {csv_path.parent}"
            )
        except Exception as exc:
            logger.error("Failed to load trace data from %s: %s", csv_path, exc)
            self.app_view_model.set_status_message(f"Error loading traces: {exc}")

    def _current_image(self) -> np.ndarray | None:
        image = self._image_cache.get(self._selected_data_type)
        if image is None:
            return None
        return image[self._current_frame_index] if image.ndim == 3 else image

    def _trace_feature_options(self) -> list[str]:
        all_features = set()
        for trace_data in self._trace_features.values():
            all_features.update(trace_data.keys())
        return sorted(all_features)

    def _visible_trace_ids(self) -> list[str]:
        start = self._trace_page * self._items_per_page
        return self._trace_ids[start : start + self._items_per_page]

    def _trace_rows(self) -> list[ListRowState]:
        rows: list[ListRowState] = []
        for trace_id in self._visible_trace_ids():
            is_good = self._good_status.get(trace_id, False)
            is_active = trace_id == self._active_trace_id
            color = "green" if not is_good else "red" if is_active else "blue"
            rows.append(
                ListRowState(
                    label=f"Trace {trace_id}",
                    value=trace_id,
                    color=color,
                    selected=is_active,
                )
            )
        return rows

    def _trace_page_state(self) -> PageState:
        total_pages = max(
            1, (len(self._trace_ids) + self._items_per_page - 1) // self._items_per_page
        )
        return PageState(
            label=f"Page {self._trace_page + 1} of {total_pages}",
            can_previous=self._trace_page > 0,
            can_next=self._trace_page < total_pages - 1,
        )

    def _trace_plot(self) -> PlotSpec | None:
        feature = self._selected_feature
        if not feature or not self._trace_ids:
            return None
        lines, styles = [], []
        for trace_id in self._visible_trace_ids():
            features = self._trace_features.get(trace_id)
            frames = self._trace_frames.get(trace_id)
            if features is None or frames is None or feature not in features:
                continue
            is_good = self._good_status.get(trace_id, False)
            is_active = trace_id == self._active_trace_id
            if not is_good:
                color = "green"
                alpha = 0.5
                linewidth = 1
            elif is_active:
                color = "red"
                alpha = 1.0
                linewidth = 2
            else:
                color = "blue"
                alpha = 0.5
                linewidth = 1
            lines.append((frames, features[feature]))
            styles.append({"color": color, "alpha": alpha, "linewidth": linewidth})
        if not lines:
            return None
        return PlotSpec(
            kind="lines",
            lines_data=lines,
            styles_data=styles,
            x_label="Frame",
            y_label=feature,
        )

    def _overlay_specs(self) -> list[OverlaySpec]:
        overlays: list[OverlaySpec] = []
        for trace_id in self._visible_trace_ids():
            pos_data = self._trace_positions.get(trace_id)
            if pos_data is None:
                continue
            matches = np.where(pos_data["frames"] == self._current_frame_index)[0]
            if len(matches) == 0:
                continue
            idx = matches[0]
            x = pos_data["x"][idx]
            y = pos_data["y"][idx]
            is_good = self._good_status.get(trace_id, False)
            is_active = trace_id == self._active_trace_id and is_good
            if not is_good:
                color = "green"
            elif is_active:
                color = "red"
            else:
                color = "blue"
            overlays.append(
                OverlaySpec(
                    overlay_id=f"trace_{trace_id}",
                    properties={
                        "type": "circle",
                        "xy": (x, y),
                        "radius": 40,
                        "edgecolor": color,
                        "facecolor": "none",
                        "linewidth": 2.0,
                        "alpha": 1.0,
                        "zorder": 10,
                    },
                )
            )
        return overlays

    def _clear_project_handle(self) -> None:
        self._project_handle = None

    def _clear_visualization_handle(self) -> None:
        self._visualization_handle = None

    @staticmethod
    def _extract_available_channels(project_data: dict) -> list[str]:
        if not project_data.get("position_data"):
            return []
        first_position = next(iter(project_data["position_data"].values()))
        channels = [key for key in first_position.keys() if not key.startswith("traces")]
        return sorted(channels)

    @staticmethod
    def _format_project_details(project_data: dict) -> str:
        details = [
            f"Project Path: {project_data.get('project_path', 'Unknown')}",
            f"Positions: {project_data.get('n_positions', 0)}",
        ]
        if project_data.get("position_data"):
            first_position = next(iter(project_data["position_data"].values()))
            details.append("Available Data:")
            details.extend([f"   * {data_type}" for data_type in first_position.keys()])
        return "\n".join(details)

    @staticmethod
    def _format_project_error(message: str) -> str:
        return message

    def _clear_trace_state(self) -> None:
        self._trace_features.clear()
        self._trace_frames.clear()
        self._trace_positions.clear()
        self._good_status.clear()
        self._trace_ids.clear()
        self._active_trace_id = None
        self._processing_df = None
        self._traces_csv_path = None
        self._inspected_path = None
        self._trace_page = 0
        self._selected_feature = ""

    def _clear_visualization_state(self) -> None:
        self._image_cache.clear()
        self._selected_data_type = ""
        self._current_frame_index = 0
        self._max_frame_index = 0
        self._clear_trace_state()
