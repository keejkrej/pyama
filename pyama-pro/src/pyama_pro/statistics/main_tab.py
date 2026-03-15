"""Statistics tab orchestration for trace metrics and sample comparison."""

import logging
from pathlib import Path

import pandas as pd
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QHBoxLayout, QWidget

from pyama_core.statistics.service import run_folder_statistics
from pyama_pro.statistics.comparison import StatisticsComparisonPanel
from pyama_pro.statistics.detail import StatisticsDetailPanel
from pyama_pro.statistics.load import StatisticsLoadPanel
from pyama_pro.types.statistics import StatisticsRequest
from pyama_pro.utils import WorkerHandle, start_worker

logger = logging.getLogger(__name__)


class StatisticsWorker(QObject):
    """Background worker for folder-level statistics processing."""

    finished = Signal(bool, str)

    def __init__(self, request: StatisticsRequest) -> None:
        super().__init__()
        self._request = request
        self._results_df: pd.DataFrame | None = None
        self._traces_by_sample: dict[str, pd.DataFrame] = {}
        self._saved_csv_path: Path | None = None

    def process_data(self) -> None:
        try:
            (
                self._results_df,
                self._traces_by_sample,
                self._saved_csv_path,
            ) = run_folder_statistics(
                self._request.folder_path,
                self._request.mode,
                normalize_by_area=self._request.normalize_by_area,
                fit_window_hours=self._request.fit_window_hours,
                area_filter_size=self._request.area_filter_size,
            )
        except Exception as exc:
            logger.exception("Statistics processing failed")
            self.finished.emit(False, str(exc))
            return

        mode_label = "AUC" if self._request.mode == "auc" else "Onset"
        normalization_label = (
            "area-normalized" if self._request.normalize_by_area else "raw intensity"
        )
        save_name = self._saved_csv_path.name if self._saved_csv_path else "results"
        self.finished.emit(
            True,
            f"{mode_label} statistics ({normalization_label}) saved to {save_name}",
        )


class StatisticsTab(QWidget):
    """Statistics page orchestration."""

    processing_started = Signal()
    processing_finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status_manager = None
        self._worker: StatisticsWorker | None = None
        self._worker_handle: WorkerHandle | None = None
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)

        self._load_panel = StatisticsLoadPanel(self)
        self._detail_panel = StatisticsDetailPanel(self)
        self._comparison_panel = StatisticsComparisonPanel(self)

        layout.addWidget(self._load_panel, 1)
        layout.addWidget(self._detail_panel, 1)
        layout.addWidget(self._comparison_panel, 1)

    def _connect_signals(self) -> None:
        self._load_panel.results_invalidated.connect(self._clear_results)
        self._load_panel.run_requested.connect(self._start_worker)
        self._load_panel.status_message.connect(self._on_status_message)

    def set_status_manager(self, status_manager) -> None:
        self._status_manager = status_manager

    @Slot()
    def _clear_results(self) -> None:
        self._detail_panel.clear()
        self._comparison_panel.clear()

    @Slot(str)
    def _on_status_message(self, message: str) -> None:
        if self._status_manager:
            self._status_manager.show_message(message)

    def _start_worker(self, request: StatisticsRequest) -> None:
        self.processing_started.emit()
        if self._status_manager:
            self._status_manager.show_message("Running statistics...")

        self._worker = StatisticsWorker(request)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker_handle = start_worker(
            self._worker,
            start_method="process_data",
            finished_callback=lambda: setattr(self, "_worker_handle", None),
        )
        self._load_panel.set_processing_active(True)

    @Slot(bool, str)
    def _on_worker_finished(self, success: bool, message: str) -> None:
        self._load_panel.set_processing_active(False)
        self.processing_finished.emit()

        if success and self._worker and self._worker._results_df is not None:
            mode = self._worker._request.mode
            self._detail_panel.set_results(
                self._worker._results_df,
                self._worker._traces_by_sample,
                mode,
                normalize_by_area=self._worker._request.normalize_by_area,
            )
            self._comparison_panel.set_results(self._worker._results_df, mode)
            logger.info("Statistics processing completed: %s", message)
        else:
            logger.error("Statistics processing failed: %s", message)

        if self._status_manager:
            self._status_manager.show_message(message)
