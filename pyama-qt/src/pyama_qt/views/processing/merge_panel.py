import logging

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyama_qt.config import DEFAULT_DIR
from pyama_qt.components.sample_table import SampleTable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MergeRequestPayload:
    """Lightweight container describing merge inputs."""

    sample_yaml: Path
    processing_results_yaml: Path
    data_dir: Path
    output_dir: Path


class ProcessingMergePanel(QWidget):
    """Panel responsible for FOV assignment and CSV merging utilities."""

    # Signals for controller
    load_samples_requested = Signal(Path)
    save_samples_requested = Signal(Path)
    merge_requested = Signal(object)  # Emits MergeRequestPayload
    samples_changed = Signal(list[dict[str, Any]])  # For real-time updates if needed

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.table: SampleTable | None = None
        self.build()
        self.bind()

    def build(self) -> None:
        """Build UI components."""
        main_layout = QVBoxLayout(self)

        # Create the two main sections
        assign_group = self._create_assign_group()
        merge_group = self._create_merge_group()

        # Add to main layout with equal stretch
        main_layout.addWidget(assign_group, 1)
        main_layout.addWidget(merge_group, 1)

    def _create_assign_group(self) -> QGroupBox:
        """Create the FOV assignment section."""
        group = QGroupBox("Assign FOVs")
        layout = QVBoxLayout(group)

        # Table
        if self.table is None:
            self.table = SampleTable(self)
        layout.addWidget(self.table)

        # Create buttons
        self.add_btn = QPushButton("Add Sample")
        self.remove_btn = QPushButton("Remove Selected")
        self.load_btn = QPushButton("Load from YAML")
        self.save_btn = QPushButton("Save to YAML")

        # Arrange buttons in rows
        btn_row1 = QHBoxLayout()
        btn_row1.addWidget(self.add_btn)
        btn_row1.addWidget(self.remove_btn)

        btn_row2 = QHBoxLayout()
        btn_row2.addWidget(self.load_btn)
        btn_row2.addWidget(self.save_btn)

        layout.addLayout(btn_row1)
        layout.addLayout(btn_row2)

        return group

    def _create_merge_group(self) -> QGroupBox:
        """Create the merge samples section."""
        group = QGroupBox("Merge Samples")
        layout = QVBoxLayout(group)

        # File/folder selectors
        # Sample YAML selector
        sample_row = QHBoxLayout()
        sample_row.addWidget(QLabel("Sample YAML:"))
        sample_row.addStretch()
        sample_browse_btn = QPushButton("Browse")
        sample_browse_btn.clicked.connect(self._choose_sample)
        sample_row.addWidget(sample_browse_btn)
        layout.addLayout(sample_row)
        self.sample_edit = QLineEdit()
        layout.addWidget(self.sample_edit)

        # Processing Results YAML selector
        processing_results_row = QHBoxLayout()
        processing_results_row.addWidget(QLabel("Processing Results YAML:"))
        processing_results_row.addStretch()
        processing_results_browse_btn = QPushButton("Browse")
        processing_results_browse_btn.clicked.connect(self._choose_processing_results)
        processing_results_row.addWidget(processing_results_browse_btn)
        layout.addLayout(processing_results_row)
        self.processing_results_edit = QLineEdit()
        layout.addWidget(self.processing_results_edit)

        # CSV folder selector
        data_row = QHBoxLayout()
        data_row.addWidget(QLabel("CSV folder:"))
        data_row.addStretch()
        data_browse_btn = QPushButton("Browse")
        data_browse_btn.clicked.connect(self._choose_data_dir)
        data_row.addWidget(data_browse_btn)
        layout.addLayout(data_row)
        self.data_edit = QLineEdit()
        layout.addWidget(self.data_edit)

        # Output folder selector
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Output folder:"))
        output_row.addStretch()
        output_browse_btn = QPushButton("Browse")
        output_browse_btn.clicked.connect(self._choose_output_dir)
        output_row.addWidget(output_browse_btn)
        layout.addLayout(output_row)
        self.output_edit = QLineEdit()
        layout.addWidget(self.output_edit)

        # Run button
        actions = QHBoxLayout()
        self.run_btn = QPushButton("Run Merge")
        actions.addWidget(self.run_btn)
        layout.addLayout(actions)

        return group

    def bind(self) -> None:
        """Connect widget signals."""
        # Table buttons
        self.add_btn.clicked.connect(self.table.add_empty_row)
        self.remove_btn.clicked.connect(self.table.remove_selected_row)
        self.load_btn.clicked.connect(self._on_load_requested)
        self.save_btn.clicked.connect(self._on_save_requested)

        # Merge button
        self.run_btn.clicked.connect(self._on_merge_requested)

        # Optional: Connect table changes to emit samples_changed if real-time needed
        # For now, emit on load/save

    def _on_load_requested(self) -> None:
        """Request load via signal."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open sample.yaml",
            DEFAULT_DIR,
            "YAML Files (*.yaml *.yml);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self.load_samples_requested.emit(Path(file_path))

    def _on_save_requested(self) -> None:
        """Request save via signal."""
        try:
            # Note: samples_changed signal not currently connected, so skip emit
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save sample.yaml",
                DEFAULT_DIR,
                "YAML Files (*.yaml *.yml);;All Files (*)",
                options=QFileDialog.Option.DontUseNativeDialog,
            )
            if file_path:
                self.save_samples_requested.emit(Path(file_path))
        except ValueError:
            pass

    def _on_merge_requested(self) -> None:
        """Request merge via signal after basic validation."""
        try:
            sample_text = self.sample_edit.text().strip()
            processing_text = self.processing_results_edit.text().strip()
            data_text = self.data_edit.text().strip()
            output_text = self.output_edit.text().strip()

            if not all([sample_text, processing_text, data_text, output_text]):
                raise ValueError("All paths must be specified")

            payload = MergeRequestPayload(
                sample_yaml=Path(sample_text).expanduser(),
                processing_results_yaml=Path(processing_text).expanduser(),
                data_dir=Path(data_text).expanduser(),
                output_dir=Path(output_text).expanduser(),
            )
            self.merge_requested.emit(payload)
        except ValueError as exc:
            logger.warning("Invalid merge request: %s", exc)

    def _choose_sample(self) -> None:
        """Browse for sample YAML file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select sample.yaml",
            DEFAULT_DIR,
            "YAML Files (*.yaml *.yml)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.sample_edit.setText(path)

    def _choose_processing_results(self) -> None:
        """Browse for processing results YAML file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select processing_results.yaml",
            DEFAULT_DIR,
            "YAML Files (*.yaml *.yml)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.processing_results_edit.setText(path)

    def _choose_data_dir(self) -> None:
        """Browse for CSV data directory."""
        path = QFileDialog.getExistingDirectory(
            self,
            "Select FOV CSV folder",
            DEFAULT_DIR,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.data_edit.setText(path)

    def _choose_output_dir(self) -> None:
        """Browse for output directory."""
        path = QFileDialog.getExistingDirectory(
            self,
            "Select output folder",
            DEFAULT_DIR,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.output_edit.setText(path)

    # ------------------------------------------------------------------
    # Controller helpers
    # ------------------------------------------------------------------
    def load_samples(self, samples: list[dict[str, Any]]) -> None:
        """Populate the sample table with controller-supplied content."""
        if self.table is None:
            self.table = SampleTable(self)
        self.table.load_samples(samples)

    def current_samples(self) -> list[dict[str, Any]]:
        """Return the current sample definitions."""
        if self.table is None:
            return []
        return self.table.to_samples()

    def set_sample_yaml_path(self, path: Path | str) -> None:
        self.sample_edit.setText(str(path))

    def set_processing_results_path(self, path: Path | str) -> None:
        self.processing_results_edit.setText(str(path))

    def set_data_directory(self, path: Path | str) -> None:
        self.data_edit.setText(str(path))

    def set_output_directory(self, path: Path | str) -> None:
        self.output_edit.setText(str(path))
