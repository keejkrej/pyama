"""Annotator desktop entry point."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import ImageDraw
from PySide6 import QtCore, QtWidgets

from .annotations import Label, load_annotation, load_labels, save_annotation, save_labels
from .ui.image_view import ImageCanvas
from .ui.qt import run_window
from .workspace import RoiRecord, scan_roi_workspace


def read_roi_stack(path: Path) -> np.ndarray:
    import tifffile

    stack = np.asarray(tifffile.imread(str(path)))
    if stack.ndim == 2:
        return stack[None, None, None, :, :]
    if stack.ndim == 3:
        return stack[:, None, None, :, :]
    if stack.ndim == 4:
        return stack[:, :, None, :, :]
    if stack.ndim == 5:
        return stack
    raise ValueError(f"Unsupported ROI TIFF shape: {stack.shape}")


class AnnotatorWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Pyama Annotator")
        self.resize(1200, 820)
        self.root = Path.cwd()
        self.records: list[RoiRecord] = []
        self.stack: np.ndarray | None = None
        self.mask: np.ndarray | None = None
        self.undo_stack: list[np.ndarray] = []
        self.redo_stack: list[np.ndarray] = []
        self.lasso_points: list[tuple[int, int]] = []

        self.canvas = ImageCanvas()
        self.canvas.scene().sigMouseClicked.connect(self.on_canvas_click)
        self._build_ui()
        self.load_workspace(self.root)

    def _build_ui(self) -> None:
        root = QtWidgets.QWidget()
        self.setCentralWidget(root)
        layout = QtWidgets.QHBoxLayout(root)
        layout.addWidget(self.canvas, stretch=1)

        panel = QtWidgets.QWidget()
        panel.setMaximumWidth(360)
        form = QtWidgets.QFormLayout(panel)
        layout.addWidget(panel)

        self.workspace_edit = QtWidgets.QLineEdit(str(self.root))
        browse = QtWidgets.QPushButton("...")
        browse.clicked.connect(self.choose_workspace)
        row = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.workspace_edit)
        row_layout.addWidget(browse)
        form.addRow("Workspace", row)

        reload_btn = QtWidgets.QPushButton("Scan")
        reload_btn.clicked.connect(lambda: self.load_workspace(Path(self.workspace_edit.text())))
        form.addRow(reload_btn)

        self.roi_list = QtWidgets.QListWidget()
        self.roi_list.currentRowChanged.connect(self.open_roi)
        form.addRow("ROIs", self.roi_list)

        self.t_spin = self._spin(self.update_frame)
        self.c_spin = self._spin(self.update_frame)
        self.z_spin = self._spin(self.update_frame)
        form.addRow("Time", self.t_spin)
        form.addRow("Channel", self.c_spin)
        form.addRow("Z", self.z_spin)

        self.label_combo = QtWidgets.QComboBox()
        form.addRow("Label", self.label_combo)
        label_row = QtWidgets.QWidget()
        label_layout = QtWidgets.QHBoxLayout(label_row)
        label_layout.setContentsMargins(0, 0, 0, 0)
        add_label = QtWidgets.QPushButton("Add")
        add_label.clicked.connect(self.add_label)
        remove_label = QtWidgets.QPushButton("Remove")
        remove_label.clicked.connect(self.remove_label)
        label_layout.addWidget(add_label)
        label_layout.addWidget(remove_label)
        form.addRow(label_row)

        self.mode = QtWidgets.QComboBox()
        self.mode.addItems(["brush", "erase", "lasso"])
        form.addRow("Tool", self.mode)
        self.brush = self._spin(lambda: None, 1, 200, 12)
        form.addRow("Brush", self.brush)

        actions = QtWidgets.QWidget()
        action_layout = QtWidgets.QGridLayout(actions)
        for i, (text, slot) in enumerate(
            [
                ("Undo", self.undo),
                ("Redo", self.redo),
                ("Discard", self.discard),
                ("Fill Lasso", self.fill_lasso),
                ("Save", self.save_current),
            ]
        ):
            button = QtWidgets.QPushButton(text)
            button.clicked.connect(slot)
            action_layout.addWidget(button, i // 2, i % 2)
        form.addRow(actions)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        form.addRow(self.status)

    def _spin(self, slot, minimum: int = 0, maximum: int = 0, value: int = 0) -> QtWidgets.QSpinBox:
        spin = QtWidgets.QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.valueChanged.connect(slot)
        return spin

    def choose_workspace(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose ROI Workspace")
        if path:
            self.workspace_edit.setText(path)
            self.load_workspace(Path(path))

    def load_workspace(self, root: Path) -> None:
        self.root = root
        self.labels = load_labels(root)
        self.label_combo.clear()
        for label in self.labels:
            self.label_combo.addItem(label.name, label.id)

        workspace = scan_roi_workspace(root)
        self.records = workspace.records
        self.roi_list.clear()
        for record in self.records:
            self.roi_list.addItem(f"Pos{record.pos} Roi{record.roi}")
        if self.records:
            self.roi_list.setCurrentRow(0)
        self.status.setText(f"Found {len(self.records)} ROIs")

    @QtCore.Slot(int)
    def open_roi(self, row: int) -> None:
        if row < 0 or row >= len(self.records):
            return
        record = self.records[row]
        self.stack = read_roi_stack(Path(record.path))
        self.t_spin.setRange(0, self.stack.shape[0] - 1)
        self.c_spin.setRange(0, self.stack.shape[1] - 1)
        self.z_spin.setRange(0, self.stack.shape[2] - 1)
        self.mask = np.zeros(self.stack.shape[-2:], dtype=bool)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.update_frame()

    def current_record(self) -> RoiRecord | None:
        row = self.roi_list.currentRow()
        if row < 0 or row >= len(self.records):
            return None
        return self.records[row]

    def update_frame(self) -> None:
        if self.stack is None:
            return
        frame = self.stack[self.t_spin.value(), self.c_spin.value(), self.z_spin.value()]
        self.canvas.set_frame(frame)
        record = self.current_record()
        if record is not None:
            annotation, mask = load_annotation(
                self.root,
                pos=record.pos,
                roi=record.roi,
                channel=self.c_spin.value(),
                time=self.t_spin.value(),
                z=self.z_spin.value(),
            )
            if annotation and annotation.label_id:
                idx = self.label_combo.findData(annotation.label_id)
                if idx >= 0:
                    self.label_combo.setCurrentIndex(idx)
            self.mask = mask if mask is not None else np.zeros(frame.shape, dtype=bool)
        self.canvas.set_mask(self.mask)

    def on_canvas_click(self, event) -> None:
        if self.stack is None or self.mask is None:
            return
        point = self.canvas.plotItem.vb.mapSceneToView(event.scenePos())
        x, y = int(round(point.x())), int(round(point.y()))
        if not (0 <= y < self.mask.shape[0] and 0 <= x < self.mask.shape[1]):
            return
        mode = self.mode.currentText()
        if mode == "lasso":
            self.lasso_points.append((x, y))
            self.status.setText(f"Lasso points: {len(self.lasso_points)}")
            return
        self.push_undo()
        radius = self.brush.value()
        y1, y2 = max(0, y - radius), min(self.mask.shape[0], y + radius + 1)
        x1, x2 = max(0, x - radius), min(self.mask.shape[1], x + radius + 1)
        yy, xx = np.ogrid[y1:y2, x1:x2]
        brush = (yy - y) ** 2 + (xx - x) ** 2 <= radius**2
        self.mask[y1:y2, x1:x2][brush] = mode == "brush"
        self.canvas.set_mask(self.mask)

    def push_undo(self) -> None:
        if self.mask is not None:
            self.undo_stack.append(self.mask.copy())
            self.redo_stack.clear()

    def undo(self) -> None:
        if self.mask is None or not self.undo_stack:
            return
        self.redo_stack.append(self.mask.copy())
        self.mask = self.undo_stack.pop()
        self.canvas.set_mask(self.mask)

    def redo(self) -> None:
        if self.mask is None or not self.redo_stack:
            return
        self.undo_stack.append(self.mask.copy())
        self.mask = self.redo_stack.pop()
        self.canvas.set_mask(self.mask)

    def discard(self) -> None:
        if self.stack is None:
            return
        self.mask = np.zeros(self.stack.shape[-2:], dtype=bool)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.canvas.set_mask(self.mask)

    def fill_lasso(self) -> None:
        if self.mask is None or len(self.lasso_points) < 3:
            return
        self.push_undo()
        from PIL import Image

        image = Image.new("L", (self.mask.shape[1], self.mask.shape[0]), 0)
        ImageDraw.Draw(image).polygon(self.lasso_points, fill=1)
        self.mask |= np.asarray(image, dtype=bool)
        self.lasso_points.clear()
        self.canvas.set_mask(self.mask)

    def save_current(self) -> None:
        record = self.current_record()
        if record is None:
            return
        save_labels(self.root, self.labels)
        save_annotation(
            self.root,
            pos=record.pos,
            roi=record.roi,
            channel=self.c_spin.value(),
            time=self.t_spin.value(),
            z=self.z_spin.value(),
            label_id=self.label_combo.currentData(),
            mask=self.mask,
        )
        self.status.setText("Saved annotation")

    def add_label(self) -> None:
        name, ok = QtWidgets.QInputDialog.getText(self, "Add Label", "Name")
        if not ok or not name.strip():
            return
        label_id = name.strip().lower().replace(" ", "_")
        self.labels.append(Label(id=label_id, name=name.strip(), color="#ffcc00"))
        save_labels(self.root, self.labels)
        self.load_workspace(self.root)

    def remove_label(self) -> None:
        idx = self.label_combo.currentIndex()
        if idx < 0:
            return
        label_id = self.label_combo.itemData(idx)
        self.labels = [label for label in self.labels if label.id != label_id]
        save_labels(self.root, self.labels)
        self.load_workspace(self.root)


def main() -> int:
    return run_window(AnnotatorWindow())
