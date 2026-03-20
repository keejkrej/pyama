"""Consolidated view for the processing tab."""

import logging
from typing import Any

import pandas as pd
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
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
from pyama_gui.apps.processing.view_model import ProcessingViewModel

logger = logging.getLogger(__name__)

_PARAMETER_NAMES = ["position_start", "position_end", "n_workers", "background_weight"]


class SampleTable(QTableWidget):
    """Editable table of sample names and position assignments."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 2, parent)
        self.setHorizontalHeaderLabels(["Name", "Positions"])
        positions_header = self.horizontalHeaderItem(1)
        if positions_header is not None:
            positions_header.setToolTip("Examples: 0:3, 5, 8:10")
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

    def add_row(self, name: str, positions_text: str) -> None:
        row = self.rowCount()
        self.insertRow(row)
        self.setItem(row, 0, QTableWidgetItem(name))
        self.setItem(row, 1, QTableWidgetItem(positions_text))

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
            positions_value = sample.get("positions", [])
            if isinstance(positions_value, list):
                positions_text = ", ".join(str(int(value)) for value in positions_value)
            elif isinstance(positions_value, str):
                positions_text = positions_value
            else:
                positions_text = ""
            self.add_row(name, positions_text)

    def to_samples(self) -> list[dict[str, Any]]:
        samples: list[dict[str, Any]] = []
        seen_names = set()
        for row in range(self.rowCount()):
            name_item = self.item(row, 0)
            positions_item = self.item(row, 1)
            name = (name_item.text() if name_item else "").strip()
            positions_text = (positions_item.text() if positions_item else "").strip()
            if not name:
                raise ValueError(f"Row {row + 1}: Sample name is required")
            if name in seen_names:
                raise ValueError(f"Row {row + 1}: Duplicate sample name '{name}'")
            if not positions_text:
                raise ValueError(
                    f"Row {row + 1} ('{name}'): At least one position is required"
                )
            seen_names.add(name)
            samples.append({"name": name, "positions": positions_text})
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
        self.view_model.state_changed.connect(self._refresh_all)
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
        self.view_model.request_select_microscopy()

    @Slot()
    def _refresh_metadata(self) -> None:
        state = self.view_model.state
        self._microscopy_path_field.setText(state.microscopy_path_label)

        self._pc_combo.blockSignals(True)
        self._pc_combo.clear()
        for label, value in state.phase_channel_options:
            self._pc_combo.addItem(label, value)
        if state.selected_phase_channel is not None:
            index = self._pc_combo.findData(state.selected_phase_channel)
            if index >= 0:
                self._pc_combo.setCurrentIndex(index)
        self._pc_combo.blockSignals(False)

        self._fl_channel_combo.blockSignals(True)
        self._fl_channel_combo.clear()
        for label, value in state.fluorescence_channel_options:
            self._fl_channel_combo.addItem(label, value)
        self._fl_channel_combo.blockSignals(False)

        self._feature_combo.blockSignals(True)
        self._feature_combo.clear()
        for feature in state.available_fl_features:
            self._feature_combo.addItem(feature)
        self._feature_combo.blockSignals(False)

        self._populate_fl_feature_table(state.fluorescence_feature_rows)
        self._fl_feature_table.clearSelection()
        self._remove_button.setEnabled(False)

        self._pc_feature_table.blockSignals(True)
        self._pc_feature_table.clearContents()
        self._pc_feature_table.setRowCount(len(state.available_pc_features))
        for row, feature in enumerate(state.available_pc_features):
            item = QTableWidgetItem(feature)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._pc_feature_table.setItem(row, 0, item)
        self._pc_feature_table.blockSignals(False)

        self._populate_parameter_table(state.parameter_values)

    @Slot()
    def _refresh_workflow_state(self) -> None:
        state = self.view_model.state
        running = state.workflow_running
        self._process_button.setEnabled(not running)
        self._cancel_button.setEnabled(running)
        self._progress_indicator.setText(state.workflow_message)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(state.workflow_progress)

    @Slot()
    def _refresh_merge_state(self) -> None:
        self._run_merge_btn.setEnabled(not self.view_model.state.merge_running)

    @Slot()
    def _refresh_samples(self) -> None:
        self._sample_table.load_samples(self.view_model.state.samples)
        self._refresh_merge_state()

    @Slot()
    def _refresh_all(self) -> None:
        self._refresh_metadata()
        self._refresh_workflow_state()
        self._refresh_samples()

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
        feature_value = self._feature_combo.currentText()
        if channel_value is None or not feature_value:
            return
        self.view_model.add_fluorescence_feature(
            channel=int(channel_value), feature_name=feature_value
        )
        self._sync_channel_selection()

    @Slot()
    def _on_remove_selected_feature(self) -> None:
        indexes = self._fl_feature_table.selectionModel().selectedRows()
        if not indexes:
            return
        rows_to_remove: list[tuple[int, str]] = []
        for index in indexes:
            channel_item = self._fl_feature_table.item(index.row(), 0)
            feature_item = self._fl_feature_table.item(index.row(), 1)
            if channel_item is None or feature_item is None:
                continue
            channel_value = channel_item.data(Qt.ItemDataRole.UserRole)
            if channel_value is None:
                continue
            rows_to_remove.append((int(channel_value), feature_item.text()))
        self.view_model.remove_fluorescence_features(rows_to_remove)
        self._sync_channel_selection()

    @Slot()
    def _on_mapping_selection_changed(self) -> None:
        self._remove_button.setEnabled(
            bool(self._fl_feature_table.selectionModel().selectedRows())
        )

    @Slot()
    def _on_parameters_changed(self) -> None:
        self.view_model.set_workflow_parameters_from_raw(self._read_parameter_table())

    @Slot()
    def _on_run_workflow(self) -> None:
        self._sync_channel_selection()
        self._on_parameters_changed()
        self.view_model.run_workflow()

    @Slot()
    def _on_load_samples(self) -> None:
        self.view_model.request_load_samples()

    @Slot()
    def _on_save_samples(self) -> None:
        try:
            rows = self._sample_rows()
        except ValueError as exc:
            self.app_view_model.set_status_message(str(exc))
            return
        self.view_model.request_save_samples(rows)

    @Slot()
    def _on_run_merge(self) -> None:
        try:
            samples = self._sample_rows()
        except ValueError as exc:
            self.app_view_model.set_status_message(str(exc))
            return
        self.view_model.set_samples_from_rows(samples)
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
                row_value = defaults_dict.get(param_name)
                if isinstance(row_value, dict):
                    value = row_value.get("value")
                else:
                    value = row_value
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

    def _populate_fl_feature_table(
        self, rows: list[tuple[str, int, str]]
    ) -> None:
        self._fl_feature_table.setRowCount(0)
        for channel_label, channel_id, feature_name in rows:
            row = self._fl_feature_table.rowCount()
            self._fl_feature_table.insertRow(row)
            channel_item = QTableWidgetItem(channel_label)
            channel_item.setData(Qt.ItemDataRole.UserRole, channel_id)
            channel_item.setFlags(channel_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            feature_item = QTableWidgetItem(feature_name)
            feature_item.setFlags(feature_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._fl_feature_table.setItem(row, 0, channel_item)
            self._fl_feature_table.setItem(row, 1, feature_item)

    def _read_parameter_table(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for row in range(self._param_table.rowCount()):
            name_item = self._param_table.item(row, 0)
            value_item = self._param_table.item(row, 1)
            if name_item is None:
                continue
            values[name_item.text()] = value_item.text() if value_item else ""
        return values

    def _sample_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for row_index in range(self._sample_table.rowCount()):
            name_item = self._sample_table.item(row_index, 0)
            positions_item = self._sample_table.item(row_index, 1)
            rows.append(
                {
                    "name": (name_item.text() if name_item is not None else "").strip(),
                    "positions": (
                        (positions_item.text() if positions_item is not None else "").strip()
                    ),
                }
            )
        return rows
