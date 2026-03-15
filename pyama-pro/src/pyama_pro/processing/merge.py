"""FOV assignment and CSV merging utilities."""

import logging
from pathlib import Path
from typing import Any

import yaml
from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pyama_core.processing.merge import read_samples_yaml, run_merge
from pyama_pro.constants import DEFAULT_DIR
from pyama_pro.types.processing import MergeRequest
from pyama_pro.utils import WorkerHandle, start_worker

logger = logging.getLogger(__name__)


def read_yaml_config(path: Path) -> dict[str, Any]:
    """Read a YAML config file with samples specification."""
    return read_samples_yaml(path)


class MergeRunner(QObject):
    """Background worker for running the merge process."""

    finished = Signal(bool, str)

    def __init__(self, request: MergeRequest) -> None:
        super().__init__()
        self._request = request

    def run(self) -> None:
        def progress_callback(current: int, total: int, message: str) -> None:
            if total > 0:
                progress = int((current / total) * 100)
                logger.info("%s: %d/%d (%d%%)", message, current, total, progress)
            else:
                logger.info("%s: %d", message, current)

        try:
            message = run_merge(
                self._request.samples,
                self._request.processing_results_dir,
                progress_callback=progress_callback,
            )
            self.finished.emit(True, message)
        except Exception as exc:
            logger.exception("Merge failed")
            self.finished.emit(False, str(exc))


class SampleTable(QTableWidget):
    """Editable table of sample names and FOV assignments."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 2, parent)
        self._build_ui()

    def _build_ui(self) -> None:
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
        for index in sorted(indexes, key=lambda item: item.row(), reverse=True):
            self.removeRow(index.row())

    def to_samples(self) -> list[dict[str, Any]]:
        samples = []
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

    def load_samples(self, samples: list[dict[str, Any]]) -> None:
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


class MergePanel(QWidget):
    """Panel for assigning FOVs and merging sample CSV outputs."""

    merge_started = Signal()
    merge_finished = Signal(bool, str)
    samples_loading_started = Signal()
    samples_loading_finished = Signal(bool, str)
    samples_saving_started = Signal()
    samples_saving_finished = Signal(bool, str)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._merge_runner: WorkerHandle | None = None
        self._table = SampleTable(self)
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        group = QGroupBox("Assign FOVs and Merge Samples")
        layout = QVBoxLayout(group)

        layout.addWidget(self._table)

        sample_btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add Sample")
        self._remove_btn = QPushButton("Remove Selected")
        sample_btn_row.addWidget(self._add_btn)
        sample_btn_row.addWidget(self._remove_btn)
        layout.addLayout(sample_btn_row)

        yaml_btn_row = QHBoxLayout()
        self._load_btn = QPushButton("Load from YAML")
        self._save_btn = QPushButton("Save to YAML")
        yaml_btn_row.addWidget(self._load_btn)
        yaml_btn_row.addWidget(self._save_btn)
        layout.addLayout(yaml_btn_row)

        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Processing Results Folder:"))
        folder_row.addStretch()
        self._processing_results_btn = QPushButton("Browse")
        folder_row.addWidget(self._processing_results_btn)
        layout.addLayout(folder_row)

        self._processing_results_dir_edit = QLineEdit()
        layout.addWidget(self._processing_results_dir_edit)

        hint_label = QLabel(
            "Merge reads processing_results.yaml from this folder and writes outputs to merge_output inside it."
        )
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

        self.run_btn = QPushButton("Run Merge")
        layout.addWidget(self.run_btn)

        main_layout.addWidget(group)

    def _connect_signals(self) -> None:
        self._add_btn.clicked.connect(self._on_add_row)
        self._remove_btn.clicked.connect(self._on_remove_row)
        self._load_btn.clicked.connect(self._on_load_requested)
        self._save_btn.clicked.connect(self._on_save_requested)
        self._processing_results_btn.clicked.connect(
            self._choose_processing_results_dir
        )
        self.run_btn.clicked.connect(self._on_merge_requested)

    @Slot()
    def _on_add_row(self) -> None:
        self._table.add_empty_row()

    @Slot()
    def _on_remove_row(self) -> None:
        self._table.remove_selected_row()

    @Slot()
    def _on_load_requested(self) -> None:
        logger.debug("UI Click: Load samples button (start_dir=%s)", DEFAULT_DIR)
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open sample.yaml",
            DEFAULT_DIR,
            "YAML Files (*.yaml *.yml);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self._load_samples(Path(file_path))

    @Slot()
    def _on_save_requested(self) -> None:
        logger.debug("UI Click: Save samples button (start_dir=%s)", DEFAULT_DIR)
        try:
            samples = self.current_samples()
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save sample.yaml",
                DEFAULT_DIR,
                "YAML Files (*.yaml *.yml);;All Files (*)",
                options=QFileDialog.Option.DontUseNativeDialog,
            )
            if file_path:
                self._save_samples(Path(file_path), samples)
        except ValueError as exc:
            logger.error("Failed to save samples: %s", exc)

    def _load_samples(self, path: Path) -> None:
        self.samples_loading_started.emit()
        try:
            data = read_yaml_config(path)
            samples = data.get("samples", [])
            if not isinstance(samples, list):
                raise ValueError("Invalid YAML: 'samples' must be list")
            self.load_samples(samples)
            logger.info("Loaded %d samples from %s", len(samples), path)
            self.samples_loading_finished.emit(True, f"Samples loaded from {path}")
        except Exception as exc:
            logger.error("Failed to load samples from %s: %s", path, exc)
            self.samples_loading_finished.emit(
                False,
                f"Failed to load samples from {path}: {exc}",
            )

    def _save_samples(self, path: Path, samples: list[dict[str, Any]]) -> None:
        self.samples_saving_started.emit()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as handle:
                yaml.safe_dump({"samples": samples}, handle, sort_keys=False)
            logger.info("Saved %d samples to %s", len(samples), path)
            self.samples_saving_finished.emit(True, f"Samples saved to {path}")
        except Exception as exc:
            logger.error("Failed to save samples to %s: %s", path, exc)
            self.samples_saving_finished.emit(
                False,
                f"Failed to save samples to {path}: {exc}",
            )

    @Slot()
    def _on_merge_requested(self) -> None:
        logger.debug(
            "UI Click: Run merge button (processing_results_dir=%s)",
            self._processing_results_dir_edit.text(),
        )
        if self._merge_runner:
            logger.warning("Merge already running")
            return

        try:
            samples = self.current_samples()
            processing_results_dir_text = self._processing_results_dir_edit.text().strip()
            if not processing_results_dir_text:
                return

            request = MergeRequest(
                samples=samples,
                processing_results_dir=Path(processing_results_dir_text).expanduser(),
            )
            logger.info(
                "Starting merge (processing_results_dir=%s, samples=%d)",
                request.processing_results_dir,
                len(request.samples),
            )

            worker = MergeRunner(request)
            worker.finished.connect(self._on_merge_finished)
            self._merge_runner = start_worker(
                worker,
                start_method="run",
                finished_callback=self._clear_merge_handle,
            )
            self.merge_started.emit()
        except Exception as exc:
            logger.error("Failed to start merge: %s", exc)

    @Slot(bool, str)
    def _on_merge_finished(self, success: bool, message: str) -> None:
        if success:
            logger.info("Merge completed successfully: %s", message)
        else:
            logger.error("Merge failed: %s", message)
        self.merge_finished.emit(success, message)

    def _clear_merge_handle(self) -> None:
        logger.info("Merge thread finished")
        self._merge_runner = None

    @Slot()
    def _choose_processing_results_dir(self) -> None:
        logger.debug(
            "UI Click: Browse processing results folder button (start_dir=%s)",
            DEFAULT_DIR,
        )
        path = QFileDialog.getExistingDirectory(
            self,
            "Select processing results folder",
            DEFAULT_DIR,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            logger.debug("UI Action: Set processing results folder - %s", path)
            self._processing_results_dir_edit.setText(path)

    def load_samples(self, samples: list[dict[str, Any]]) -> None:
        self._table.load_samples(samples)

    def current_samples(self) -> list[dict[str, Any]]:
        return self._table.to_samples()

    def set_processing_results_directory(self, path: Path | str) -> None:
        self._processing_results_dir_edit.setText(str(path))
