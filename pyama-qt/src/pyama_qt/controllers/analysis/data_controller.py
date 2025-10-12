"""Controller for analysis data panel interactions."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QObject

from pyama_qt.models.analysis import AnalysisModel
from pyama_qt.views.analysis.view import AnalysisView

logger = logging.getLogger(__name__)


class AnalysisDataController(QObject):
    """Handles CSV loading and plot rendering for the analysis data panel."""

    def __init__(
        self,
        view: AnalysisView,
        model: AnalysisModel,
        *,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._model = model

        self._current_plot_title: str = ""
        self._current_plot_data: Sequence[tuple] | None = None

        self._connect_view_signals()
        self._connect_model_signals()

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------
    def _connect_view_signals(self) -> None:
        self._view.data_panel.csv_selected.connect(self._on_csv_selected)

    def _connect_model_signals(self) -> None:
        data_model = self._model.data_model
        data_model.plotDataChanged.connect(self._handle_plot_data_changed)
        data_model.plotTitleChanged.connect(self._handle_plot_title_changed)

    # ------------------------------------------------------------------
    # View → Controller handlers
    # ------------------------------------------------------------------
    def _on_csv_selected(self, path: Path) -> None:
        self._load_csv(path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_csv(self, path: Path) -> None:
        self._model.data_model.load_csv(path)

        fitted_path = path.parent / f"{path.stem}_fitted.csv"
        if fitted_path.exists():
            try:
                self._model.results_model.load_from_csv(fitted_path)
                logger.info("Loaded existing fitted results from %s", fitted_path)
            except Exception as exc:
                logger.warning(
                    "Failed to load fitted results from %s: %s", fitted_path, exc
                )
        else:
            self._model.results_model.clear_results()
            logger.info("No fitted results found for %s", path)

        self._view.status_bar.showMessage(f"Loaded {path.name}")

    def _handle_plot_data_changed(self, plot_data: Sequence[tuple] | None) -> None:
        self._current_plot_data = plot_data
        self._view.data_panel.render_plot(
            plot_data,
            title=self._current_plot_title,
            x_label="Time (hours)",
            y_label="Intensity",
        )

    def _handle_plot_title_changed(self, title: str) -> None:
        self._current_plot_title = title
        self._view.data_panel.render_plot(
            self._current_plot_data,
            title=title,
            x_label="Time (hours)",
            y_label="Intensity",
        )
