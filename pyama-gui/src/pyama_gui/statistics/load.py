"""Loader and configuration panel for statistics workflows."""

import logging
from pathlib import Path

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)

from pyama.tasks import discover_sample_pairs
from pyama.types import SamplePair
from pyama_gui.constants import DEFAULT_DIR
from pyama_gui.types.statistics import StatisticsRequest

logger = logging.getLogger(__name__)


class StatisticsLoadPanel(QWidget):
    """Panel for folder loading and statistics configuration."""

    results_invalidated = Signal()
    run_requested = Signal(object)
    status_message = Signal(str)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._folder_path: Path | None = None
        self._sample_pairs: list[SamplePair] = []
        self._normalization_available = False
        self._build_ui()
        self._connect_signals()
        self._on_mode_changed(self.mode)
        self._update_normalization_availability()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("Statistics Controls")
        group_layout = QVBoxLayout(group)

        self._load_button = QPushButton("Load Folder")
        group_layout.addWidget(self._load_button)

        self._folder_label = QLabel("No folder loaded.")
        self._folder_label.setWordWrap(True)
        group_layout.addWidget(self._folder_label)

        self._samples_label = QLabel("Discovered samples: 0")
        group_layout.addWidget(self._samples_label)

        self._sample_list = QListWidget()
        self._sample_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        group_layout.addWidget(self._sample_list)

        form = QFormLayout()

        self._mode_combo = QComboBox()
        self._mode_combo.addItem("AUC", "auc")
        self._mode_combo.addItem("Onset", "onset_shifted_relu")
        form.addRow("Mode:", self._mode_combo)

        self._normalize_checkbox = QCheckBox("Normalize by area")
        self._normalize_checkbox.setChecked(False)
        form.addRow("", self._normalize_checkbox)

        self._window_label = QLabel("Onset window (h):")
        self._window_spin = QDoubleSpinBox()
        self._window_spin.setRange(0.5, 24.0)
        self._window_spin.setSingleStep(0.5)
        self._window_spin.setValue(4.0)
        form.addRow(self._window_label, self._window_spin)

        self._filter_label = QLabel("Area filter size:")
        self._filter_spin = QSpinBox()
        self._filter_spin.setRange(1, 101)
        self._filter_spin.setValue(10)
        form.addRow(self._filter_label, self._filter_spin)

        group_layout.addLayout(form)

        self._run_button = QPushButton("Run Statistics")
        group_layout.addWidget(self._run_button)

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.hide()
        group_layout.addWidget(self._progress_bar)

        group_layout.addStretch()
        layout.addWidget(group)

    def _connect_signals(self) -> None:
        self._load_button.clicked.connect(self._on_load_folder_clicked)
        self._run_button.clicked.connect(self._on_run_clicked)
        self._mode_combo.currentIndexChanged.connect(
            lambda _: self._on_mode_changed(self.mode)
        )
        self._normalize_checkbox.toggled.connect(self._on_normalize_toggled)

    @property
    def mode(self) -> str:
        return str(self._mode_combo.currentData())

    @property
    def folder_path(self) -> Path | None:
        return self._folder_path

    @property
    def sample_pairs(self) -> list[SamplePair]:
        return list(self._sample_pairs)

    def set_processing_active(self, is_active: bool) -> None:
        self._run_button.setEnabled(not is_active)
        self._load_button.setEnabled(not is_active)
        self._mode_combo.setEnabled(not is_active)
        self._normalize_checkbox.setEnabled(
            not is_active and self._normalization_available
        )
        self._window_spin.setEnabled(not is_active)
        self._filter_spin.setEnabled(
            not is_active and self._normalize_checkbox.isChecked()
        )
        if is_active:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.show()
        else:
            self._progress_bar.hide()

    @Slot()
    def _on_load_folder_clicked(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select merge_output Folder",
            str(DEFAULT_DIR),
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if directory:
            self._load_folder(Path(directory))

    def _load_folder(self, folder_path: Path) -> None:
        try:
            sample_pairs = discover_sample_pairs(folder_path)
        except Exception as exc:
            logger.warning("Failed to load statistics folder %s: %s", folder_path, exc)
            self._sample_pairs = []
            self._folder_path = None
            self._normalization_available = False
            self._sample_list.clear()
            self._samples_label.setText("Discovered samples: 0")
            self._folder_label.setText(f"Failed to load folder: {exc}")
            self._update_normalization_availability()
            self.results_invalidated.emit()
            self.status_message.emit(f"Failed to load statistics folder: {exc}")
            return

        self._folder_path = folder_path
        self._sample_pairs = sample_pairs
        self._normalization_available = bool(sample_pairs) and all(
            pair.area_csv is not None for pair in sample_pairs
        )
        self._sample_list.clear()
        for pair in sample_pairs:
            self._sample_list.addItem(pair.sample_name)
        self._folder_label.setText(str(folder_path))
        self._samples_label.setText(f"Discovered samples: {len(sample_pairs)}")
        self._update_normalization_availability()

        self.results_invalidated.emit()
        logger.info(
            "Loaded statistics folder %s with %d sample pairs",
            folder_path,
            len(sample_pairs),
        )
        if self._normalization_available:
            self.status_message.emit(
                f"Loaded statistics folder with {len(sample_pairs)} samples"
            )
        else:
            self.status_message.emit(
                "Loaded statistics folder with "
                f"{len(sample_pairs)} samples; area normalization disabled because at least one sample has no area CSV"
            )

    @Slot(str)
    def _on_mode_changed(self, mode: str) -> None:
        show_window = mode == "onset_shifted_relu"
        self._window_label.setVisible(show_window)
        self._window_spin.setVisible(show_window)
        self._sync_normalization_controls()
        self.results_invalidated.emit()

    @Slot(bool)
    def _on_normalize_toggled(self, _: bool) -> None:
        self._sync_normalization_controls()
        self.results_invalidated.emit()

    def _sync_normalization_controls(self) -> None:
        show_filter = (
            self._normalization_available and self._normalize_checkbox.isChecked()
        )
        self._filter_label.setVisible(show_filter)
        self._filter_spin.setVisible(show_filter)
        self._filter_spin.setEnabled(show_filter)

    def _update_normalization_availability(self) -> None:
        if not self._normalization_available and self._normalize_checkbox.isChecked():
            self._normalize_checkbox.setChecked(False)
        self._normalize_checkbox.setEnabled(self._normalization_available)
        self._sync_normalization_controls()

    @Slot()
    def _on_run_clicked(self) -> None:
        if self._folder_path is None:
            self.status_message.emit("Load a statistics folder before running.")
            return

        if not self._sample_pairs:
            self.status_message.emit("No valid sample pairs were found in this folder.")
            return

        request = StatisticsRequest(
            mode=self.mode,
            folder_path=self._folder_path,
            normalize_by_area=self._normalize_checkbox.isChecked(),
            fit_window_hours=float(self._window_spin.value()),
            area_filter_size=int(self._filter_spin.value()),
        )
        self.run_requested.emit(request)
