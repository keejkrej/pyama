"""Qt view model for the aligner workflow."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from PySide6 import QtCore

from .adapters import ReaderSession, open_reader
from .grid import GridCell, GridSpec, auto_excluded_cells, cell_at, enumerate_grid
from .ui.qt import WorkerThread
from .workspace import Alignment, RoiRecord, cell_bbox_union, crop_rois, save_alignment, save_bbox

ReaderFactory = Callable[[Path], ReaderSession]


class AlignerViewModel(QtCore.QObject):
    frame_changed = QtCore.Signal(object)
    grid_changed = QtCore.Signal(object, object, object)
    frame_limits_changed = QtCore.Signal(int, int, int, int)
    source_open_changed = QtCore.Signal(bool)
    progress_changed = QtCore.Signal(object)
    status_changed = QtCore.Signal(str)

    def __init__(
        self,
        *,
        reader_factory: ReaderFactory = open_reader,
        cropper: Callable[..., list[RoiRecord]] = crop_rois,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.reader_factory = reader_factory
        self.cropper = cropper
        self.session: ReaderSession | None = None
        self.source_path: Path | None = None
        self.workspace_path = Path.cwd()
        self.grid_spec = GridSpec()
        self.excluded: set[int] = set()
        self.pos = 0
        self.time = 0
        self.channel = 0
        self.z = 0
        self.worker: WorkerThread | None = None
        self.image_width: int | None = None
        self.image_height: int | None = None

    def open_source(self, path: Path) -> None:
        self.close()
        self.source_path = path.expanduser()
        self.session = self.reader_factory(self.source_path)
        info = self.session.info
        self.pos = min(self.pos, max(info.n_pos - 1, 0))
        self.time = min(self.time, max(info.n_time - 1, 0))
        self.channel = min(self.channel, max(info.n_chan - 1, 0))
        self.z = min(self.z, max(info.n_z - 1, 0))
        self.frame_limits_changed.emit(
            max(info.n_pos - 1, 0),
            max(info.n_time - 1, 0),
            max(info.n_chan - 1, 0),
            max(info.n_z - 1, 0),
        )
        self.source_open_changed.emit(True)
        self.update_frame()

    def set_workspace_path(self, path: Path) -> None:
        self.workspace_path = path

    def set_frame_indices(self, pos: int, time: int, channel: int, z: int) -> None:
        self.pos = pos
        self.time = time
        self.channel = channel
        self.z = z
        self.update_frame()

    def set_grid_spec(self, spec: GridSpec) -> None:
        self.grid_spec = spec
        self.update_overlay()

    def update_frame(self) -> None:
        if self.session is None:
            return
        frame = self.session.read_frame(self.pos, self.time, self.channel, self.z)
        self.image_height, self.image_width = frame.shape[:2]
        self.frame_changed.emit(frame)
        self.update_overlay()

    def update_overlay(self) -> None:
        spec = self.grid_spec
        image_width, image_height = self._grid_bounds()
        self.grid_changed.emit(
            enumerate_grid(spec, image_width, image_height),
            set(self.excluded),
            lambda x, y: cell_at(spec, x, y, image_width, image_height),
        )

    @QtCore.Slot(int)
    def toggle_cell(self, index: int) -> None:
        if index in self.excluded:
            self.excluded.remove(index)
        else:
            self.excluded.add(index)
        self.update_overlay()

    def auto_exclude(self) -> None:
        if self.session is None:
            return
        image_width, image_height = self._grid_bounds()
        if image_width is None or image_height is None:
            return
        self.excluded |= auto_excluded_cells(self.grid_spec, image_width, image_height)
        self.update_overlay()

    def reset_exclusions(self) -> None:
        self.excluded.clear()
        self.update_overlay()

    def exclude_all(self) -> None:
        self.excluded = {cell.index for cell in self.current_cells()}
        self.update_overlay()

    def active_cells(self) -> Iterable[GridCell]:
        return (cell for cell in self.current_cells() if cell.index not in self.excluded)

    def current_cells(self) -> list[GridCell]:
        image_width, image_height = self._grid_bounds()
        return enumerate_grid(self.grid_spec, image_width, image_height)

    def _grid_bounds(self) -> tuple[int | None, int | None]:
        if self.image_width is not None and self.image_height is not None:
            return self.image_width, self.image_height
        if self.session is not None:
            info = self.session.info
            if info.size_x is not None and info.size_y is not None:
                return info.size_x, info.size_y
        return None, None

    def save_alignment_files(self) -> None:
        if self.source_path is None:
            return
        bbox = cell_bbox_union(self.active_cells())
        save_bbox(self.workspace_path, self.pos, bbox)
        save_alignment(
            self.workspace_path,
            Alignment(
                pos=self.pos,
                source=str(self.source_path),
                grid=self.grid_spec,
                excluded=set(self.excluded),
            ),
        )
        self.status_changed.emit("Saved alignment")

    def start_crop(self) -> None:
        if self.session is None or self.source_path is None:
            return
        self.save_alignment_files()
        self.worker = WorkerThread(
            self.cropper,
            self.session,
            self.workspace_path,
            source=str(self.source_path),
            pos=self.pos,
            grid=self.grid_spec,
            excluded=set(self.excluded),
        )
        self.worker.progress.connect(self.progress_changed.emit)
        self.worker.failed.connect(self.status_changed.emit)
        self.worker.succeeded.connect(self._on_crop_succeeded)
        self.worker.start()

    def cancel_crop(self) -> None:
        if self.worker is not None:
            self.worker.cancel.cancel()

    @QtCore.Slot(object)
    def _on_crop_succeeded(self, records: list[RoiRecord]) -> None:
        self.status_changed.emit(f"Wrote {len(records)} ROIs")

    def close(self) -> None:
        if self.session is not None:
            self.session.close()
            self.session = None
            self.image_width = None
            self.image_height = None
            self.source_open_changed.emit(False)
