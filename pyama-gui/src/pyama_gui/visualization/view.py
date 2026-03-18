"""Consolidated view for the visualization tab."""

import logging
from dataclasses import fields as dataclass_fields
from pathlib import Path

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pyama.tasks import (
    VisualizationCache,
    extract_all_cells_data,
    get_dataframe,
    resolve_trace_path,
    update_cell_quality,
    write_dataframe,
)
from pyama.types import Channels, Result
from pyama_gui.app_view_model import AppViewModel
from pyama_gui.task_runner import TaskWorker, WorkerHandle, run_task
from pyama_gui.visualization.view_model import VisualizationViewModel
from pyama_gui.widgets import MplCanvas

logger = logging.getLogger(__name__)


class VisualizationLoaderWorker(TaskWorker):
    """Load selected FOV image data in the background."""

    def __init__(
        self, *, project_data: dict, fov_id: int, selected_channels: list[str]
    ) -> None:
        super().__init__()
        self._project_data = project_data
        self._fov_id = fov_id
        self._selected_channels = selected_channels
        self._cache = VisualizationCache()

    def run(self) -> None:
        try:
            fov_data = self._project_data["fov_data"].get(self._fov_id)
            if not fov_data:
                self.emit_failure(f"FOV {self._fov_id} not found in project data")
                return

            image_map = {}
            for channel in self._selected_channels:
                if channel not in fov_data:
                    continue
                path = Path(fov_data[channel])
                if path.exists():
                    cached = self._cache.get_or_build_uint8(path, channel)
                    image_map[channel] = np.load(cached.path)

            if not image_map:
                self.emit_failure("No image data found for selected channels")
                return

            seg_labeled_data = None
            for channel_name, image_data in image_map.items():
                if channel_name.startswith("seg_labeled_ch_"):
                    seg_labeled_data = image_data[0] if image_data.ndim == 3 else image_data
                    break

            payload = {
                "traces": self._get_trace_paths(fov_data),
                "seg_labeled": seg_labeled_data,
                "time_units": self._project_data.get("time_units", "min"),
            }
            self.emit_success(
                {
                    "fov_id": self._fov_id,
                    "image_map": image_map,
                    "payload": payload,
                }
            )
        except Exception as exc:  # pragma: no cover - worker boundary
            logger.exception("Error processing FOV data")
            self.emit_failure(str(exc))

    def _get_trace_paths(self, fov_data: dict) -> dict[str, Path]:
        traces_paths = {}
        combined_path = fov_data.get("traces")
        if combined_path:
            original_path = Path(combined_path)
            trace_path = resolve_trace_path(original_path)
            if trace_path and trace_path.exists():
                channels_info = self._project_data.get("channels")
                if not isinstance(channels_info, dict):
                    channels_info = {}
                try:
                    channels_model = Channels.from_serialized(channels_info)
                except ValueError:
                    channels_model = Channels()
                channel_ids: set[str] = set()
                pc_channel = channels_model.get_pc_channel()
                if pc_channel is not None:
                    channel_ids.add(str(pc_channel))
                for selection in channels_model.fl:
                    channel_ids.add(str(selection.channel))
                if not channel_ids:
                    channel_ids.add("0")
                for channel_id in sorted(channel_ids, key=lambda value: int(value)):
                    traces_paths[channel_id] = trace_path
        else:
            for key, value in fov_data.items():
                if key.startswith("traces_ch_"):
                    channel_id = key.split("_")[-1]
                    trace_path = Path(value)
                    if trace_path.exists():
                        traces_paths[channel_id] = trace_path
        return traces_paths


class VisualizationView(QWidget):
    """Consolidated visualization tab view."""

    def __init__(
        self,
        app_view_model: AppViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_view_model = app_view_model
        self.view_model = VisualizationViewModel(app_view_model, self)
        self._image_cache: dict[str, np.ndarray] = {}
        self._current_data_type = ""
        self._current_frame_index = 0
        self._max_frame_index = 0
        self._loader_handle: WorkerHandle | None = None
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
        self._build_ui()
        self._connect_signals()
        self._refresh_state()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.addWidget(self._build_workspace_section(), 1)
        layout.addWidget(self._build_image_section(), 2)
        layout.addWidget(self._build_trace_section(), 1)

    def _build_workspace_section(self) -> QGroupBox:
        group = QGroupBox("Workspace")
        layout = QVBoxLayout(group)

        self._project_details_text = QTextEdit()
        self._project_details_text.setReadOnly(True)
        layout.addWidget(self._project_details_text)

        selection_group = QGroupBox("Visualization Settings")
        selection_layout = QVBoxLayout(selection_group)

        fov_row = QHBoxLayout()
        self._fov_spinbox = QSpinBox()
        self._fov_max_label = QLabel("/ 0")
        fov_row.addWidget(QLabel("FOV:"))
        fov_row.addStretch()
        fov_row.addWidget(self._fov_spinbox)
        fov_row.addWidget(self._fov_max_label)
        selection_layout.addLayout(fov_row)

        self._channels_list = QListWidget()
        self._channels_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._channels_list.setEditTriggers(QListWidget.EditTrigger.NoEditTriggers)
        selection_layout.addWidget(self._channels_list)

        self._visualize_button = QPushButton("Start Visualization")
        selection_layout.addWidget(self._visualize_button)

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.hide()
        selection_layout.addWidget(self._progress_bar)

        layout.addWidget(selection_group)
        return group

    def _build_image_section(self) -> QGroupBox:
        group = QGroupBox("Image Viewer")
        layout = QVBoxLayout(group)

        controls_layout = QVBoxLayout()
        first_row = QHBoxLayout()
        first_row.addWidget(QLabel("Data Type:"))
        self._data_type_combo = QComboBox()
        first_row.addWidget(self._data_type_combo)
        controls_layout.addLayout(first_row)

        second_row = QHBoxLayout()
        self._prev_frame_10_button = QPushButton("<<")
        self._prev_frame_button = QPushButton("<")
        self._frame_label = QLabel("Frame 0/0")
        self._frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._next_frame_button = QPushButton(">")
        self._next_frame_10_button = QPushButton(">>")
        second_row.addWidget(self._prev_frame_10_button)
        second_row.addWidget(self._prev_frame_button)
        second_row.addWidget(self._frame_label)
        second_row.addWidget(self._next_frame_button)
        second_row.addWidget(self._next_frame_10_button)
        controls_layout.addLayout(second_row)
        layout.addLayout(controls_layout)

        self._image_canvas = MplCanvas(self)
        layout.addWidget(self._image_canvas)
        return group

    def _build_trace_section(self) -> QGroupBox:
        group = QGroupBox("Trace Plot")
        outer_layout = QVBoxLayout(group)

        selection_row = QHBoxLayout()
        selection_row.addWidget(QLabel("Feature:"))
        self._feature_dropdown = QComboBox()
        selection_row.addWidget(self._feature_dropdown)
        outer_layout.addLayout(selection_row)

        self._trace_canvas = MplCanvas(self)
        outer_layout.addWidget(self._trace_canvas)

        list_group = QGroupBox("Trace Selection")
        list_layout = QVBoxLayout(list_group)
        self._trace_list = QListWidget()
        self._trace_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._trace_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        list_layout.addWidget(self._trace_list)

        pagination_row = QHBoxLayout()
        self._trace_page_label = QLabel("Page 1 of 1")
        self._trace_prev_button = QPushButton("Previous")
        self._trace_next_button = QPushButton("Next")
        pagination_row.addWidget(self._trace_page_label)
        pagination_row.addWidget(self._trace_prev_button)
        pagination_row.addWidget(self._trace_next_button)
        list_layout.addLayout(pagination_row)

        self._save_button = QPushButton("Save Inspected CSV")
        list_layout.addWidget(self._save_button)
        outer_layout.addWidget(list_group)
        return group

    def _connect_signals(self) -> None:
        self.view_model.state_changed.connect(self._refresh_state)
        self._visualize_button.clicked.connect(self._start_visualization)
        self._data_type_combo.currentTextChanged.connect(self._on_data_type_selected)
        self._prev_frame_button.clicked.connect(lambda: self._set_current_frame(self._current_frame_index - 1))
        self._next_frame_button.clicked.connect(lambda: self._set_current_frame(self._current_frame_index + 1))
        self._prev_frame_10_button.clicked.connect(lambda: self._set_current_frame(self._current_frame_index - 10))
        self._next_frame_10_button.clicked.connect(lambda: self._set_current_frame(self._current_frame_index + 10))
        self._image_canvas.artist_picked.connect(self._on_artist_picked)
        self._image_canvas.artist_right_clicked.connect(self._on_artist_right_clicked)
        self._feature_dropdown.currentTextChanged.connect(lambda _text: self._plot_current_page())
        self._trace_list.itemClicked.connect(self._on_trace_item_clicked)
        self._trace_list.customContextMenuRequested.connect(self._on_trace_list_right_clicked)
        self._trace_prev_button.clicked.connect(self._on_trace_prev_page)
        self._trace_next_button.clicked.connect(self._on_trace_next_page)
        self._save_button.clicked.connect(self._on_save_clicked)

    @Slot()
    def _refresh_state(self) -> None:
        self._project_details_text.setPlainText(self.view_model.details_text)
        self._channels_list.clear()
        for channel in self.view_model.available_channels:
            item = QListWidgetItem(channel)
            item.setData(Qt.ItemDataRole.UserRole, channel)
            self._channels_list.addItem(item)
        self._channels_list.setVisible(bool(self.view_model.available_channels))
        self._visualize_button.setVisible(bool(self.view_model.available_channels))
        self._visualize_button.setEnabled(bool(self.view_model.available_channels) and self._loader_handle is None)
        self._fov_spinbox.setRange(self.view_model.min_fov, self.view_model.max_fov)
        self._fov_max_label.setText(f"/ {self.view_model.max_fov}")
        if self.view_model.project_data is None:
            self._clear_visualization_state()

    @Slot()
    def _start_visualization(self) -> None:
        if self._loader_handle is not None:
            return
        selected_channels = [
            str(item.data(Qt.ItemDataRole.UserRole))
            for item in self._channels_list.selectedItems()
        ]
        fov_id = int(self._fov_spinbox.value())
        self.view_model.start_visualization(fov_id, selected_channels)
        project_data = self.view_model.project_data
        if not project_data or not selected_channels:
            return
        worker = VisualizationLoaderWorker(
            project_data=project_data,
            fov_id=fov_id,
            selected_channels=selected_channels,
        )
        worker.finished.connect(self._on_loader_finished)
        self._loader_handle = run_task(
            worker,
            start_method="run",
            finished_callback=self._clear_loader_handle,
        )
        self._set_visualization_loading(True)

    @Slot(bool, object, str)
    def _on_loader_finished(self, success: bool, result: object, message: str) -> None:
        self._set_visualization_loading(False)
        if not success:
            self.app_view_model.set_status_message(f"Visualization error: {message}")
            return
        payload = dict(result)
        image_map = payload["image_map"]
        self._clear_visualization_state()
        self._image_cache = image_map
        self._max_frame_index = max(
            (arr.shape[0] - 1 for arr in image_map.values() if arr.ndim == 3),
            default=0,
        )
        self._update_frame_label()
        self._data_type_combo.blockSignals(True)
        self._data_type_combo.clear()
        self._data_type_combo.addItems(list(image_map.keys()))
        self._data_type_combo.blockSignals(False)
        if image_map:
            self._on_data_type_selected(next(iter(image_map.keys())))
        self._set_current_frame(0)
        self._load_trace_data(payload["payload"])

    def _clear_loader_handle(self) -> None:
        self._loader_handle = None

    def _set_visualization_loading(self, is_loading: bool) -> None:
        if is_loading:
            self._progress_bar.setVisible(True)
            self._progress_bar.setRange(0, 0)
            self._visualize_button.setText("Loading...")
            self._visualize_button.setEnabled(False)
        else:
            self._progress_bar.hide()
            self._visualize_button.setText("Start Visualization")
            self._visualize_button.setEnabled(bool(self.view_model.available_channels))

    @Slot(str)
    def _on_data_type_selected(self, data_type: str) -> None:
        if data_type and data_type in self._image_cache:
            self._current_data_type = data_type
            self._render_current_frame()

    @Slot(str)
    def _on_artist_picked(self, artist_id: str) -> None:
        if artist_id.startswith("cell_"):
            self._select_trace(artist_id.split("_")[1])
        elif artist_id.startswith("trace_"):
            self._select_trace(artist_id.split("_")[1])

    @Slot(str)
    def _on_artist_right_clicked(self, artist_id: str) -> None:
        if artist_id.startswith("trace_"):
            self._toggle_trace_quality(artist_id.split("_")[1])

    @Slot(QListWidgetItem)
    def _on_trace_item_clicked(self, item: QListWidgetItem) -> None:
        trace_id = item.data(Qt.ItemDataRole.UserRole)
        if trace_id:
            self._set_active_trace(str(trace_id))

    @Slot(object)
    def _on_trace_list_right_clicked(self, pos) -> None:
        item = self._trace_list.itemAt(pos)
        if item is not None:
            trace_id = item.data(Qt.ItemDataRole.UserRole)
            if trace_id:
                self._toggle_trace_quality(str(trace_id))

    def _load_trace_data(self, payload: dict) -> None:
        self._clear_trace_state()
        traces_entry = payload.get("traces", {})
        candidate_paths: list[Path] = []
        if isinstance(traces_entry, dict):
            for value in traces_entry.values():
                path_obj = Path(value)
                if path_obj not in candidate_paths:
                    candidate_paths.append(path_obj)
        elif traces_entry:
            candidate_paths.append(Path(traces_entry))
        if not candidate_paths:
            return
        csv_path = resolve_trace_path(candidate_paths[0])
        if csv_path is None:
            self.app_view_model.set_status_message(f"Invalid trace path: {candidate_paths[0]}")
            return
        try:
            df = get_dataframe(csv_path)
            base_fields = ["fov"] + [field.name for field in dataclass_fields(Result)]
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
            cells_data = extract_all_cells_data(self._processing_df)
            for cell_id, data in cells_data.items():
                self._good_status[cell_id] = data["quality"]
                frame = data["features"]["frame"]
                features = {key: value for key, value in data["features"].items() if key != "frame"}
                self._trace_frames[cell_id] = frame
                self._trace_features[cell_id] = features
                self._trace_positions[cell_id] = {
                    "frames": data["positions"]["frames"],
                    "x": data["positions"]["position_x"],
                    "y": data["positions"]["position_y"],
                }
            self._trace_ids = sorted(self._trace_features.keys(), key=int)
            self._trace_page = 0
            self._update_feature_dropdown()
            self._update_trace_pagination()
            self._populate_trace_table()
            self._plot_current_page()
            self._emit_position_overlays()
            self.app_view_model.set_status_message(
                f"{csv_path.name} loaded from {csv_path.parent}"
            )
        except Exception as exc:
            logger.error("Failed to load trace data from %s: %s", csv_path, exc)
            self.app_view_model.set_status_message(f"Error loading traces: {exc}")

    def _set_current_frame(self, index: int) -> None:
        index = max(0, min(index, self._max_frame_index))
        if index == self._current_frame_index:
            return
        self._current_frame_index = index
        self._update_frame_label()
        self._render_current_frame()
        self._emit_position_overlays()

    def _update_frame_label(self) -> None:
        self._frame_label.setText(f"Frame {self._current_frame_index}/{self._max_frame_index}")

    def _render_current_frame(self) -> None:
        image = self._image_cache.get(self._current_data_type)
        if image is None:
            self._image_canvas.clear()
            return
        frame = image[self._current_frame_index] if image.ndim == 3 else image
        self._image_canvas.plot_image(frame, cmap="gray", vmin=0, vmax=255)

    def _plot_current_page(self) -> None:
        feature = self._feature_dropdown.currentText()
        if not feature or not self._trace_ids:
            self._trace_canvas.clear()
            return
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
        self._trace_canvas.plot_lines(
            lines,
            styles,
            title="",
            x_label="Frame",
            y_label=feature,
        )

    def _visible_trace_ids(self) -> list[str]:
        start = self._trace_page * self._items_per_page
        return self._trace_ids[start : start + self._items_per_page]

    def _populate_trace_table(self) -> None:
        self._trace_list.blockSignals(True)
        self._trace_list.clear()
        for trace_id in self._visible_trace_ids():
            item = QListWidgetItem(f"Trace {trace_id}")
            item.setData(Qt.ItemDataRole.UserRole, trace_id)
            is_good = self._good_status.get(trace_id, False)
            is_active = trace_id == self._active_trace_id
            if not is_good:
                color = QColor("green")
            elif is_active:
                color = QColor("red")
            else:
                color = QColor("blue")
            item.setForeground(color)
            self._trace_list.addItem(item)
        self._trace_list.blockSignals(False)

    def _update_trace_pagination(self) -> None:
        total_pages = max(1, (len(self._trace_ids) + self._items_per_page - 1) // self._items_per_page)
        self._trace_page_label.setText(f"Page {self._trace_page + 1} of {total_pages}")
        self._trace_prev_button.setEnabled(self._trace_page > 0)
        self._trace_next_button.setEnabled(self._trace_page < total_pages - 1)

    @Slot()
    def _on_trace_prev_page(self) -> None:
        if self._trace_page <= 0:
            return
        self._trace_page -= 1
        self._set_active_trace(None)
        self._update_trace_pagination()
        self._populate_trace_table()
        self._plot_current_page()
        self._emit_position_overlays()

    @Slot()
    def _on_trace_next_page(self) -> None:
        total_pages = max(1, (len(self._trace_ids) + self._items_per_page - 1) // self._items_per_page)
        if self._trace_page >= total_pages - 1:
            return
        self._trace_page += 1
        self._set_active_trace(None)
        self._update_trace_pagination()
        self._populate_trace_table()
        self._plot_current_page()
        self._emit_position_overlays()

    def _select_trace(self, trace_id: str) -> None:
        if trace_id not in self._trace_ids:
            return
        index = self._trace_ids.index(trace_id)
        page = index // self._items_per_page
        if page != self._trace_page:
            self._trace_page = page
            self._update_trace_pagination()
            self._populate_trace_table()
        self._set_active_trace(trace_id)

    def _set_active_trace(self, trace_id: str | None) -> None:
        if self._active_trace_id == trace_id:
            return
        self._active_trace_id = trace_id
        self._populate_trace_table()
        self._plot_current_page()
        self._emit_position_overlays()

    def _toggle_trace_quality(self, trace_id: str) -> None:
        if trace_id not in self._good_status:
            return
        self._good_status[trace_id] = not self._good_status[trace_id]
        if not self._good_status[trace_id] and self._active_trace_id == trace_id:
            self._set_active_trace(None)
        self._populate_trace_table()
        self._plot_current_page()
        self._emit_position_overlays()

    def _emit_position_overlays(self) -> None:
        for key in list(self._image_canvas._overlay_artists):
            if key.startswith("trace_"):
                self._image_canvas.remove_overlay(key)
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
            self._image_canvas.plot_overlay(
                f"trace_{trace_id}",
                {
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

    def _update_feature_dropdown(self) -> None:
        self._feature_dropdown.blockSignals(True)
        self._feature_dropdown.clear()
        all_features = set()
        for trace_data in self._trace_features.values():
            all_features.update(trace_data.keys())
        self._feature_dropdown.addItems(sorted(all_features))
        self._feature_dropdown.blockSignals(False)

    @Slot()
    def _on_save_clicked(self) -> None:
        if self._processing_df is None or self._traces_csv_path is None:
            self.app_view_model.set_status_message("No data to save.")
            return
        updated_quality = pd.DataFrame(self._good_status.items(), columns=["cell", "good"])
        updated_quality["cell"] = updated_quality["cell"].astype(int)
        updated_df = update_cell_quality(self._processing_df, updated_quality)
        if self._inspected_path and self._inspected_path.name.endswith("_inspected.csv"):
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
        self._trace_list.clear()
        self._trace_canvas.clear()
        self._feature_dropdown.clear()
        self._update_trace_pagination()
        for key in list(self._image_canvas._overlay_artists):
            if key.startswith("trace_"):
                self._image_canvas.remove_overlay(key)

    def _clear_visualization_state(self) -> None:
        self._image_cache.clear()
        self._current_data_type = ""
        self._current_frame_index = 0
        self._max_frame_index = 0
        self._data_type_combo.clear()
        self._update_frame_label()
        self._image_canvas.clear()
        self._image_canvas.clear_overlays()
        self._clear_trace_state()
