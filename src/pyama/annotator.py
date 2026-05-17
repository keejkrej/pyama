"""Annotator desktop entry point."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtWidgets

from .annotator_viewmodel import AnnotatorViewModel
from .ui.image_view import ImageCanvas
from .ui.qt import get_app, run_window


class AnnotatorWindow(QtWidgets.QMainWindow):
    def __init__(self, view_model: AnnotatorViewModel | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Pyama Annotator")
        self.resize(1200, 820)
        self.vm = view_model or AnnotatorViewModel()

        self.canvas = ImageCanvas()
        self.canvas.scene().sigMouseClicked.connect(self.on_canvas_click)
        self._build_ui()
        self._connect_view_model()
        self.vm.load_workspace(self.vm.root)

    def _build_ui(self) -> None:
        root = QtWidgets.QWidget()
        self.setCentralWidget(root)
        layout = QtWidgets.QHBoxLayout(root)
        layout.addWidget(self.canvas, stretch=1)

        panel = QtWidgets.QWidget()
        panel.setMaximumWidth(360)
        form = QtWidgets.QFormLayout(panel)
        layout.addWidget(panel)

        self.workspace_edit = QtWidgets.QLineEdit(str(self.vm.root))
        form.addRow("Workspace", self._path_row(self.workspace_edit, self.choose_workspace))

        reload_btn = QtWidgets.QPushButton("Scan")
        reload_btn.clicked.connect(lambda: self.vm.load_workspace(Path(self.workspace_edit.text())))
        form.addRow(reload_btn)

        self.roi_list = QtWidgets.QListWidget()
        self.roi_list.currentRowChanged.connect(self.vm.open_roi)
        form.addRow("ROIs", self.roi_list)

        self.t_spin = self._spin(self.update_frame_selection)
        self.c_spin = self._spin(self.update_frame_selection)
        self.z_spin = self._spin(self.update_frame_selection)
        form.addRow("Time", self.t_spin)
        form.addRow("Channel", self.c_spin)
        form.addRow("Z", self.z_spin)

        self.label_combo = QtWidgets.QComboBox()
        self.label_combo.currentIndexChanged.connect(self.on_label_changed)
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
                ("Undo", self.vm.undo),
                ("Redo", self.vm.redo),
                ("Discard", self.vm.discard),
                ("Fill Lasso", self.vm.fill_lasso),
                ("Save", self.vm.save_current),
            ]
        ):
            button = QtWidgets.QPushButton(text)
            button.clicked.connect(slot)
            action_layout.addWidget(button, i // 2, i % 2)
        form.addRow(actions)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        form.addRow(self.status)

    def _connect_view_model(self) -> None:
        self.vm.roi_list_changed.connect(self.set_roi_list)
        self.vm.labels_changed.connect(self.set_labels)
        self.vm.label_selected_changed.connect(self.select_label)
        self.vm.frame_limits_changed.connect(self.set_frame_limits)
        self.vm.frame_changed.connect(self.canvas.set_frame)
        self.vm.mask_changed.connect(self.canvas.set_mask)
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

    def choose_workspace(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose ROI Workspace")
        if path:
            self.workspace_edit.setText(path)
            self.vm.load_workspace(Path(path))

    @QtCore.Slot(object)
    def set_roi_list(self, rows: list[str]) -> None:
        previous = self.roi_list.blockSignals(True)
        self.roi_list.clear()
        self.roi_list.addItems(rows)
        if rows:
            self.roi_list.setCurrentRow(0)
        self.roi_list.blockSignals(previous)

    @QtCore.Slot(object)
    def set_labels(self, labels) -> None:
        previous = self.label_combo.blockSignals(True)
        self.label_combo.clear()
        for label in labels:
            self.label_combo.addItem(label.name, label.id)
        self.label_combo.blockSignals(previous)

    @QtCore.Slot(object)
    def select_label(self, label_id: str | None) -> None:
        if label_id is None:
            return
        idx = self.label_combo.findData(label_id)
        if idx >= 0:
            previous = self.label_combo.blockSignals(True)
            self.label_combo.setCurrentIndex(idx)
            self.label_combo.blockSignals(previous)

    @QtCore.Slot(int, int, int)
    def set_frame_limits(self, max_time: int, max_chan: int, max_z: int) -> None:
        for spin, maximum in (
            (self.t_spin, max_time),
            (self.c_spin, max_chan),
            (self.z_spin, max_z),
        ):
            previous = spin.blockSignals(True)
            spin.setRange(0, maximum)
            spin.blockSignals(previous)

    def update_frame_selection(self) -> None:
        self.vm.set_frame_indices(self.t_spin.value(), self.c_spin.value(), self.z_spin.value())

    def on_label_changed(self) -> None:
        self.vm.set_label_id(self.label_combo.currentData())

    def on_canvas_click(self, event) -> None:
        point = self.canvas.plotItem.vb.mapSceneToView(event.scenePos())
        x, y = int(round(point.x())), int(round(point.y()))
        if self.mode.currentText() == "lasso":
            self.vm.add_lasso_point(x, y)
        else:
            self.vm.paint_at(x, y, self.mode.currentText(), self.brush.value())

    def add_label(self) -> None:
        name, ok = QtWidgets.QInputDialog.getText(self, "Add Label", "Name")
        if ok:
            self.vm.add_label(name)

    def remove_label(self) -> None:
        self.vm.remove_label(self.label_combo.currentData())


def main() -> int:
    get_app()
    return run_window(AnnotatorWindow())
