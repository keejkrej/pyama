"""Output panel for the processing workflow."""

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyama_gui.components.parameter_table import ParameterTable
from pyama_gui.constants import DEFAULT_DIR

logger = logging.getLogger(__name__)


class OutputPanel(QWidget):
    """Collect output and execution settings for processing."""

    output_directory_selected = Signal(object)
    process_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._output_dir: Path | None = None
        self._fov_start = 0
        self._fov_end = -1
        self._n_workers = 2
        self._background_weight = 1.0
        self._build_ui()
        self._connect_signals()
        self.reset()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("Output")
        group_layout = QVBoxLayout(group)

        header = QHBoxLayout()
        header.addWidget(QLabel("Save Directory:"))
        header.addStretch()
        self._output_button = QPushButton("Browse")
        header.addWidget(self._output_button)
        group_layout.addLayout(header)

        self._output_dir_field = QLineEdit()
        self._output_dir_field.setReadOnly(True)
        group_layout.addWidget(self._output_dir_field)

        self._param_panel = ParameterTable()
        group_layout.addWidget(self._param_panel)

        self._process_button = QPushButton("Start Complete Workflow")
        group_layout.addWidget(self._process_button)

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setEnabled(False)
        group_layout.addWidget(self._cancel_button)

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        group_layout.addWidget(self._progress_bar)

        layout.addWidget(group)

    def _connect_signals(self) -> None:
        self._output_button.clicked.connect(self._on_output_clicked)
        self._process_button.clicked.connect(self.process_requested)
        self._cancel_button.clicked.connect(self.cancel_requested)
        self._param_panel.parameters_changed.connect(self._on_parameters_changed)

    @property
    def output_dir(self) -> Path | None:
        return self._output_dir

    @property
    def fov_start(self) -> int:
        return self._fov_start

    @property
    def fov_end(self) -> int:
        return self._fov_end

    @property
    def n_workers(self) -> int:
        return self._n_workers

    @property
    def background_weight(self) -> float:
        return self._background_weight

    def reset(self) -> None:
        self._output_dir = None
        self.display_output_directory(None)
        self.set_parameter_defaults(
            {
                "fov_start": {"value": 0},
                "fov_end": {"value": -1},
                "n_workers": {"value": 2},
                "background_weight": {"value": 1.0},
            }
        )
        self.set_processing_active(False)
        self.set_process_enabled(True)

    @Slot()
    def _on_output_clicked(self) -> None:
        logger.debug(
            "UI Click: Output directory browse button (start_dir=%s)", DEFAULT_DIR
        )
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            DEFAULT_DIR,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not directory:
            return

        logger.info(
            "Output directory chosen: %s (exists=%s)",
            directory,
            Path(directory).exists(),
        )
        self._output_dir = Path(directory)
        self.display_output_directory(self._output_dir)
        self.output_directory_selected.emit(self._output_dir)

    @Slot()
    def _on_parameters_changed(self) -> None:
        values_dict = self._param_panel.get_values()

        values: dict[str, object] = {}
        for param_name, fields in values_dict.items():
            if "value" in fields:
                values[param_name] = fields["value"]
            elif fields:
                values[param_name] = next(iter(fields.values()))

        try:
            self._fov_start = int(values.get("fov_start", 0))
        except (ValueError, TypeError):
            self._fov_start = 0

        try:
            self._fov_end = int(values.get("fov_end", -1))
        except (ValueError, TypeError):
            self._fov_end = -1

        try:
            self._n_workers = int(values.get("n_workers", 2))
        except (ValueError, TypeError):
            self._n_workers = 2

        try:
            self._background_weight = float(values.get("background_weight", 1.0))
        except (ValueError, TypeError):
            self._background_weight = 1.0

        logger.debug(
            "Workflow parameters updated from UI - fov_start=%d, fov_end=%d, n_workers=%d, background_weight=%.2f",
            self._fov_start,
            self._fov_end,
            self._n_workers,
            self._background_weight,
        )

    def display_output_directory(self, path: Path | None) -> None:
        self._output_dir_field.setText(str(path or ""))

    def set_processing_active(self, active: bool) -> None:
        if active:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setVisible(True)
        else:
            self._progress_bar.setVisible(False)
            self._progress_bar.setRange(0, 1)

    def set_progress_value(self, percent: int) -> None:
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(max(0, min(100, percent)))

    def set_process_enabled(self, enabled: bool) -> None:
        self._process_button.setEnabled(enabled)
        self._cancel_button.setEnabled(not enabled)

    def set_parameter_defaults(
        self, defaults: dict[str, dict[str, Any]] | pd.DataFrame
    ) -> None:
        if isinstance(defaults, dict):
            self._param_panel.set_parameters(defaults)
        else:
            self._param_panel.set_parameters_df(defaults)
        self._on_parameters_changed()
