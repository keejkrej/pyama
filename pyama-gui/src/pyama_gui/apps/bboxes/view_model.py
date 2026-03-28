"""View-model for the bbox alignment tab."""

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal
from pyama_gui.apps.alignment import (
    build_bbox_csv,
    clear_excluded_cell_ids,
    collect_edge_cell_ids,
    count_visible_cells,
    create_default_grid,
    merge_excluded_cell_ids,
    normalize_grid_state,
    set_excluded_cell_ids_for_position,
    toggle_excluded_cell_ids,
)
from pyama.io.microscopy import inspect_microscopy_file
from pyama.types import MicroscopyMetadata
from pyama_gui.app_view_model import AppViewModel
from pyama_gui.apps.bboxes.canvas_backend import AlignCanvasBackendServer
from pyama_gui.task_runner import TaskWorker, WorkerHandle, run_task
from pyama_gui.types import BBoxesViewState

logger = logging.getLogger(__name__)

_DEFAULT_CONTRAST_DOMAIN = {"min": 0, "max": 65535}


def _format_time_value(value: float) -> str:
    rounded = round(float(value))
    if abs(float(value) - rounded) < 1e-9:
        return str(int(rounded))
    return f"{float(value):.3f}".rstrip("0").rstrip(".")


def _normalize_contrast(
    contrast: dict[str, int] | None,
    *,
    domain_min: int,
    domain_max: int,
) -> dict[str, int]:
    if contrast is None:
        raise ValueError("contrast window is required")

    minimum = max(domain_min, min(int(contrast["min"]), domain_max - 1))
    maximum = max(minimum + 1, min(int(contrast["max"]), domain_max))
    return {"min": minimum, "max": maximum}


class MicroscopyMetadataWorker(TaskWorker):
    """Load microscopy metadata for bbox alignment."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path

    def run(self) -> None:
        try:
            if self.cancelled:
                self.emit_failure("Loading cancelled")
                return
            self.emit_success(inspect_microscopy_file(self._path))
        except Exception as exc:  # pragma: no cover - worker boundary
            logger.exception("Failed to inspect microscopy file %s", self._path)
            self.emit_failure(str(exc))


class BBoxesViewModel(QObject):
    """Tab-level state and commands for bbox alignment."""

    state_changed = Signal()

    def __init__(
        self,
        app_view_model: AppViewModel,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_view_model = app_view_model
        self._workspace_dir = app_view_model.workspace_dir
        self._microscopy_path = app_view_model.microscopy_path
        self._metadata: MicroscopyMetadata | None = None
        self._position_options: list[tuple[str, int]] = []
        self._channel_options: list[tuple[str, int]] = []
        self._z_options: list[tuple[str, int]] = []
        self._selected_position: int | None = None
        self._selected_channel: int | None = None
        self._selected_z: int | None = None
        self._selected_frame = 0
        self._grid = normalize_grid_state(create_default_grid())
        self._excluded_cell_ids_by_position: dict[int, list[str]] = (
            clear_excluded_cell_ids()
        )
        self._frame_size: tuple[int, int] | None = None
        self._included_count = 0
        self._excluded_count = 0
        self._contrast_mode = "manual"
        self._contrast_domain = dict(_DEFAULT_CONTRAST_DOMAIN)
        self._contrast_min = int(self._contrast_domain["min"])
        self._contrast_max = int(self._contrast_domain["max"])
        self._auto_contrast_request_token = 0
        self._loading_metadata = False
        self._loading_frame = False
        self._metadata_handle: WorkerHandle | None = None
        self._backend_error_message: str | None = None
        self._backend_server = AlignCanvasBackendServer()
        self._backend_url = ""

        try:
            self._backend_server.start()
            self._backend_url = self._backend_server.url
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to start Align canvas backend")
            self._backend_error_message = str(exc)

        self.app_view_model.workspace_changed.connect(self._on_workspace_changed)
        self.app_view_model.microscopy_changed.connect(self._on_microscopy_changed)
        if self._microscopy_path is not None:
            self._start_metadata_load(self._microscopy_path)

    @property
    def state(self) -> BBoxesViewState:
        return BBoxesViewState(
            microscopy_path_label=str(self._microscopy_path)
            if self._microscopy_path
            else "",
            workspace_path_label=str(self._workspace_dir)
            if self._workspace_dir
            else "",
            position_options=list(self._position_options),
            channel_options=list(self._channel_options),
            z_options=list(self._z_options),
            selected_position=self._selected_position,
            selected_channel=self._selected_channel,
            selected_z=self._selected_z,
            frame_max=max(0, (self._metadata.n_frames - 1) if self._metadata else 0),
            selected_frame=self._selected_frame,
            time_values=self._time_values(),
            time_value_label=self._time_value_label(),
            grid_values=dict(self._grid),
            included_count=self._included_count,
            excluded_count=self._excluded_count,
            contrast_domain_min=int(self._contrast_domain["min"]),
            contrast_domain_max=int(self._contrast_domain["max"]),
            contrast_min=int(self._contrast_min),
            contrast_max=int(self._contrast_max),
            loading_metadata=self._loading_metadata,
            loading_frame=self._loading_frame,
            can_save=self._can_save(),
            can_disable_edge=self._can_disable_edge(),
            save_path_label=str(self._save_path()) if self._can_save() else "",
        )

    def shutdown(self) -> None:
        self._cancel_workers()
        self._end_frame_loading()
        self._backend_server.stop()

    def canvas_payload(self, *, selection_mode: bool) -> dict[str, object]:
        return {
            "backendUrl": self._backend_url or None,
            "source": self._canvas_source(),
            "request": self._canvas_request(),
            "contrast": {
                "mode": self._contrast_mode,
                "value": {
                    "min": int(self._contrast_min),
                    "max": int(self._contrast_max),
                }
                if self._contrast_mode == "manual"
                else None,
            },
            "autoContrastRequestToken": int(self._auto_contrast_request_token),
            "grid": dict(self._grid),
            "excludedCellIds": sorted(self._active_excluded_cell_ids()),
            "selectionMode": selection_mode,
            "emptyText": self._empty_text(),
            "messages": self._canvas_messages(),
        }

    def handle_canvas_grid_changed(self, payload: Any) -> None:
        next_grid = normalize_grid_state(payload if isinstance(payload, dict) else None)
        if next_grid == self._grid:
            return
        self._grid = next_grid
        self._update_counts()
        self.state_changed.emit()

    def handle_canvas_excluded_cells_toggled(self, payload: Any) -> None:
        position_id = self._selected_position
        if position_id is None or not isinstance(payload, list):
            return

        toggled_cell_ids = [value for value in payload if isinstance(value, str)]
        if not toggled_cell_ids:
            return
        current = self._excluded_cell_ids_by_position.get(position_id, [])
        next_cell_ids = toggle_excluded_cell_ids(current, toggled_cell_ids)
        self._excluded_cell_ids_by_position = set_excluded_cell_ids_for_position(
            self._excluded_cell_ids_by_position,
            position_id,
            next_cell_ids,
        )
        self._update_counts()
        self.state_changed.emit()

    def handle_canvas_frame_loaded(self, payload: Any) -> None:
        self._end_frame_loading()
        if not isinstance(payload, dict):
            return
        try:
            width = int(payload["width"])
            height = int(payload["height"])
        except (KeyError, TypeError, ValueError):
            return

        self._frame_size = (width, height)
        contrast_domain = payload.get("contrastDomain")
        if isinstance(contrast_domain, dict):
            domain_min = int(contrast_domain.get("min", self._contrast_domain["min"]))
            domain_max = int(contrast_domain.get("max", self._contrast_domain["max"]))
            if domain_min >= domain_max:
                domain_max = domain_min + 1
            self._contrast_domain = {"min": domain_min, "max": domain_max}

        applied = (
            payload.get("appliedContrast")
            or payload.get("suggestedContrast")
            or self._contrast_domain
        )
        if isinstance(applied, dict):
            normalized = self._normalized_contrast_window(
                int(applied.get("min", self._contrast_min)),
                int(applied.get("max", self._contrast_max)),
            )
            self._contrast_min = int(normalized["min"])
            self._contrast_max = int(normalized["max"])
        self._contrast_mode = "manual"
        self._update_counts()
        self.state_changed.emit()
        self.app_view_model.set_status_message("Microscopy frame loaded")

    def handle_canvas_frame_load_failed(self, payload: Any) -> None:
        self._end_frame_loading()
        self._frame_size = None
        self._update_counts()
        self.state_changed.emit()
        if isinstance(payload, dict) and isinstance(payload.get("message"), str):
            self.app_view_model.set_status_message(payload["message"])
        else:
            self.app_view_model.set_status_message("Failed to load microscopy frame.")

    def _on_workspace_changed(self, path: Path | None) -> None:
        self._workspace_dir = path
        self.state_changed.emit()

    def _on_microscopy_changed(self, path: Path | None) -> None:
        self._cancel_workers()
        self._end_frame_loading()
        self._microscopy_path = path
        self._metadata = None
        self._position_options = []
        self._channel_options = []
        self._z_options = []
        self._selected_position = None
        self._selected_channel = None
        self._selected_z = None
        self._selected_frame = 0
        self._excluded_cell_ids_by_position = clear_excluded_cell_ids()
        self._frame_size = None
        self._reset_contrast_state()
        self._loading_metadata = False
        self._update_counts()
        self.state_changed.emit()
        if path is None:
            return
        self._start_metadata_load(path)

    def set_selected_position(self, position_id: int) -> None:
        if self._selected_position == position_id:
            return
        self._selected_position = int(position_id)
        self._update_counts()
        self.state_changed.emit()
        self._request_frame_refresh()

    def set_selected_channel(self, channel_id: int) -> None:
        if self._selected_channel == channel_id:
            return
        self._selected_channel = int(channel_id)
        self.state_changed.emit()
        self._request_frame_refresh()

    def set_selected_z(self, z_idx: int) -> None:
        if self._selected_z == z_idx:
            return
        self._selected_z = int(z_idx)
        self.state_changed.emit()
        self._request_frame_refresh()

    def set_selected_frame(self, frame_idx: int) -> None:
        next_frame = max(0, int(frame_idx))
        if self._selected_frame == next_frame:
            return
        self._selected_frame = next_frame
        self.state_changed.emit()
        self._request_frame_refresh()

    def set_grid_patch(self, patch: dict[str, object]) -> None:
        next_grid = normalize_grid_state({**self._grid, **patch})
        if next_grid == self._grid:
            return
        self._grid = next_grid
        self._update_counts()
        self.state_changed.emit()

    def reset_grid(self) -> None:
        enabled = bool(self._grid.get("enabled", False))
        self._grid = normalize_grid_state({**create_default_grid(), "enabled": enabled})
        self._excluded_cell_ids_by_position = clear_excluded_cell_ids()
        self._update_counts()
        self.state_changed.emit()

    def disable_edge_cells(self) -> None:
        position_id = self._selected_position
        frame_size = self._frame_size
        if position_id is None or frame_size is None:
            return
        edge_cell_ids = collect_edge_cell_ids(
            int(frame_size[0]),
            int(frame_size[1]),
            self._grid,
        )
        if not edge_cell_ids:
            return
        current = self._excluded_cell_ids_by_position.get(position_id, [])
        next_cell_ids = merge_excluded_cell_ids(current, edge_cell_ids)
        if next_cell_ids == current:
            return
        self._excluded_cell_ids_by_position = set_excluded_cell_ids_for_position(
            self._excluded_cell_ids_by_position,
            position_id,
            next_cell_ids,
        )
        self._update_counts()
        self.state_changed.emit()

    def preview_contrast_window(self, minimum: int, maximum: int) -> None:
        normalized = self._normalized_contrast_window(minimum, maximum)
        next_min = int(normalized["min"])
        next_max = int(normalized["max"])
        if self._contrast_min == next_min and self._contrast_max == next_max:
            return
        self._contrast_min = next_min
        self._contrast_max = next_max
        self.state_changed.emit()

    def commit_contrast_window(self, minimum: int, maximum: int) -> None:
        if self._canvas_request() is None:
            return
        normalized = self._normalized_contrast_window(minimum, maximum)
        next_min = int(normalized["min"])
        next_max = int(normalized["max"])
        changed = self._contrast_min != next_min or self._contrast_max != next_max
        self._contrast_min = next_min
        self._contrast_max = next_max
        self._contrast_mode = "manual"
        if changed:
            self.state_changed.emit()
        self._request_frame_refresh()

    def auto_contrast_current_frame(self) -> None:
        if self._canvas_request() is None:
            return
        self._contrast_mode = "auto"
        self._auto_contrast_request_token += 1
        self.state_changed.emit()
        self._request_frame_refresh()

    def save_current_bboxes(self) -> None:
        frame_size = self._frame_size
        path = self._save_path()
        if frame_size is None or path is None:
            self.app_view_model.set_status_message(
                "Select a workspace, microscopy file, and preview frame first."
            )
            return

        csv_text = build_bbox_csv(
            int(frame_size[0]),
            int(frame_size[1]),
            self._grid,
            self._active_excluded_cell_ids(),
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{csv_text}\n", encoding="utf-8")
        self.app_view_model.set_status_message(f"Saved bbox CSV to {path}")

    def _start_metadata_load(self, path: Path) -> None:
        worker = MicroscopyMetadataWorker(path)
        worker.finished.connect(self._on_metadata_loaded)
        self._metadata_handle = run_task(
            worker,
            start_method="run",
            finished_callback=self._clear_metadata_handle,
        )
        self._loading_metadata = True
        self.state_changed.emit()
        self.app_view_model.begin_busy()
        self.app_view_model.set_status_message("Loading microscopy metadata...")

    def _on_metadata_loaded(
        self,
        success: bool,
        metadata: MicroscopyMetadata | None,
        message: str,
    ) -> None:
        self._loading_metadata = False
        self.app_view_model.end_busy()
        if not success or metadata is None:
            self.app_view_model.set_status_message(
                message or "Failed to load microscopy metadata."
            )
            self.state_changed.emit()
            return

        self._metadata = metadata
        self._position_options = [
            (str(position_id), int(position_id))
            for position_id in metadata.position_list
        ]
        self._channel_options = [
            (
                f"{index}: {channel_name}" if channel_name else str(index),
                index,
            )
            for index, channel_name in enumerate(metadata.channel_names)
        ]
        self._z_options = [
            (str(z_value), int(z_value)) for z_value in metadata.z_slices
        ]
        self._selected_position = (
            self._position_options[0][1] if self._position_options else None
        )
        self._selected_channel = (
            self._channel_options[0][1] if self._channel_options else None
        )
        self._selected_z = self._z_options[0][1] if self._z_options else None
        self._selected_frame = 0
        self._update_counts()
        self.state_changed.emit()
        self.app_view_model.set_status_message(
            f"{metadata.file_path.name} loaded for alignment"
        )
        self._request_frame_refresh()

    def _canvas_source(self) -> dict[str, str] | None:
        if self._microscopy_path is None:
            return None
        suffix = self._microscopy_path.suffix.lower()
        kind = "tif" if suffix in {".tif", ".tiff"} else "nd2"
        return {"kind": kind, "path": str(self._microscopy_path)}

    def _canvas_request(self) -> dict[str, int] | None:
        if (
            self._selected_position is None
            or self._selected_channel is None
            or self._selected_z is None
        ):
            return None
        return {
            "pos": int(self._selected_position),
            "channel": int(self._selected_channel),
            "time": int(self._selected_frame),
            "z": int(self._selected_z),
        }

    def _request_frame_refresh(self) -> None:
        if (
            self._canvas_request() is None
            or self._microscopy_path is None
            or not self._backend_url
        ):
            self._end_frame_loading()
            self._frame_size = None
            self._update_counts()
            self.state_changed.emit()
            if self._backend_error_message:
                self.app_view_model.set_status_message(self._backend_error_message)
            return
        already_loading = self._loading_frame
        self._frame_size = None
        self._loading_frame = True
        self._update_counts()
        self.state_changed.emit()
        if not already_loading:
            self.app_view_model.begin_busy()
        self.app_view_model.set_status_message("Loading microscopy frame...")

    def _end_frame_loading(self) -> None:
        if not self._loading_frame:
            return
        self._loading_frame = False
        self.app_view_model.end_busy()

    def _active_excluded_cell_ids(self) -> list[str]:
        if self._selected_position is None:
            return []
        return list(
            self._excluded_cell_ids_by_position.get(self._selected_position, [])
        )

    def _update_counts(self) -> None:
        frame_size = self._frame_size
        if frame_size is None or not bool(self._grid.get("enabled", False)):
            self._included_count = 0
            self._excluded_count = 0
            return
        included, excluded = count_visible_cells(
            int(frame_size[0]),
            int(frame_size[1]),
            self._grid,
            self._active_excluded_cell_ids(),
        )
        self._included_count = included
        self._excluded_count = excluded

    def _time_value_label(self) -> str:
        metadata = self._metadata
        if metadata is None:
            return "0"
        if 0 <= self._selected_frame < len(metadata.timepoints):
            return _format_time_value(metadata.timepoints[self._selected_frame])
        return str(self._selected_frame)

    def _time_values(self) -> list[str]:
        metadata = self._metadata
        if metadata is None:
            return []
        if len(metadata.timepoints) == metadata.n_frames:
            return [_format_time_value(value) for value in metadata.timepoints]
        return [str(index) for index in range(metadata.n_frames)]

    def _normalized_contrast_window(self, minimum: int, maximum: int) -> dict[str, int]:
        return _normalize_contrast(
            {"min": int(minimum), "max": int(maximum)},
            domain_min=int(self._contrast_domain["min"]),
            domain_max=int(self._contrast_domain["max"]),
        )

    def _reset_contrast_state(self) -> None:
        self._contrast_mode = "manual"
        self._contrast_domain = dict(_DEFAULT_CONTRAST_DOMAIN)
        self._contrast_min = int(self._contrast_domain["min"])
        self._contrast_max = int(self._contrast_domain["max"])
        self._auto_contrast_request_token = 0

    def _empty_text(self) -> str:
        if self._workspace_dir is None:
            return "Set a workspace folder from the Welcome tab to save bbox CSVs"
        if self._microscopy_path is None:
            return "Select a microscopy file from the Welcome tab"
        if self._metadata is not None and self._canvas_request() is None:
            return "No frames found in microscopy file"
        return "No frame loaded"

    def _canvas_messages(self) -> list[dict[str, str]]:
        if self._backend_error_message:
            return [{"tone": "error", "text": self._backend_error_message}]
        return []

    def _can_save(self) -> bool:
        return (
            self._workspace_dir is not None
            and self._microscopy_path is not None
            and self._selected_position is not None
            and self._frame_size is not None
            and bool(self._grid.get("enabled", False))
        )

    def _can_disable_edge(self) -> bool:
        return self._selected_position is not None and self._frame_size is not None

    def _save_path(self) -> Path | None:
        if self._workspace_dir is None or self._selected_position is None:
            return None
        return self._workspace_dir / "bbox" / f"Pos{self._selected_position}.csv"

    def _cancel_workers(self) -> None:
        if self._metadata_handle is not None:
            self._metadata_handle.cancel()
            self._metadata_handle = None
            if self._loading_metadata:
                self.app_view_model.end_busy()

    def _clear_metadata_handle(self) -> None:
        self._metadata_handle = None
