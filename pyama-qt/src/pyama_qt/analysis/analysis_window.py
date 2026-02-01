"""Standalone analysis window for individual sample analysis.

This module provides the AnalysisWindow which is a self-contained window
for analyzing a single sample. It embeds the same panels as the original
AnalysisTab but with its own status bar and without load buttons.
"""

import logging
from pathlib import Path

import pandas as pd
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStatusBar,
    QWidget,
)

from pyama_qt.analysis.data import DataPanel
from pyama_qt.analysis.parameter import ParameterPanel
from pyama_qt.analysis.quality import QualityPanel

logger = logging.getLogger(__name__)


class StatusManager(QObject):
    """Status manager for showing user-friendly messages in the analysis window."""

    status_message = Signal(str)
    status_cleared = Signal()

    def show_message(self, message: str) -> None:
        """Show a status message."""
        logger.debug("AnalysisWindow Status: %s", message)
        self.status_message.emit(message)

    def clear_status(self) -> None:
        """Clear the status message."""
        self.status_cleared.emit()


class StatusBar(QStatusBar):
    """Status bar for the analysis window."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status_label = QLabel("Ready")
        self.addWidget(self._status_label)

    def show_status_message(self, message: str) -> None:
        """Display status message."""
        self._status_label.setText(message)

    def clear_status(self) -> None:
        """Clear status and show ready state."""
        self._status_label.setText("Ready")


class AnalysisWindow(QMainWindow):
    """Standalone window for analyzing a single sample.

    This window provides the same functionality as the AnalysisTab but
    as an independent window with its own status bar. It is opened from
    the AnalysisTab when the user double-clicks a sample card.

    The window receives pre-loaded data and optionally pre-loaded fitted
    results, eliminating the need for load buttons.
    """

    window_closed = Signal(object)  # Emitted when window is closed (Path)

    def __init__(
        self,
        csv_path: Path,
        data: pd.DataFrame,
        fitted_path: Path | None = None,
        frame_interval: float = 1 / 6,
        time_mapping: dict[int, float] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the analysis window.

        Args:
            csv_path: Path to the analysis CSV file
            data: Pre-loaded DataFrame with MultiIndex (fov, cell)
            fitted_path: Optional path to fitted results CSV (auto-loaded if provided)
            frame_interval: Frame interval used for data (for reference)
            time_mapping: Time mapping used for data (for reference)
            parent: Parent widget
        """
        super().__init__(parent)
        self._csv_path = csv_path
        self._data = data
        self._fitted_path = fitted_path
        self._frame_interval = frame_interval
        self._time_mapping = time_mapping

        self._status_manager = StatusManager(self)
        self._build_ui()
        self._connect_signals()
        self._load_data()

    def _build_ui(self) -> None:
        """Build the window UI."""
        title = f"Analysis: {self._csv_path.name}"
        if self._time_mapping:
            title += " [custom time]"
        self.setWindowTitle(title)
        self.resize(1400, 700)

        # Create central widget with horizontal layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)

        # Create panels (without load buttons)
        self._data_panel = DataPanel(self, show_load_buttons=False)
        self._quality_panel = QualityPanel(self)
        self._parameter_panel = ParameterPanel(self)

        # Arrange panels horizontally
        layout.addWidget(self._data_panel, 1)
        layout.addWidget(self._quality_panel, 1)
        layout.addWidget(self._parameter_panel, 1)

        # Create status bar
        self._status_bar = StatusBar(self)
        self.setStatusBar(self._status_bar)

    def _connect_signals(self) -> None:
        """Connect all signals between panels and status manager."""
        # Data Panel -> Quality Panel
        self._data_panel.raw_data_changed.connect(
            self._quality_panel.on_raw_data_changed
        )
        self._data_panel.fitting_completed.connect(
            self._quality_panel.on_fitting_completed
        )

        # Data Panel -> Parameter Panel
        self._data_panel.fitting_completed.connect(
            self._parameter_panel.on_fitting_completed
        )
        self._data_panel.fitted_results_loaded.connect(
            self._parameter_panel.on_fitting_completed
        )
        self._data_panel.fitted_results_loaded.connect(
            self._quality_panel.on_fitted_results_changed
        )

        # Parameter Panel -> Quality Panel
        self._parameter_panel.results_loaded.connect(
            self._quality_panel.on_fitted_results_changed
        )

        # Status signals
        self._status_manager.status_message.connect(
            self._status_bar.show_status_message
        )
        self._status_manager.status_cleared.connect(
            self._status_bar.clear_status
        )

        # Connect panel status signals
        self._data_panel.fitting_started.connect(self._on_fitting_started)
        self._data_panel.fitting_finished.connect(self._on_fitting_finished)
        self._data_panel.data_loading_finished.connect(self._on_data_loading_finished)
        self._parameter_panel.plot_saved.connect(self._on_plot_saved)

    def _load_data(self) -> None:
        """Load the pre-loaded data into panels."""
        # Set data in data panel
        self._data_panel.set_data(self._csv_path, self._data)

        # Auto-load fitted results if path provided
        if self._fitted_path and self._fitted_path.exists():
            try:
                fitted_df = pd.read_csv(self._fitted_path)
                self._data_panel.set_fitted_results(fitted_df)
                logger.info(
                    "Auto-loaded fitted results from %s (%d rows)",
                    self._fitted_path.name,
                    len(fitted_df),
                )
            except Exception as e:
                logger.warning("Failed to auto-load fitted results: %s", e)

    @Slot()
    def _on_fitting_started(self) -> None:
        """Handle fitting started event."""
        self._status_manager.show_message("Fitting analysis models...")

    @Slot(bool, str)
    def _on_fitting_finished(self, success: bool, message: str) -> None:
        """Handle fitting finished event."""
        if success:
            if message:
                self._status_manager.show_message(message)
        else:
            self._status_manager.show_message(f"Fitting failed: {message}")

    @Slot(bool, str)
    def _on_data_loading_finished(self, success: bool, message: str) -> None:
        """Handle data loading finished event."""
        if success:
            self._status_manager.show_message(message)
        else:
            self._status_manager.show_message(f"Failed to load data: {message}")

    @Slot(str, str)
    def _on_plot_saved(self, filename: str, folder: str) -> None:
        """Handle plot saved event."""
        self._status_manager.show_message(f"{filename} saved to {folder}")

    def closeEvent(self, event) -> None:
        """Handle window close event."""
        logger.info("Analysis window closed: %s", self._csv_path.name)
        self.window_closed.emit(self._csv_path)
        super().closeEvent(event)
