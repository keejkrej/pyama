"""Aligner desktop entry point."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtWidgets

from .aligner_viewmodel import AlignerViewModel
from .grid import GridSpec
from .ui.image_view import ImageCanvas
from .ui.qt import get_app, run_window


class AlignerWindow(QtWidgets.QMainWindow):
    def __init__(self, view_model: AlignerViewModel | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Pyama Aligner")
        self.resize(1200, 820)
        self.vm = view_model or AlignerViewModel()

        self.canvas = ImageCanvas()
        self.canvas.cellClicked.connect(self.vm.toggle_cell)
        self._build_ui()
        self._connect_view_model()
        self._sync_source_enabled(False)

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
        form.addRow("Source", self._path_row(self.source_edit, self.choose_source))
        self.workspace_edit = QtWidgets.QLineEdit(str(Path.cwd()))
        form.addRow("Workspace", self._path_row(self.workspace_edit, self.choose_workspace))

        open_btn = QtWidgets.QPushButton("Open")
        open_btn.clicked.connect(self.open_source)
        form.addRow(open_btn)

        self.pos_spin = self._spin(self.update_frame_selection)
        self.t_spin = self._spin(self.update_frame_selection)
        self.c_spin = self._spin(self.update_frame_selection)
        self.z_spin = self._spin(self.update_frame_selection)
        form.addRow("Position", self.pos_spin)
        form.addRow("Time", self.t_spin)
        form.addRow("Channel", self.c_spin)
        form.addRow("Z", self.z_spin)

        self.kind_combo = QtWidgets.QComboBox()
        self.kind_combo.addItems(["rect", "hex"])
        self.kind_combo.currentTextChanged.connect(self.update_grid_spec)
        form.addRow("Grid", self.kind_combo)
        self.origin_x = self._double(0, self.update_grid_spec)
        self.origin_y = self._double(0, self.update_grid_spec)
        self.roi_w = self._spin(self.update_grid_spec, 1, 10000, 64)
        self.roi_h = self._spin(self.update_grid_spec, 1, 10000, 64)
        self.spacing_x = self._double(80, self.update_grid_spec)
        self.spacing_y = self._double(80, self.update_grid_spec)
        self.rows = self._spin(self.update_grid_spec, 1, 1000, 4)
        self.cols = self._spin(self.update_grid_spec, 1, 1000, 4)
        form.addRow("Origin X", self.origin_x)
        form.addRow("Origin Y", self.origin_y)
        form.addRow("ROI W", self.roi_w)
        form.addRow("ROI H", self.roi_h)
        form.addRow("Spacing X", self.spacing_x)
        form.addRow("Spacing Y", self.spacing_y)
        form.addRow("Rows", self.rows)
        form.addRow("Cols", self.cols)

        self.auto_btn = QtWidgets.QPushButton("Auto Exclude")
        self.auto_btn.clicked.connect(self.vm.auto_exclude)
        form.addRow(self.auto_btn)
        self.save_btn = QtWidgets.QPushButton("Save BBox + Align")
        self.save_btn.clicked.connect(self.save_alignment_files)
        form.addRow(self.save_btn)
        self.crop_btn = QtWidgets.QPushButton("Batch Crop")
        self.crop_btn.clicked.connect(self.start_crop)
        form.addRow(self.crop_btn)
        self.cancel_btn = QtWidgets.QPushButton("Cancel Crop")
        self.cancel_btn.clicked.connect(self.vm.cancel_crop)
        form.addRow(self.cancel_btn)

        self.progress = QtWidgets.QProgressBar()
        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        form.addRow(self.progress)
        form.addRow(self.status)

    def _connect_view_model(self) -> None:
        self.vm.frame_changed.connect(self.canvas.set_frame)
        self.vm.grid_changed.connect(self.canvas.set_grid)
        self.vm.frame_limits_changed.connect(self.set_frame_limits)
        self.vm.source_open_changed.connect(self._sync_source_enabled)
        self.vm.progress_changed.connect(self.on_progress)
        self.vm.status_changed.connect(self.status.setText)

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
        spin.valueChanged.connect(lambda *_: slot())
        return spin

    def _double(self, value: float, slot) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(-1_000_000, 1_000_000)
        spin.setDecimals(2)
        spin.setValue(value)
        spin.valueChanged.connect(lambda *_: slot())
        return spin

    def choose_source(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Source", "", "Images (*.nd2 *.czi *.tif *.tiff *.png *.jpg *.jpeg)"
        )
        if not path:
            path = QtWidgets.QFileDialog.getExistingDirectory(self, "Open Image Folder")
        if path:
            self.source_edit.setText(path)

    def choose_workspace(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose Workspace")
        if path:
            self.workspace_edit.setText(path)

    def open_source(self) -> None:
        self.vm.set_workspace_path(Path(self.workspace_edit.text()))
        self.vm.open_source(Path(self.source_edit.text()))

    @QtCore.Slot(int, int, int, int)
    def set_frame_limits(self, max_pos: int, max_time: int, max_chan: int, max_z: int) -> None:
        for spin, maximum in (
            (self.pos_spin, max_pos),
            (self.t_spin, max_time),
            (self.c_spin, max_chan),
            (self.z_spin, max_z),
        ):
            previous = spin.blockSignals(True)
            spin.setRange(0, maximum)
            spin.blockSignals(previous)

    @QtCore.Slot(bool)
    def _sync_source_enabled(self, enabled: bool) -> None:
        for widget in (self.pos_spin, self.t_spin, self.c_spin, self.z_spin):
            widget.setEnabled(enabled)
        for widget in (self.auto_btn, self.save_btn, self.crop_btn, self.cancel_btn):
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

    def update_frame_selection(self) -> None:
        self.vm.set_frame_indices(
            self.pos_spin.value(),
            self.t_spin.value(),
            self.c_spin.value(),
            self.z_spin.value(),
        )

    def update_grid_spec(self) -> None:
        self.vm.set_grid_spec(self.grid_spec())

    def save_alignment_files(self) -> None:
        self.vm.set_workspace_path(Path(self.workspace_edit.text()))
        self.vm.set_grid_spec(self.grid_spec())
        self.vm.save_alignment_files()

    def start_crop(self) -> None:
        self.vm.set_workspace_path(Path(self.workspace_edit.text()))
        self.vm.set_grid_spec(self.grid_spec())
        self.vm.start_crop()

    @QtCore.Slot(object)
    def on_progress(self, event) -> None:
        self.progress.setRange(0, max(event.total, 1))
        self.progress.setValue(event.done)
        self.status.setText(event.message)

    def closeEvent(self, event) -> None:
        self.vm.close()
        super().closeEvent(event)


def main() -> int:
    get_app()
    return run_window(AlignerWindow())
