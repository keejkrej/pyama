"""Aligner desktop entry point."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtWidgets

from .adapters import ReaderSession, open_reader
from .grid import GridSpec, auto_excluded_cells, cell_at, enumerate_grid
from .ui.image_view import ImageCanvas
from .ui.qt import WorkerThread, run_window
from .workspace import Alignment, cell_bbox_union, crop_rois, save_alignment, save_bbox


class AlignerWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Pyama Aligner")
        self.resize(1200, 820)
        self.session: ReaderSession | None = None
        self.source_path: Path | None = None
        self.worker: WorkerThread | None = None
        self.excluded: set[int] = set()

        self.canvas = ImageCanvas()
        self.canvas.cellClicked.connect(self.toggle_cell)
        self._build_ui()
        self._sync_limits_enabled(False)

    def _build_ui(self) -> None:
        root = QtWidgets.QWidget()
        self.setCentralWidget(root)
        layout = QtWidgets.QHBoxLayout(root)
        layout.addWidget(self.canvas, stretch=1)

        panel = QtWidgets.QWidget()
        panel.setMaximumWidth(360)
        form = QtWidgets.QFormLayout(panel)
        layout.addWidget(panel)

        self.source_edit = QtWidgets.QLineEdit()
        source_row = self._path_row(self.source_edit, self.choose_source)
        form.addRow("Source", source_row)
        self.workspace_edit = QtWidgets.QLineEdit(str(Path.cwd()))
        form.addRow("Workspace", self._path_row(self.workspace_edit, self.choose_workspace))

        open_btn = QtWidgets.QPushButton("Open")
        open_btn.clicked.connect(self.open_source)
        form.addRow(open_btn)

        self.pos_spin = self._spin(self.update_frame)
        self.t_spin = self._spin(self.update_frame)
        self.c_spin = self._spin(self.update_frame)
        self.z_spin = self._spin(self.update_frame)
        form.addRow("Position", self.pos_spin)
        form.addRow("Time", self.t_spin)
        form.addRow("Channel", self.c_spin)
        form.addRow("Z", self.z_spin)

        self.kind_combo = QtWidgets.QComboBox()
        self.kind_combo.addItems(["rect", "hex"])
        self.kind_combo.currentTextChanged.connect(self.update_overlay)
        form.addRow("Grid", self.kind_combo)
        self.origin_x = self._double(0, self.update_overlay)
        self.origin_y = self._double(0, self.update_overlay)
        self.roi_w = self._spin(self.update_overlay, 1, 10000, 64)
        self.roi_h = self._spin(self.update_overlay, 1, 10000, 64)
        self.spacing_x = self._double(80, self.update_overlay)
        self.spacing_y = self._double(80, self.update_overlay)
        self.rows = self._spin(self.update_overlay, 1, 1000, 4)
        self.cols = self._spin(self.update_overlay, 1, 1000, 4)
        form.addRow("Origin X", self.origin_x)
        form.addRow("Origin Y", self.origin_y)
        form.addRow("ROI W", self.roi_w)
        form.addRow("ROI H", self.roi_h)
        form.addRow("Spacing X", self.spacing_x)
        form.addRow("Spacing Y", self.spacing_y)
        form.addRow("Rows", self.rows)
        form.addRow("Cols", self.cols)

        auto_btn = QtWidgets.QPushButton("Auto Exclude")
        auto_btn.clicked.connect(self.auto_exclude)
        form.addRow(auto_btn)
        save_btn = QtWidgets.QPushButton("Save BBox + Align")
        save_btn.clicked.connect(self.save_alignment_files)
        form.addRow(save_btn)
        crop_btn = QtWidgets.QPushButton("Batch Crop")
        crop_btn.clicked.connect(self.start_crop)
        form.addRow(crop_btn)
        cancel_btn = QtWidgets.QPushButton("Cancel Crop")
        cancel_btn.clicked.connect(self.cancel_crop)
        form.addRow(cancel_btn)

        self.progress = QtWidgets.QProgressBar()
        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        form.addRow(self.progress)
        form.addRow(self.status)

    def _path_row(self, edit: QtWidgets.QLineEdit, slot) -> QtWidgets.QWidget:
        row = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(edit)
        btn = QtWidgets.QPushButton("...")
        btn.clicked.connect(slot)
        layout.addWidget(btn)
        return row

    def _spin(self, slot, minimum: int = 0, maximum: int = 0, value: int = 0) -> QtWidgets.QSpinBox:
        spin = QtWidgets.QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.valueChanged.connect(slot)
        return spin

    def _double(self, value: float, slot) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(-1_000_000, 1_000_000)
        spin.setDecimals(2)
        spin.setValue(value)
        spin.valueChanged.connect(slot)
        return spin

    def choose_source(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Source", "", "Images (*.nd2 *.czi *.tif *.tiff *.png *.jpg *.jpeg)"
        )
        if not path:
            directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Open Image Folder")
            path = directory
        if path:
            self.source_edit.setText(path)

    def choose_workspace(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose Workspace")
        if path:
            self.workspace_edit.setText(path)

    def open_source(self) -> None:
        if self.session is not None:
            self.session.close()
        self.source_path = Path(self.source_edit.text()).expanduser()
        self.session = open_reader(self.source_path)
        info = self.session.info
        self.pos_spin.setRange(0, max(info.n_pos - 1, 0))
        self.t_spin.setRange(0, max(info.n_time - 1, 0))
        self.c_spin.setRange(0, max(info.n_chan - 1, 0))
        self.z_spin.setRange(0, max(info.n_z - 1, 0))
        self._sync_limits_enabled(True)
        self.update_frame()

    def _sync_limits_enabled(self, enabled: bool) -> None:
        for widget in (self.pos_spin, self.t_spin, self.c_spin, self.z_spin):
            widget.setEnabled(enabled)

    def grid_spec(self) -> GridSpec:
        return GridSpec(
            kind=self.kind_combo.currentText(),
            origin_x=self.origin_x.value(),
            origin_y=self.origin_y.value(),
            roi_width=self.roi_w.value(),
            roi_height=self.roi_h.value(),
            spacing_x=self.spacing_x.value(),
            spacing_y=self.spacing_y.value(),
            rows=self.rows.value(),
            cols=self.cols.value(),
        )

    def update_frame(self) -> None:
        if self.session is None:
            return
        frame = self.session.read_frame(
            self.pos_spin.value(), self.t_spin.value(), self.c_spin.value(), self.z_spin.value()
        )
        self.canvas.set_frame(frame)
        self.update_overlay()

    def update_overlay(self) -> None:
        spec = self.grid_spec()
        self.canvas.set_grid(
            enumerate_grid(spec),
            self.excluded,
            lambda x, y: cell_at(spec, x, y),
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
        info = self.session.info
        if info.size_x is None or info.size_y is None:
            frame = self.session.read_frame(self.pos_spin.value(), 0, 0, 0)
            image_height, image_width = frame.shape[:2]
        else:
            image_width, image_height = info.size_x, info.size_y
        self.excluded |= auto_excluded_cells(self.grid_spec(), image_width, image_height)
        self.update_overlay()

    def save_alignment_files(self) -> None:
        if self.source_path is None:
            return
        root = Path(self.workspace_edit.text())
        spec = self.grid_spec()
        bbox = cell_bbox_union(
            cell for cell in enumerate_grid(spec) if cell.index not in self.excluded
        )
        pos = self.pos_spin.value()
        save_bbox(root, pos, bbox)
        save_alignment(
            root,
            Alignment(pos=pos, source=str(self.source_path), grid=spec, excluded=self.excluded),
        )
        self.status.setText("Saved alignment")

    def start_crop(self) -> None:
        if self.session is None or self.source_path is None:
            return
        self.save_alignment_files()
        self.worker = WorkerThread(
            crop_rois,
            self.session,
            Path(self.workspace_edit.text()),
            source=str(self.source_path),
            pos=self.pos_spin.value(),
            grid=self.grid_spec(),
            excluded=set(self.excluded),
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.failed.connect(self.on_failed)
        self.worker.succeeded.connect(
            lambda records: self.status.setText(f"Wrote {len(records)} ROIs")
        )
        self.worker.start()

    def cancel_crop(self) -> None:
        if self.worker is not None:
            self.worker.cancel.cancel()

    @QtCore.Slot(object)
    def on_progress(self, event) -> None:
        self.progress.setRange(0, max(event.total, 1))
        self.progress.setValue(event.done)
        self.status.setText(event.message)

    @QtCore.Slot(str)
    def on_failed(self, message: str) -> None:
        self.status.setText(message)

    def closeEvent(self, event) -> None:
        if self.session is not None:
            self.session.close()
        super().closeEvent(event)


def main() -> int:
    return run_window(AlignerWindow())
