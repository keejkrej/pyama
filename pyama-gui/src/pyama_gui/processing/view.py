"""Consolidated view for the processing tab."""

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pyama_gui.app_view_model import AppViewModel
from pyama_gui.constants import DEFAULT_DIR
from pyama_gui.processing.view_model import ProcessingViewModel

logger = logging.getLogger(__name__)

_PARAMETER_NAMES = ["fov_start", "fov_end", "n_workers", "background_weight"]


class SampleTable(QTableWidget):
    """Editable table of sample names and FOV assignments."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 2, parent)
        self.setHorizontalHeaderLabels(["Name", "FOVs"])
        fovs_header = self.horizontalHeaderItem(1)
        if fovs_header is not None:
            fovs_header.setToolTip("Examples: 0-5, 7, 9-11")
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)

    def add_empty_row(self) -> None:
        row = self.rowCount()
        self.insertRow(row)
        self.setItem(row, 0, QTableWidgetItem(""))
        self.setItem(row, 1, QTableWidgetItem(""))
        self.setCurrentCell(row, 0)

    def add_row(self, name: str, fovs_text: str) -> None:
        row = self.rowCount()
        self.insertRow(row)
        self.setItem(row, 0, QTableWidgetItem(name))
        self.setItem(row, 1, QTableWidgetItem(fovs_text))

    def remove_selected_row(self) -> None:
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return
        for index in sorted(indexes, key=lambda item: item.row(), reverse=True):
            self.removeRow(index.row())

    def load_samples(self, samples: list[dict[str, Any]]) -> None:
        self.setRowCount(0)
        for sample in samples:
            name = str(sample.get("name", ""))
            fovs_value = sample.get("fovs", [])
            if isinstance(fovs_value, list):
                fovs_text = ", ".join(str(int(value)) for value in fovs_value)
            elif isinstance(fovs_value, str):
                fovs_text = fovs_value
            else:
                fovs_text = ""
            self.add_row(name, fovs_text)

    def to_samples(self) -> list[dict[str, Any]]:
        samples: list[dict[str, Any]] = []
        seen_names = set()
        for row in range(self.rowCount()):
            name_item = self.item(row, 0)
            fovs_item = self.item(row, 1)
            name = (name_item.text() if name_item else "").strip()
            fovs_text = (fovs_item.text() if fovs_item else "").strip()
            if not name:
                raise ValueError(f"Row {row + 1}: Sample name is required")
            if name in seen_names:
                raise ValueError(f"Row {row + 1}: Duplicate sample name '{name}'")
            if not fovs_text:
                raise ValueError(
                    f"Row {row + 1} ('{name}'): At least one FOV is required"
                )
            seen_names.add(name)
            samples.append({"name": name, "fovs": fovs_text})
        return samples


class ProcessingView(QWidget):
    """Consolidated processing tab view."""

    def __init__(
        self,
        app_view_model: AppViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_view_model = app_view_model
        self.view_model = ProcessingViewModel(app_view_model, self)
        self._build_ui()
        self._connect_signals()
        self._refresh_metadata()
        self._refresh_workflow_state()
        self._refresh_samples()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.addWidget(self._build_input_section(), 1)
        layout.addWidget(self._build_output_section(), 1)
        layout.addWidget(self._build_merge_section(), 1)

    def _build_input_section(self) -> QGroupBox:
        group = QGroupBox("Input")
        layout = QVBoxLayout(group)

        header = QHBoxLayout()
        header.addWidget(QLabel("Microscopy File:"))
        header.addStretch()
        self._microscopy_button = QPushButton("Browse")
        header.addWidget(self._microscopy_button)
        layout.addLayout(header)

        self._microscopy_path_field = QLineEdit()
        self._microscopy_path_field.setReadOnly(True)
        layout.addWidget(self._microscopy_path_field)

        pc_layout = QVBoxLayout()
        pc_label = QLabel("Phase Contrast")
        pc_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        pc_layout.addWidget(pc_label)
        self._pc_combo = QComboBox()
        pc_layout.addWidget(self._pc_combo)
        layout.addLayout(pc_layout)

        self._pc_feature_table = QTableWidget()
        self._pc_feature_table.setColumnCount(1)
        self._pc_feature_table.setHorizontalHeaderLabels(["Feature"])
        self._pc_feature_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._pc_feature_table.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        self._pc_feature_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._pc_feature_table.verticalHeader().setVisible(False)
        layout.addWidget(self._pc_feature_table)

        fl_layout = QVBoxLayout()
        fl_layout.addWidget(QLabel("Fluorescence"))

        add_layout = QHBoxLayout()
        self._fl_channel_combo = QComboBox()
        add_layout.addWidget(self._fl_channel_combo)
        self._feature_combo = QComboBox()
        add_layout.addWidget(self._feature_combo)
        fl_layout.addLayout(add_layout)

        self._fl_feature_table = QTableWidget()
        self._fl_feature_table.setColumnCount(2)
        self._fl_feature_table.setHorizontalHeaderLabels(["Channel", "Feature"])
        self._fl_feature_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._fl_feature_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._fl_feature_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._fl_feature_table.verticalHeader().setVisible(False)
        fl_layout.addWidget(self._fl_feature_table)

        button_layout = QHBoxLayout()
        self._add_button = QPushButton("Add")
        self._add_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        button_layout.addWidget(self._add_button)
        self._remove_button = QPushButton("Remove")
        self._remove_button.setEnabled(False)
        self._remove_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        button_layout.addWidget(self._remove_button)
        fl_layout.addLayout(button_layout)

        layout.addLayout(fl_layout)
        return group

    def _build_output_section(self) -> QGroupBox:
        group = QGroupBox("Output")
        layout = QVBoxLayout(group)

        self._param_table = QTableWidget()
        self._param_table.setColumnCount(2)
        self._param_table.setHorizontalHeaderLabels(["Parameter", "Value"])
        self._param_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._param_table.verticalHeader().setVisible(False)
        self._param_table.setAlternatingRowColors(True)
        layout.addWidget(self._param_table)

        action_row = QHBoxLayout()
        self._process_button = QPushButton("Start")
        action_row.addWidget(self._process_button)
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setEnabled(False)
        action_row.addWidget(self._cancel_button)
        layout.addLayout(action_row)

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)
        self._progress_indicator = QLabel("")
        layout.addWidget(self._progress_indicator)
        return group

    def _build_merge_section(self) -> QGroupBox:
        group = QGroupBox("Merge")
        layout = QVBoxLayout(group)

        self._sample_table = SampleTable(self)
        layout.addWidget(self._sample_table)

        sample_btn_row = QHBoxLayout()
        self._add_sample_btn = QPushButton("Add")
        self._remove_sample_btn = QPushButton("Remove")
        sample_btn_row.addWidget(self._add_sample_btn)
        sample_btn_row.addWidget(self._remove_sample_btn)
        layout.addLayout(sample_btn_row)

        yaml_btn_row = QHBoxLayout()
        self._load_samples_btn = QPushButton("Load")
        self._save_samples_btn = QPushButton("Save")
        yaml_btn_row.addWidget(self._load_samples_btn)
        yaml_btn_row.addWidget(self._save_samples_btn)
        layout.addLayout(yaml_btn_row)

        self._run_merge_btn = QPushButton("Run")
        layout.addWidget(self._run_merge_btn)
        return group

    def _connect_signals(self) -> None:
        self.view_model.metadata_changed.connect(self._refresh_metadata)
        self.view_model.workflow_state_changed.connect(self._refresh_workflow_state)
        self.view_model.samples_changed.connect(self._refresh_samples)
        self.view_model.merge_state_changed.connect(self._refresh_merge_state)

        self._microscopy_button.clicked.connect(self._on_microscopy_clicked)
        self._pc_combo.currentIndexChanged.connect(self._sync_channel_selection)
        self._pc_feature_table.itemSelectionChanged.connect(
            self._sync_channel_selection
        )
        self._add_button.clicked.connect(self._on_add_channel_feature)
        self._remove_button.clicked.connect(self._on_remove_selected_feature)
        self._fl_feature_table.itemSelectionChanged.connect(
            self._on_mapping_selection_changed
        )
        self._param_table.itemChanged.connect(self._on_parameters_changed)
        self._process_button.clicked.connect(self._on_run_workflow)
        self._cancel_button.clicked.connect(self.view_model.cancel_workflow)
        self._add_sample_btn.clicked.connect(self._sample_table.add_empty_row)
        self._remove_sample_btn.clicked.connect(self._sample_table.remove_selected_row)
        self._load_samples_btn.clicked.connect(self._on_load_samples)
        self._save_samples_btn.clicked.connect(self._on_save_samples)
        self._run_merge_btn.clicked.connect(self._on_run_merge)

    @Slot()
    def _on_microscopy_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Microscopy File",
            DEFAULT_DIR,
            "Microscopy Files (*.nd2 *.czi);;ND2 Files (*.nd2);;CZI Files (*.czi);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self.view_model.select_microscopy(Path(file_path))

    @Slot()
    def _refresh_metadata(self) -> None:
        path = self.view_model.microscopy_path
        self._microscopy_path_field.setText(path.name if path else "")

        self._pc_combo.blockSignals(True)
        self._pc_combo.clear()
        for label, value in self.view_model.phase_channel_options:
            self._pc_combo.addItem(label, value)
        self._pc_combo.blockSignals(False)

        self._fl_channel_combo.blockSignals(True)
        self._fl_channel_combo.clear()
        for label, value in self.view_model.fluorescence_channel_options:
            self._fl_channel_combo.addItem(label, value)
        self._fl_channel_combo.blockSignals(False)

        self._feature_combo.blockSignals(True)
        self._feature_combo.clear()
        for feature in self.view_model.available_fl_features:
            self._feature_combo.addItem(feature)
        self._feature_combo.blockSignals(False)

        self._fl_feature_table.setRowCount(0)
        self._fl_feature_table.clearSelection()
        self._remove_button.setEnabled(False)

        self._pc_feature_table.blockSignals(True)
        self._pc_feature_table.clearContents()
        self._pc_feature_table.setRowCount(len(self.view_model.available_pc_features))
        for row, feature in enumerate(self.view_model.available_pc_features):
            item = QTableWidgetItem(feature)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._pc_feature_table.setItem(row, 0, item)
        self._pc_feature_table.blockSignals(False)

        self._populate_parameter_table(self.view_model.parameter_defaults)
        self._sync_channel_selection()

    @Slot()
    def _refresh_workflow_state(self) -> None:
        running = self.view_model.workflow_running
        self._process_button.setEnabled(not running)
        self._cancel_button.setEnabled(running)
        self._progress_indicator.setText(self.view_model.workflow_message)
        if running:
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(self.view_model.workflow_progress)
        else:
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(self.view_model.workflow_progress)

    @Slot()
    def _refresh_merge_state(self) -> None:
        self._run_merge_btn.setEnabled(not self.view_model.merge_running)

    @Slot()
    def _refresh_samples(self) -> None:
        self._sample_table.load_samples(self.view_model.samples)
        self._refresh_merge_state()

    @Slot()
    def _sync_channel_selection(self) -> None:
        phase_channel = self._pc_combo.currentData()
        pc_features = [
            self._pc_feature_table.item(index.row(), 0).text()
            for index in self._pc_feature_table.selectionModel().selectedRows()
            if self._pc_feature_table.item(index.row(), 0) is not None
        ]
        self.view_model.set_channel_selection(
            phase_channel=phase_channel,
            pc_features=pc_features,
            fl_features=self._current_fl_features(),
        )

    @Slot()
    def _on_add_channel_feature(self) -> None:
        channel_index = self._fl_channel_combo.currentIndex()
        feature_index = self._feature_combo.currentIndex()
        if channel_index < 0 or feature_index < 0:
            return

        channel_value = self._fl_channel_combo.currentData()
        channel_label = self._fl_channel_combo.currentText()
        feature_value = self._feature_combo.currentText()
        if channel_value is None or not feature_value:
            return

        current_features = self._current_fl_features()
        feature_list = current_features.setdefault(int(channel_value), [])
        if feature_value in feature_list:
            return
        feature_list.append(feature_value)

        row = self._fl_feature_table.rowCount()
        self._fl_feature_table.insertRow(row)
        channel_item = QTableWidgetItem(channel_label)
        channel_item.setData(Qt.ItemDataRole.UserRole, int(channel_value))
        channel_item.setFlags(channel_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        feature_item = QTableWidgetItem(feature_value)
        feature_item.setFlags(feature_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._fl_feature_table.setItem(row, 0, channel_item)
        self._fl_feature_table.setItem(row, 1, feature_item)
        self._sync_channel_selection()

    @Slot()
    def _on_remove_selected_feature(self) -> None:
        indexes = self._fl_feature_table.selectionModel().selectedRows()
        if not indexes:
            return
        for index in sorted(indexes, key=lambda value: value.row(), reverse=True):
            self._fl_feature_table.removeRow(index.row())
        self._sync_channel_selection()

    @Slot()
    def _on_mapping_selection_changed(self) -> None:
        self._remove_button.setEnabled(
            bool(self._fl_feature_table.selectionModel().selectedRows())
        )

    @Slot()
    def _on_parameters_changed(self) -> None:
        values = self._read_parameter_table()
        try:
            fov_start = int(values.get("fov_start", 0))
        except (TypeError, ValueError):
            fov_start = 0
        try:
            fov_end = int(values.get("fov_end", -1))
        except (TypeError, ValueError):
            fov_end = -1
        try:
            n_workers = int(values.get("n_workers", 2))
        except (TypeError, ValueError):
            n_workers = 2
        try:
            background_weight = float(values.get("background_weight", 1.0))
        except (TypeError, ValueError):
            background_weight = 1.0
        self.view_model.set_workflow_parameters(
            fov_start=fov_start,
            fov_end=fov_end,
            n_workers=n_workers,
            background_weight=background_weight,
        )

    @Slot()
    def _on_run_workflow(self) -> None:
        self._sync_channel_selection()
        self._on_parameters_changed()
        self.view_model.run_workflow()

    @Slot()
    def _on_load_samples(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open sample.yaml",
            DEFAULT_DIR,
            "YAML Files (*.yaml *.yml);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self.view_model.load_samples(Path(file_path))

    @Slot()
    def _on_save_samples(self) -> None:
        try:
            samples = self._sample_table.to_samples()
        except ValueError as exc:
            self.app_view_model.set_status_message(str(exc))
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save sample.yaml",
            DEFAULT_DIR,
            "YAML Files (*.yaml *.yml);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self.view_model.save_samples(Path(file_path), samples)

    @Slot()
    def _on_run_merge(self) -> None:
        try:
            samples = self._sample_table.to_samples()
        except ValueError as exc:
            self.app_view_model.set_status_message(str(exc))
            return
        self.view_model.set_samples(samples)
        self.view_model.run_merge()

    def _populate_parameter_table(
        self, defaults: dict[str, dict[str, Any]] | pd.DataFrame
    ) -> None:
        if isinstance(defaults, pd.DataFrame):
            defaults_dict = {}
            df_local = defaults.copy()
            if "name" in df_local.columns:
                df_local = df_local.set_index("name")
            for param_name in df_local.index.map(str):
                defaults_dict[param_name] = {
                    str(field): df_local.loc[param_name, field]
                    for field in df_local.columns
                }
        else:
            defaults_dict = defaults or {}

        param_names = [name for name in _PARAMETER_NAMES if name in defaults_dict]
        self._param_table.blockSignals(True)
        try:
            self._param_table.clearContents()
            self._param_table.setRowCount(len(param_names))
            for row, param_name in enumerate(param_names):
                name_item = QTableWidgetItem(param_name)
                name_item.setFlags(
                    name_item.flags()
                    & ~Qt.ItemFlag.ItemIsEditable
                    & ~Qt.ItemFlag.ItemIsUserCheckable
                )
                self._param_table.setItem(row, 0, name_item)
                value = defaults_dict.get(param_name, {}).get("value")
                self._param_table.setItem(
                    row, 1, QTableWidgetItem("" if value is None else str(value))
                )
        finally:
            self._param_table.blockSignals(False)

    def _current_fl_features(self) -> dict[int, list[str]]:
        features: dict[int, list[str]] = {}
        for row in range(self._fl_feature_table.rowCount()):
            channel_item = self._fl_feature_table.item(row, 0)
            feature_item = self._fl_feature_table.item(row, 1)
            if channel_item is None or feature_item is None:
                continue
            channel_value = channel_item.data(Qt.ItemDataRole.UserRole)
            if channel_value is None:
                continue
            features.setdefault(int(channel_value), []).append(feature_item.text())
        return features

    def _read_parameter_table(self) -> dict[str, object]:
        values: dict[str, object] = {}
        for row in range(self._param_table.rowCount()):
            name_item = self._param_table.item(row, 0)
            value_item = self._param_table.item(row, 1)
            if name_item is None:
                continue
            values[name_item.text()] = self._coerce(
                value_item.text() if value_item else ""
            )
        return values

    @staticmethod
    def _coerce(text: str) -> object:
        if text == "":
            return None
        try:
            if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
                return int(text)
            return float(text)
        except ValueError:
            return text
