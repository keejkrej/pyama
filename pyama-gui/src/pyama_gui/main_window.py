"""Primary application window hosting all PyAMA views without MVC separation."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
from importlib import import_module

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStatusBar,
    QTabWidget,
    QWidget,
)

logger = logging.getLogger(__name__)

_TAB_SPECS = (
    ("processing_tab", "Processing", "pyama_gui.processing.main_tab", "ProcessingTab"),
    ("statistics_tab", "Statistics", "pyama_gui.statistics.main_tab", "StatisticsTab"),
    ("modeling_tab", "Modeling", "pyama_gui.modeling.main_tab", "ModelingTab"),
    (
        "visualization_tab",
        "Visualization",
        "pyama_gui.visualization.main_tab",
        "VisualizationTab",
    ),
)


class _LazyTabContainer(QWidget):
    """Container that hosts a tab widget only when it is first requested."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.label = label
        self._loaded_widget: QWidget | None = None
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

    @property
    def loaded_widget(self) -> QWidget | None:
        return self._loaded_widget

    def set_loaded_widget(self, widget: QWidget) -> None:
        if self._loaded_widget is not None:
            return
        self._loaded_widget = widget
        self._layout.addWidget(widget)


# =============================================================================
# STATUS MANAGER
# =============================================================================


class StatusManager(QObject):
    """Status manager for showing user-friendly messages."""

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    status_message = Signal(str)  # message
    status_cleared = Signal()  # Clear the status

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

    # ------------------------------------------------------------------------
    # STATUS METHODS
    # ------------------------------------------------------------------------
    def show_message(self, message: str) -> None:
        """Show a status message."""
        logger.debug("Status Bar: Rendering user status message: %s", message)
        self.status_message.emit(message)

    def clear_status(self) -> None:
        """Clear the status message."""
        logger.debug("Status Bar: Clearing status message and reverting to ready state")
        self.status_cleared.emit()


# =============================================================================
# STATUS BAR
# =============================================================================


class StatusBar(QStatusBar):
    """Status bar for displaying status messages only."""

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Set up the status bar UI components."""
        # Main status label
        self._status_label = QLabel("Ready")
        self.addWidget(self._status_label)

    def _connect_signals(self) -> None:
        """Connect signals for the status bar."""
        pass

    # ------------------------------------------------------------------------
    # STATUS UPDATES
    # ------------------------------------------------------------------------
    def show_status_message(self, message: str) -> None:
        """Display status message."""
        self._status_label.setText(message)

    def clear_status(self) -> None:
        """Clear status and show ready state."""
        self._status_label.setText("Ready")


# =============================================================================
# MAIN WINDOW CLASS
# =============================================================================


class MainWindow(QMainWindow):
    """Top-level window assembling the Processing, Visualization, Modeling, and Statistics tabs."""

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self) -> None:
        super().__init__()
        self.status_manager = StatusManager()
        self.processing_tab = None
        self.visualization_tab = None
        self.modeling_tab = None
        self.statistics_tab = None
        self._tab_containers: list[_LazyTabContainer] = []
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # UI BUILDING
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build all UI components for the main window."""
        self._setup_window()
        self._create_status_bar()
        self._create_tabs()
        self._finalize_window()

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect all signals and establish communication between components."""
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._ensure_tab_loaded(0)

    # ------------------------------------------------------------------------
    # WINDOW SETUP
    # ------------------------------------------------------------------------
    def _setup_window(self) -> None:
        """Configure basic window properties."""
        self.setWindowTitle("PyAMA-Pro")
        self.resize(1600, 800)

    # ------------------------------------------------------------------------
    # STATUS BAR SETUP
    # ------------------------------------------------------------------------
    def _create_status_bar(self) -> None:
        """Create and configure the status bar."""
        self.status_bar = StatusBar(self)
        self.setStatusBar(self.status_bar)

        # Connect status manager signals to status bar
        self.status_manager.status_message.connect(self._on_status_message)
        self.status_manager.status_cleared.connect(self._on_status_cleared)

    # ------------------------------------------------------------------------
    # TAB CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_tabs(self) -> None:
        """Kept for compatibility with the older eager-tab layout."""
        return None

    # ------------------------------------------------------------------------
    # TAB CREATION
    # ------------------------------------------------------------------------
    def _create_tabs(self) -> None:
        """Create the tab widget and individual tabs."""
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setMovable(False)
        self.tabs.setTabsClosable(False)
        self.tabs.setDocumentMode(True)

        self._tab_containers = []
        for _attr_name, label, _module_path, _class_name in _TAB_SPECS:
            container = _LazyTabContainer(label, self)
            self._tab_containers.append(container)
            self.tabs.addTab(container, label)

    def _ensure_tab_loaded(self, index: int) -> QWidget | None:
        """Instantiate a tab the first time it is shown or requested."""
        if index < 0 or index >= len(self._tab_containers):
            return None

        container = self._tab_containers[index]
        if container.loaded_widget is not None:
            return container.loaded_widget

        attr_name, label, module_path, class_name = _TAB_SPECS[index]
        logger.debug("Lazy-loading tab '%s' from %s.%s", label, module_path, class_name)
        module = import_module(module_path)
        tab_class = getattr(module, class_name)
        widget = tab_class(self)
        container.set_loaded_widget(widget)
        setattr(self, attr_name, widget)
        self._wire_tab(widget)
        return widget

    def _wire_tab(self, widget: QWidget) -> None:
        """Attach shared signals and services to a lazily-loaded tab."""
        if hasattr(widget, "processing_started"):
            widget.processing_started.connect(self._on_processing_started)
        if hasattr(widget, "processing_finished"):
            widget.processing_finished.connect(self._on_processing_finished)
        if hasattr(widget, "set_status_manager"):
            widget.set_status_manager(self.status_manager)

    @Slot()
    def _on_status_message(self, message: str) -> None:
        """Handle status message display."""
        self.status_bar.show_status_message(message)

    @Slot()
    def _on_status_cleared(self) -> None:
        """Handle status clearing."""
        self.status_bar.clear_status()

    @Slot(int)
    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change events."""
        self._ensure_tab_loaded(index)
        tab_name = self.tabs.tabText(index)
        logger.debug(
            "UI Event: Switched to tab '%s' (index=%d, total_tabs=%d)",
            tab_name,
            index,
            self.tabs.count(),
        )

    @Slot()
    def _on_processing_started(self) -> None:
        """Disable tab switching during processing."""
        logger.debug(
            "Processing started from tab '%s'; disabling tab switching",
            self.tabs.tabText(self.tabs.currentIndex()),
        )
        self.tabs.tabBar().setEnabled(False)  # Only disable tab bar, not content

    @Slot()
    def _on_processing_finished(self) -> None:
        """Re-enable tab switching when processing finishes."""
        logger.debug(
            "Processing finished; re-enabling tab switching for %d tabs",
            self.tabs.count(),
        )
        self.tabs.tabBar().setEnabled(True)  # Re-enable tab bar only

    # ------------------------------------------------------------------------
    # WINDOW FINALIZATION
    # ------------------------------------------------------------------------
    def _finalize_window(self) -> None:
        """Add tabs to window and complete setup."""
        self.setCentralWidget(self.tabs)
