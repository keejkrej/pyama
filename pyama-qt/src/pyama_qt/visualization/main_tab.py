"""Visualization page composed of project, image, and trace panels."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QHBoxLayout, QWidget

from pyama_qt.visualization.image import ImageViewerWindow
from pyama_qt.visualization.load import LoadPanel
from pyama_qt.visualization.trace import TracePanel

logger = logging.getLogger(__name__)


# =============================================================================
# MAIN VISUALIZATION TAB
# =============================================================================


class VisualizationTab(QWidget):
    """Embeddable visualization page comprising consolidated project, image, and trace panels.

    This tab orchestrates the interactions between the panels, managing signal
    routing and status updates for the visualization workflow. It provides a
    unified interface for loading project data, viewing microscopy images,
    and analyzing trace data.
    """

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the visualization tab.

        Args:
            parent: Parent widget (default: None)
        """
        super().__init__(parent)
        self._status_manager = None
        self._image_window: ImageViewerWindow | None = None
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # STATUS MANAGER INTEGRATION
    # ------------------------------------------------------------------------
    def set_status_manager(self, status_manager) -> None:
        """Set the status manager for coordinating background operations.

        Args:
            status_manager: Status manager instance for displaying messages
        """
        self._status_manager = status_manager

    # ------------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Create and arrange the UI panels.

        Creates a horizontal layout with two panels:
        1. Load panel (1/3 width) for project loading and FOV selection
        2. Trace panel (2/3 width) for displaying trace data

        The image viewer is displayed in a separate popup window.
        """
        layout = QHBoxLayout(self)

        # Create panels
        self._load_panel = LoadPanel(self)
        self._trace_panel = TracePanel(self)

        # Arrange panels with appropriate spacing
        layout.addWidget(self._load_panel, 1)
        layout.addWidget(self._trace_panel, 2)

        # Note: Image panel is in a separate popup window (ImageViewerWindow)

    # ------------------------------------------------------------------------
    # PANEL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect all signals between panels.

        Establishes the communication pathways between panels:
        - Load panel -> opens ImageViewerWindow popup
        - ImageViewerWindow -> Trace panel: FOV data and cell selection
        - Trace panel -> ImageViewerWindow: active trace and position updates

        Also connects status signals for centralized status reporting.
        """
        # Load Panel -> Visualization Tab (manages popup window)
        self._load_panel.cleanup_requested.connect(self._on_cleanup_requested)
        self._load_panel.visualization_requested.connect(
            self._on_visualization_requested
        )

        # Status signals
        self._connect_status_signals()

    def _connect_image_window_signals(self) -> None:
        """Connect signals between ImageViewerWindow and TracePanel.

        Called when the image window is created to establish signal routing.
        """
        if self._image_window is None:
            return

        # ImageViewerWindow -> LoadPanel (loading state)
        self._image_window.loading_state_changed.connect(self._load_panel.set_loading)

        # ImageViewerWindow -> TracePanel
        self._image_window.fov_data_loaded.connect(self._trace_panel.on_fov_data_loaded)
        self._image_window.cell_selected.connect(self._trace_panel.on_cell_selected)
        self._image_window.trace_quality_toggled.connect(
            self._trace_panel.on_trace_quality_toggled
        )
        self._image_window.frame_changed.connect(self._trace_panel.on_frame_changed)

        # TracePanel -> ImageViewerWindow
        self._trace_panel.active_trace_changed.connect(
            self._image_window.on_active_trace_changed
        )
        self._trace_panel.positions_updated.connect(
            self._image_window.on_trace_positions_updated
        )

        # Window lifecycle
        self._image_window.window_closed.connect(self._on_image_window_closed)

    @Slot(dict, int, list)
    def _on_visualization_requested(
        self, project_data: dict, fov_id: int, selected_channels: list[str]
    ) -> None:
        """Handle visualization request by opening/reusing popup window.

        Args:
            project_data: Dictionary containing project information
            fov_id: ID of the FOV to visualize
            selected_channels: List of channel names to load
        """
        # Create window if not exists or was closed
        if self._image_window is None:
            self._image_window = ImageViewerWindow(self)
            self._connect_image_window_signals()

        # Show and raise the window
        self._image_window.show()
        self._image_window.raise_()
        self._image_window.activateWindow()

        # Request visualization
        self._image_window.on_visualization_requested(
            project_data, fov_id, selected_channels
        )

    @Slot()
    def _on_image_window_closed(self) -> None:
        """Handle image window closed event."""
        self._image_window = None

    def _connect_status_signals(self) -> None:
        """Connect visualization-related status signals.

        Connects all status signals from child panels to their respective
        handlers to provide centralized status reporting through the
        status manager.
        """
        # Image loading status signals removed - only show final trace loading result
        self._load_panel.project_loading_started.connect(
            self._on_project_loading_started
        )
        self._load_panel.project_loading_finished.connect(
            self._on_project_loading_finished
        )

        # Connect trace panel status signals
        self._trace_panel.trace_data_loaded.connect(self._on_trace_data_loaded)
        self._trace_panel.trace_data_saved.connect(self._on_trace_data_saved)

    # ------------------------------------------------------------------------
    # CLEANUP HANDLING
    # ------------------------------------------------------------------------
    def _on_cleanup_requested(self) -> None:
        """Handle cleanup request from load panel.

        Clears all existing plots and loaded traces before starting
        a new visualization session.
        """
        logger.debug(
            "UI Event: Cleanup requested - clearing all panels and cached overlays"
        )

        # Clear image window if it exists (plots, cache, overlays)
        if self._image_window is not None:
            self._image_window._image_panel.clear_all()

        # Clear trace panel (traces, plots, data)
        self._trace_panel.clear()

        logger.debug(
            "UI Action: All panels cleared successfully (image, trace, overlays reset)"
        )

    # ------------------------------------------------------------------------
    # STATUS MANAGER INTEGRATION
    # ------------------------------------------------------------------------

    def _on_project_loading_started(self) -> None:
        """Handle project loading started event.

        Logs the event and updates the status message if a status manager is available.
        """
        if self._status_manager:
            self._status_manager.show_message("Loading project data...")

    def _on_project_loading_finished(self, success: bool, message: str) -> None:
        """Handle project loading finished event.

        Args:
            success: Whether the project loaded successfully
            message: Status message from the project loading
        """
        if self._status_manager:
            if success:
                self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(f"Failed to load project: {message}")

    def _on_trace_data_loaded(self, success: bool, message: str) -> None:
        """Handle trace data loading finished event.

        Args:
            success: Whether the trace data loaded successfully
            message: Status message from the trace data loading
        """
        if self._status_manager:
            if success:
                self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(f"Failed to load traces: {message}")

    def _on_trace_data_saved(self, success: bool, message: str) -> None:
        """Handle trace data saving finished event.

        Args:
            success: Whether the trace data saved successfully
            message: Status message from the trace data saving
        """
        if self._status_manager:
            if success:
                self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(f"Failed to save traces: {message}")

    # ------------------------------------------------------------------------
    # FUTURE STATUS BAR INTEGRATION
    # ------------------------------------------------------------------------
    def _setup_status_bar_connections(self, main_window_status_bar) -> None:
        """Example of connecting panels to a central status bar.

        This method shows how to connect all panels to a main window status bar
        if one becomes available in the future. It demonstrates the pattern
        for connecting error messages with longer display times.

        Args:
            main_window_status_bar: Status bar widget from the main window
        """
        # Connect error messages with longer display time
        self._load_panel.error_message.connect(
            lambda msg: main_window_status_bar.showMessage(f"Error: {msg}", 5000)
        )
        # Note: ImageViewerWindow has its own status bar, so no connection needed here
