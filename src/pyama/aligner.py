"""Aligner desktop entry point."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtWidgets

from .aligner_viewmodel import AlignerViewModel
from .contrast import percentile_limits
from .grid import GridCell, GridSpec
from .ui.image_view import ImageCanvas
from .ui.qt import get_app, run_window


class AlignerWindow(QtWidgets.QMainWindow):
    def __init__(self, view_model: AlignerViewModel | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Pyama Aligner")
        self.resize(1320, 860)
        self.vm = view_model or AlignerViewModel()
        self._last_cells: list[GridCell] = []
        self._last_excluded: set[int] = set()
        self.active_tool = "pan"

        self.canvas = ImageCanvas()
        self.canvas.cellClicked.connect(self.vm.toggle_cell)
        self.canvas.overlayDragged.connect(self.apply_tool_drag)
        self._build_ui()
        self._connect_view_model()
        self._sync_source_enabled(False)

    def _build_ui(self) -> None:
        root = QtWidgets.QWidget()
        self.setCentralWidget(root)
        root_layout = QtWidgets.QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)

        body = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        root_layout.addWidget(body)

        body.addWidget(self._left_sidebar())
        body.addWidget(self._main_column())
        body.addWidget(self._right_sidebar())
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        body.setStretchFactor(2, 0)
        body.setSizes([300, 760, 320])

    def _left_sidebar(self) -> QtWidgets.QWidget:
        sidebar = self._scroll_sidebar(300)
        layout = sidebar.widget().layout()
        assert isinstance(layout, QtWidgets.QVBoxLayout)

        source_group = QtWidgets.QGroupBox("Source")
        source_form = QtWidgets.QFormLayout(source_group)
        self.source_edit = QtWidgets.QLineEdit()
        self.workspace_edit = QtWidgets.QLineEdit(str(Path.cwd()))
        source_form.addRow("Source", self._path_row(self.source_edit, self.choose_source))
        source_form.addRow("Workspace", self._path_row(self.workspace_edit, self.choose_workspace))
        open_btn = QtWidgets.QPushButton("Open")
        open_btn.clicked.connect(self.open_source)
        source_form.addRow(open_btn)
        layout.addWidget(source_group)

        nav_group = QtWidgets.QGroupBox("Navigation")
        nav_form = QtWidgets.QFormLayout(nav_group)
        self.pos_spin = self._spin(self.update_frame_selection)
        self.t_spin = self._spin(self.update_frame_selection)
        self.c_spin = self._spin(self.update_frame_selection)
        self.z_spin = self._spin(self.update_frame_selection)
        nav_form.addRow("Position", self.pos_spin)
        nav_form.addRow("Time", self.t_spin)
        nav_form.addRow("Channel", self.c_spin)
        nav_form.addRow("Z", self.z_spin)
        layout.addWidget(nav_group)
        layout.addStretch(1)
        return sidebar

    def _main_column(self) -> QtWidgets.QWidget:
        column = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.canvas, stretch=1)
        layout.addWidget(self._dock())
        return column

    def _right_sidebar(self) -> QtWidgets.QWidget:
        sidebar = self._scroll_sidebar(340)
        layout = sidebar.widget().layout()
        assert isinstance(layout, QtWidgets.QVBoxLayout)
        layout.addWidget(self._contrast_section())
        layout.addWidget(self._grid_section())
        layout.addWidget(self._selection_section())
        layout.addStretch(1)
        return sidebar

    def _dock(self) -> QtWidgets.QWidget:
        dock = QtWidgets.QWidget()
        dock.setFixedHeight(170)
        layout = QtWidgets.QHBoxLayout(dock)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self._tools_section())
        layout.addWidget(self._save_section())
        return dock

    def _tools_section(self) -> QtWidgets.QWidget:
        group = QtWidgets.QGroupBox("Tools")
        layout = QtWidgets.QGridLayout(group)
        self.tool_group = QtWidgets.QButtonGroup(self)
        self.tool_group.setExclusive(True)
        tools = (
            ("pan", "Pan"),
            ("rotate", "Rotate"),
            ("zoom_vector", "Zoom Vector"),
            ("zoom_pattern", "Zoom Pattern"),
        )
        for index, (tool, label) in enumerate(tools):
            button = QtWidgets.QPushButton(label)
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, name=tool: self.set_active_tool(name))
            if index == 0:
                button.setChecked(True)
            self.tool_group.addButton(button)
            layout.addWidget(button, index // 2, index % 2)
        return group

    def _save_section(self) -> QtWidgets.QWidget:
        group = QtWidgets.QGroupBox("Save")
        layout = QtWidgets.QGridLayout(group)

        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.clicked.connect(self.save_alignment_files)
        self.crop_btn = QtWidgets.QPushButton("Crop")
        self.crop_btn.clicked.connect(self.start_crop)

        layout.addWidget(self.save_btn, 0, 0)
        layout.addWidget(self.crop_btn, 0, 1)
        return group

    def _contrast_section(self) -> QtWidgets.QWidget:
        group = QtWidgets.QGroupBox("Contrast")
        form = QtWidgets.QFormLayout(group)
        self.contrast_min = self._double(0, self.update_contrast, decimals=2)
        self.contrast_max = self._double(1, self.update_contrast, decimals=2)
        self.auto_contrast_btn = QtWidgets.QPushButton("Auto Range")
        self.auto_contrast_btn.clicked.connect(self.auto_contrast)
        form.addRow(self.auto_contrast_btn)
        form.addRow("Min", self.contrast_min)
        form.addRow("Max", self.contrast_max)
        return group

    def _grid_section(self) -> QtWidgets.QWidget:
        group = QtWidgets.QGroupBox("Grid")
        form = QtWidgets.QFormLayout(group)

        self.overlay_check = QtWidgets.QCheckBox("Show overlay")
        self.overlay_check.setChecked(True)
        self.overlay_check.toggled.connect(self.canvas.set_grid_visible)
        self.opacity_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(30)
        self.opacity_slider.valueChanged.connect(
            lambda value: self.canvas.set_grid_opacity(value / 100)
        )

        self.kind_combo = QtWidgets.QComboBox()
        self.kind_combo.addItems(["rect", "hex"])
        self.kind_combo.currentTextChanged.connect(self.update_grid_spec)
        self.rotation = self._double(0, self.update_grid_spec)
        self.vector_a = self._double(80, self.update_grid_spec, minimum=1)
        self.vector_b = self._double(80, self.update_grid_spec, minimum=1)
        self.pattern_w = self._spin(self.update_grid_spec, 1, 10000, 64)
        self.pattern_h = self._spin(self.update_grid_spec, 1, 10000, 64)
        self.offset_x = self._double(0, self.update_grid_spec)
        self.offset_y = self._double(0, self.update_grid_spec)

        form.addRow("Overlay", self.overlay_check)
        form.addRow("Opacity", self.opacity_slider)
        form.addRow("Grid shape", self.kind_combo)
        form.addRow("Rotation", self.rotation)
        form.addRow("Vector A", self.vector_a)
        form.addRow("Vector B", self.vector_b)
        form.addRow("Pattern Width", self.pattern_w)
        form.addRow("Pattern Height", self.pattern_h)
        form.addRow("Offset X", self.offset_x)
        form.addRow("Offset Y", self.offset_y)
        return group

    def _selection_section(self) -> QtWidgets.QWidget:
        group = QtWidgets.QGroupBox("Selection")
        layout = QtWidgets.QGridLayout(group)
        self.included_label = QtWidgets.QLabel("0")
        self.excluded_label = QtWidgets.QLabel("0")
        self.reset_selection_btn = QtWidgets.QPushButton("Reset")
        self.reset_selection_btn.clicked.connect(self.vm.reset_exclusions)
        self.exclude_all_btn = QtWidgets.QPushButton("Exclude All")
        self.exclude_all_btn.clicked.connect(self.vm.exclude_all)
        self.auto_btn = QtWidgets.QPushButton("Exclude Edge")
        self.auto_btn.clicked.connect(self.vm.auto_exclude)

        layout.addWidget(QtWidgets.QLabel("Included Cells"), 0, 0)
        layout.addWidget(QtWidgets.QLabel("Excluded Cells"), 0, 1)
        layout.addWidget(self.included_label, 1, 0)
        layout.addWidget(self.excluded_label, 1, 1)
        layout.addWidget(self.reset_selection_btn, 2, 0)
        layout.addWidget(self.exclude_all_btn, 2, 1)
        layout.addWidget(self.auto_btn, 3, 0, 1, 2)
        return group

    def _scroll_sidebar(self, width: int) -> QtWidgets.QScrollArea:
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        scroll.setMinimumWidth(width)
        scroll.setMaximumWidth(width + 80)
        return scroll

    def _connect_view_model(self) -> None:
        self.vm.frame_changed.connect(self.on_frame_changed)
        self.vm.grid_changed.connect(self.on_grid_changed)
        self.vm.frame_limits_changed.connect(self.set_frame_limits)
        self.vm.source_open_changed.connect(self._sync_source_enabled)

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
        spin.setKeyboardTracking(False)
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.valueChanged.connect(lambda *_: slot())
        return spin

    def _double(
        self,
        value: float,
        slot,
        *,
        minimum: float = -1_000_000,
        maximum: float = 1_000_000,
        decimals: int = 2,
    ) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setKeyboardTracking(False)
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
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
        widgets = (
            self.pos_spin,
            self.t_spin,
            self.c_spin,
            self.z_spin,
            self.auto_contrast_btn,
            self.contrast_min,
            self.contrast_max,
            self.reset_selection_btn,
            self.exclude_all_btn,
            self.auto_btn,
            self.save_btn,
            self.crop_btn,
        )
        for widget in widgets:
            widget.setEnabled(enabled)

    def grid_spec(self) -> GridSpec:
        return GridSpec(
            kind=self.kind_combo.currentText(),
            offset_x=self.offset_x.value(),
            offset_y=self.offset_y.value(),
            vector_a=self.vector_a.value(),
            vector_b=self.vector_b.value(),
            pattern_width=self.pattern_w.value(),
            pattern_height=self.pattern_h.value(),
            rotation_degrees=self.rotation.value(),
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

    @QtCore.Slot(float, float)
    def apply_tool_drag(self, dx: float, dy: float) -> None:
        if self.active_tool == "rotate":
            self._set_spin_value(self.rotation, self.rotation.value() + dx)
        elif self.active_tool == "zoom_vector":
            self._set_spin_value(self.vector_a, self.vector_a.value() + dx)
            self._set_spin_value(self.vector_b, self.vector_b.value() + dy)
        elif self.active_tool == "zoom_pattern":
            self._set_spin_value(self.pattern_w, self.pattern_w.value() + round(dx))
            self._set_spin_value(self.pattern_h, self.pattern_h.value() + round(dy))
        else:
            self.move_overlay(dx, dy)
            return
        self.update_grid_spec()

    def set_active_tool(self, tool: str) -> None:
        self.active_tool = tool

    def move_overlay(self, dx: float, dy: float) -> None:
        self._set_grid_offset_values(self.offset_x.value() + dx, self.offset_y.value() + dy)
        self.update_grid_spec()

    def update_contrast(self) -> None:
        self.canvas.set_contrast_limits(self.contrast_min.value(), self.contrast_max.value())

    def auto_contrast(self) -> None:
        limits = self.canvas.auto_contrast()
        if limits is not None:
            self._set_contrast_values(limits.low, limits.high)

    def save_alignment_files(self) -> None:
        self.vm.set_workspace_path(Path(self.workspace_edit.text()))
        self.vm.set_grid_spec(self.grid_spec())
        self.vm.save_alignment_files()

    def start_crop(self) -> None:
        self.vm.set_workspace_path(Path(self.workspace_edit.text()))
        self.vm.set_grid_spec(self.grid_spec())
        self.vm.start_crop()

    @QtCore.Slot(object)
    def on_frame_changed(self, frame: np.ndarray) -> None:
        self.canvas.set_frame(frame)
        finite = np.asarray(frame, dtype=np.float32)
        finite = finite[np.isfinite(finite)]
        if finite.size == 0:
            domain_low, domain_high = 0.0, 1.0
        else:
            domain_low = float(np.min(finite))
            domain_high = float(np.max(finite))
            if domain_high <= domain_low:
                domain_high = domain_low + 1.0

        for spin in (self.contrast_min, self.contrast_max):
            previous = spin.blockSignals(True)
            spin.setRange(domain_low, domain_high)
            spin.blockSignals(previous)

        limits = percentile_limits(frame)
        self._set_contrast_values(limits.low, limits.high)
        self.canvas.set_contrast_limits(limits.low, limits.high)

    @QtCore.Slot(object, object, object)
    def on_grid_changed(self, cells, excluded, hit_test) -> None:
        self._last_cells = list(cells)
        self._last_excluded = set(excluded)
        self.canvas.set_grid(self._last_cells, self._last_excluded, hit_test)
        valid_excluded = {cell.index for cell in self._last_cells} & self._last_excluded
        self.excluded_label.setText(str(len(valid_excluded)))
        self.included_label.setText(str(max(0, len(self._last_cells) - len(valid_excluded))))

    def _set_contrast_values(self, low: float, high: float) -> None:
        for spin, value in ((self.contrast_min, low), (self.contrast_max, high)):
            previous = spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(previous)

    def _set_grid_offset_values(self, offset_x: float, offset_y: float) -> None:
        for spin, value in ((self.offset_x, offset_x), (self.offset_y, offset_y)):
            self._set_spin_value(spin, value)

    def _set_spin_value(
        self, spin: QtWidgets.QDoubleSpinBox | QtWidgets.QSpinBox, value: float
    ) -> None:
        previous = spin.blockSignals(True)
        spin.setValue(value)
        spin.blockSignals(previous)

    def closeEvent(self, event) -> None:
        self.vm.close()
        super().closeEvent(event)


def main() -> int:
    get_app()
    return run_window(AlignerWindow())
