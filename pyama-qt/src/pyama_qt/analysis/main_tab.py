"""Analysis tab composed of comparison panel."""

import logging
from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QHBoxLayout, QWidget

from pyama_qt.analysis.analysis_window import AnalysisWindow
from pyama_qt.analysis.comparison import ComparisonPanel

logger = logging.getLogger(__name__)


class AnalysisTab(QWidget):
    """Analysis tab containing the comparison panel.

    This tab manages the AnalysisWindow signal connections and provides
    the status manager to the comparison panel.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the analysis tab.

        Args:
            parent: Parent widget (default: None)
        """
        super().__init__(parent)
        self._status_manager = None
        self._open_windows: dict[Path, AnalysisWindow] = {}
        
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        """Create the user interface layout."""
        layout = QHBoxLayout(self)

        # Create and add the comparison panel
        self._comparison_panel = ComparisonPanel(self)
        layout.addWidget(self._comparison_panel)

    def _connect_signals(self) -> None:
        """Connect signals between panel and tab."""
        # Connect comparison panel signals to handle AnalysisWindow management
        self._comparison_panel.window_request.connect(self._on_window_request)

    def _on_window_request(
        self, 
        csv_path: Path, 
        data: object, 
        fitted_path: Path | None,
        frame_interval: float,
        time_mapping: dict[int, float] | None,
    ) -> None:
        """Handle request to open AnalysisWindow.

        Args:
            csv_path: Path to the analysis CSV file
            data: Pre-loaded DataFrame data
            fitted_path: Optional path to fitted results
            frame_interval: Frame interval used
            time_mapping: Optional time mapping
        """
        # Check if already open
        if csv_path in self._open_windows:
            # Bring existing window to front
            self._open_windows[csv_path].raise_()
            self._open_windows[csv_path].activateWindow()
            return

        # Check window limit
        if len(self._open_windows) >= 1:
            logger.warning("Window limit reached, cannot open new analysis window")
            return

        # Create and show analysis window
        window = AnalysisWindow(
            csv_path, 
            data, 
            fitted_path,
            frame_interval=frame_interval,
            time_mapping=time_mapping,
            parent=None
        )
        window.window_closed.connect(self._on_window_closed)
        self._open_windows[csv_path] = window
        window.show()

        logger.info(
            "Opened analysis window for %s (fitted=%s, interval=%.4f, mapping=%s)",
            csv_path.name,
            fitted_path.name if fitted_path else None,
            frame_interval,
            time_mapping is not None,
        )

    @Slot(object)
    def _on_window_closed(self, csv_path: Path) -> None:
        """Handle analysis window close event.

        Args:
            csv_path: Path of the CSV file whose window was closed
        """
        if csv_path in self._open_windows:
            del self._open_windows[csv_path]
            logger.info("Removed window reference for %s", csv_path.name)

    def set_status_manager(self, status_manager) -> None:
        """Set the status manager for status updates.

        Args:
            status_manager: Status manager instance for displaying messages
        """
        self._status_manager = status_manager
        self._comparison_panel.set_status_manager(status_manager)
