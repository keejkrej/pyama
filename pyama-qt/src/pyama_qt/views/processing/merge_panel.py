import logging

from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from pyama_qt.components import PathSelector, PathType
from pyama_qt.config import DEFAULT_DIR

logger = logging.getLogger(__name__)


class SampleTable(QTableWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 2, parent)
        self.setHorizontalHeaderLabels(["Sample Name", "FOVs (e.g., 0-5, 7, 9-11)"])
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)

    def add_empty_row(self) -> None:
        row = self.rowCount()
        self.insertRow(row)
        name_item = QTableWidgetItem("")
        fovs_item = QTableWidgetItem("")
        name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsEditable)
        fovs_item.setFlags(fovs_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, 0, name_item)
        self.setItem(row, 1, fovs_item)
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
        for idx in sorted(indexes, key=lambda i: i.row(), reverse=True):
            self.removeRow(idx.row())

    def to_samples(self) -> list[dict[str, Any]]:
        """Convert table data to samples list with validation. Emit error if invalid."""
        samples = []
        seen_names = set()

        for row in range(self.rowCount()):
            name_item = self.item(row, 0)
            fovs_item = self.item(row, 1)
            name = (name_item.text() if name_item else "").strip()
            fovs_text = (fovs_item.text() if fovs_item else "").strip()

            # Validate name
            if not name:
                raise ValueError(f"Row {row + 1}: Sample name is required")
            if name in seen_names:
                raise ValueError(f"Row {row + 1}: Duplicate sample name '{name}'")
            seen_names.add(name)

            # Parse and validate FOVs
            if not fovs_text:
                raise ValueError(
                    f"Row {row + 1} ('{name}'): At least one FOV is required"
                )

            samples.append({"name": name, "fovs": fovs_text})

        return samples

    def load_samples(self, samples: list[dict[str, Any]]) -> None:
        """Load samples data into the table."""
        self.setRowCount(0)
        for sample in samples:
            name = str(sample.get("name", ""))
            fovs_val = sample.get("fovs", [])

            if isinstance(fovs_val, list):
                fovs_text = ", ".join(str(int(v)) for v in fovs_val)
            elif isinstance(fovs_val, str):
                fovs_text = fovs_val
            else:
                fovs_text = ""

            self.add_row(name, fovs_text)


class ProcessingMergePanel(QWidget):
    """Panel responsible for FOV assignment and CSV merging utilities."""

    # Signals for controller
    load_samples_requested = Signal(Path)
    save_samples_requested = Signal(Path)
    merge_requested = Signal()  # Simple signal - controller reads from model
    samples_changed = Signal(list[dict[str, Any]])  # For real-time updates if needed

    # Path change signals
    sample_yaml_path_changed = Signal(Path)
    processing_results_path_changed = Signal(Path)
    merge_output_dir_changed = Signal(Path)

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

        # File/folder selectors using PathSelector component
        self.sample_selector = PathSelector(
            label="Sample YAML:",
            path_type=PathType.FILE,
            dialog_title="Select sample.yaml",
            file_filter="YAML Files (*.yaml *.yml)",
            default_dir=DEFAULT_DIR,
        )
        layout.addWidget(self.sample_selector)

        self.processing_results_selector = PathSelector(
            label="Processing Results YAML:",
            path_type=PathType.FILE,
            dialog_title="Select processing_results.yaml",
            file_filter="YAML Files (*.yaml *.yml)",
            default_dir=DEFAULT_DIR,
        )
        layout.addWidget(self.processing_results_selector)

        self.output_selector = PathSelector(
            label="Output folder:",
            path_type=PathType.DIRECTORY,
            dialog_title="Select output folder",
            default_dir=DEFAULT_DIR,
        )
        layout.addWidget(self.output_selector)

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

        # Path selector changes
        self.sample_selector.path_changed.connect(
            lambda path: self.sample_yaml_path_changed.emit(Path(path))
        )
        self.processing_results_selector.path_changed.connect(
            lambda path: self.processing_results_path_changed.emit(Path(path))
        )
        self.output_selector.path_changed.connect(
            lambda path: self.merge_output_dir_changed.emit(Path(path))
        )

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
        """Request merge via signal - controller will read paths from model."""
        self.merge_requested.emit()

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
        self.sample_selector.set_path(path)

    def set_processing_results_path(self, path: Path | str) -> None:
        self.processing_results_selector.set_path(path)

    def set_output_directory(self, path: Path | str) -> None:
        self.output_selector.set_path(path)
