"""Qt view model for ROI annotation editing."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from PySide6 import QtCore

from .annotations import Label, load_annotation, load_labels, save_annotation, save_labels
from .roi_io import read_roi_stack
from .workspace import RoiRecord, scan_roi_workspace


class AnnotatorViewModel(QtCore.QObject):
    roi_list_changed = QtCore.Signal(object)
    labels_changed = QtCore.Signal(object)
    label_selected_changed = QtCore.Signal(object)
    frame_limits_changed = QtCore.Signal(int, int, int)
    frame_changed = QtCore.Signal(object)
    mask_changed = QtCore.Signal(object)
    status_changed = QtCore.Signal(str)

    def __init__(
        self,
        root: Path | None = None,
        *,
        stack_reader: Callable[[Path], np.ndarray] = read_roi_stack,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.root = root or Path.cwd()
        self.stack_reader = stack_reader
        self.records: list[RoiRecord] = []
        self.labels: list[Label] = []
        self.stack: np.ndarray | None = None
        self.mask: np.ndarray | None = None
        self.current_row = -1
        self.time = 0
        self.channel = 0
        self.z = 0
        self.label_id: str | None = None
        self.undo_stack: list[np.ndarray] = []
        self.redo_stack: list[np.ndarray] = []
        self.lasso_points: list[tuple[int, int]] = []

    def load_workspace(self, root: Path) -> None:
        self.root = root
        self.labels = load_labels(root)
        if self.label_id is None and self.labels:
            self.label_id = self.labels[0].id
        self.labels_changed.emit(list(self.labels))
        if self.label_id is not None:
            self.label_selected_changed.emit(self.label_id)

        workspace = scan_roi_workspace(root)
        self.records = workspace.records
        self.roi_list_changed.emit([f"Pos{record.pos} Roi{record.roi}" for record in self.records])
        self.status_changed.emit(f"Found {len(self.records)} ROIs")
        if self.records:
            self.open_roi(0)
        else:
            self.current_row = -1
            self.stack = None
            self.mask = None
            self.mask_changed.emit(None)

    @QtCore.Slot(int)
    def open_roi(self, row: int) -> None:
        if row < 0 or row >= len(self.records):
            return
        self.current_row = row
        record = self.records[row]
        self.stack = self.stack_reader(Path(record.path))
        self.time = min(self.time, self.stack.shape[0] - 1)
        self.channel = min(self.channel, self.stack.shape[1] - 1)
        self.z = min(self.z, self.stack.shape[2] - 1)
        self.frame_limits_changed.emit(
            self.stack.shape[0] - 1,
            self.stack.shape[1] - 1,
            self.stack.shape[2] - 1,
        )
        self.mask = np.zeros(self.stack.shape[-2:], dtype=bool)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.lasso_points.clear()
        self.update_frame()

    def current_record(self) -> RoiRecord | None:
        if self.current_row < 0 or self.current_row >= len(self.records):
            return None
        return self.records[self.current_row]

    def set_frame_indices(self, time: int, channel: int, z: int) -> None:
        self.time = time
        self.channel = channel
        self.z = z
        self.update_frame()

    def set_label_id(self, label_id: str | None) -> None:
        self.label_id = label_id

    def update_frame(self) -> None:
        if self.stack is None:
            return
        frame = self.stack[self.time, self.channel, self.z]
        self.frame_changed.emit(frame)
        record = self.current_record()
        if record is not None:
            annotation, mask = load_annotation(
                self.root,
                pos=record.pos,
                roi=record.roi,
                channel=self.channel,
                time=self.time,
                z=self.z,
            )
            if annotation and annotation.label_id:
                self.label_id = annotation.label_id
                self.label_selected_changed.emit(annotation.label_id)
            self.mask = mask if mask is not None else np.zeros(frame.shape, dtype=bool)
        self.mask_changed.emit(self.mask)

    def paint_at(self, x: int, y: int, mode: str, radius: int) -> None:
        if self.mask is None or not self._contains(x, y):
            return
        self.push_undo()
        y1, y2 = max(0, y - radius), min(self.mask.shape[0], y + radius + 1)
        x1, x2 = max(0, x - radius), min(self.mask.shape[1], x + radius + 1)
        yy, xx = np.ogrid[y1:y2, x1:x2]
        brush = (yy - y) ** 2 + (xx - x) ** 2 <= radius**2
        self.mask[y1:y2, x1:x2][brush] = mode == "brush"
        self.mask_changed.emit(self.mask)

    def add_lasso_point(self, x: int, y: int) -> None:
        if self.mask is None or not self._contains(x, y):
            return
        self.lasso_points.append((x, y))
        self.status_changed.emit(f"Lasso points: {len(self.lasso_points)}")

    def push_undo(self) -> None:
        if self.mask is not None:
            self.undo_stack.append(self.mask.copy())
            self.redo_stack.clear()

    def undo(self) -> None:
        if self.mask is None or not self.undo_stack:
            return
        self.redo_stack.append(self.mask.copy())
        self.mask = self.undo_stack.pop()
        self.mask_changed.emit(self.mask)

    def redo(self) -> None:
        if self.mask is None or not self.redo_stack:
            return
        self.undo_stack.append(self.mask.copy())
        self.mask = self.redo_stack.pop()
        self.mask_changed.emit(self.mask)

    def discard(self) -> None:
        if self.stack is None:
            return
        self.mask = np.zeros(self.stack.shape[-2:], dtype=bool)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.mask_changed.emit(self.mask)

    def fill_lasso(self) -> None:
        if self.mask is None or len(self.lasso_points) < 3:
            return
        self.push_undo()
        image = Image.new("L", (self.mask.shape[1], self.mask.shape[0]), 0)
        ImageDraw.Draw(image).polygon(self.lasso_points, fill=1)
        self.mask |= np.asarray(image, dtype=bool)
        self.lasso_points.clear()
        self.mask_changed.emit(self.mask)

    def save_current(self) -> None:
        record = self.current_record()
        if record is None:
            return
        save_labels(self.root, self.labels)
        save_annotation(
            self.root,
            pos=record.pos,
            roi=record.roi,
            channel=self.channel,
            time=self.time,
            z=self.z,
            label_id=self.label_id,
            mask=self.mask,
        )
        self.status_changed.emit("Saved annotation")

    def add_label(self, name: str) -> None:
        clean_name = name.strip()
        if not clean_name:
            return
        label_id = clean_name.lower().replace(" ", "_")
        self.labels.append(Label(id=label_id, name=clean_name, color="#ffcc00"))
        self.label_id = label_id
        save_labels(self.root, self.labels)
        self.load_workspace(self.root)

    def remove_label(self, label_id: str | None) -> None:
        if label_id is None:
            return
        self.labels = [label for label in self.labels if label.id != label_id]
        self.label_id = self.labels[0].id if self.labels else None
        save_labels(self.root, self.labels)
        self.load_workspace(self.root)

    def _contains(self, x: int, y: int) -> bool:
        return self.mask is not None and 0 <= y < self.mask.shape[0] and 0 <= x < self.mask.shape[1]
