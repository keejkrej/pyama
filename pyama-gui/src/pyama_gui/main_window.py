"""Primary application window for the consolidated MVVM Qt shell."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStatusBar,
    QTabWidget,
    QWidget,
)

from pyama_gui.app_view_model import AppViewModel
from pyama_gui.constants import DEFAULT_DIR

logger = logging.getLogger(__name__)


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
        self._workspace_label = QLabel("Workspace: Not set")
        self.addPermanentWidget(self._workspace_label)

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

    def show_workspace(self, path: Path | None) -> None:
        if path is None:
            self._workspace_label.setText("Workspace: Not set")
        else:
            self._workspace_label.setText(f"Workspace: {path}")


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
        self.app_view_model = AppViewModel(self)
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
        self._create_menu_bar()
        self._create_status_bar()
        self._create_tabs()
        self._finalize_window()

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect all signals and establish communication between components."""
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._set_workspace_action.triggered.connect(self._on_set_workspace_folder)
        self.app_view_model.status_changed.connect(self._on_status_message)
        self.app_view_model.workspace_changed.connect(self._on_workspace_changed)
        self.app_view_model.busy_changed.connect(self._on_busy_changed)
        self._ensure_tab_loaded(0)

    # ------------------------------------------------------------------------
    # WINDOW SETUP
    # ------------------------------------------------------------------------
    def _setup_window(self) -> None:
        """Configure basic window properties."""
        self.setWindowTitle("PyAMA")
        self.resize(1600, 800)

    # ------------------------------------------------------------------------
    # STATUS BAR SETUP
    # ------------------------------------------------------------------------
    def _create_status_bar(self) -> None:
        """Create and configure the status bar."""
        self.status_bar = StatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_bar.show_workspace(self.app_view_model.workspace_dir)

    def _create_menu_bar(self) -> None:
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")

        self._set_workspace_action = QAction("Set Workspace Folder", self)
        file_menu.addAction(self._set_workspace_action)

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
        for _attr_name, label, _factory in self._tab_specs():
            container = _LazyTabContainer(label, self)
            self._tab_containers.append(container)
            self.tabs.addTab(container, label)

    def _tab_specs(self) -> tuple[tuple[str, str, object], ...]:
        return (
            ("processing_tab", "Processing", self._create_processing_tab),
            ("statistics_tab", "Statistics", self._create_statistics_tab),
            ("modeling_tab", "Modeling", self._create_modeling_tab),
            ("visualization_tab", "Visualization", self._create_visualization_tab),
        )

    def _create_processing_tab(self) -> QWidget:
        from pyama_gui.processing.view import ProcessingView

        return ProcessingView(self.app_view_model, self)

    def _create_statistics_tab(self) -> QWidget:
        from pyama_gui.statistics.view import StatisticsView

        return StatisticsView(self.app_view_model, self)

    def _create_modeling_tab(self) -> QWidget:
        from pyama_gui.modeling.view import ModelingView

        return ModelingView(self.app_view_model, self)

    def _create_visualization_tab(self) -> QWidget:
        from pyama_gui.visualization.view import VisualizationView

        return VisualizationView(self.app_view_model, self)

    def _ensure_tab_loaded(self, index: int) -> QWidget | None:
        """Instantiate a tab the first time it is shown or requested."""
        if index < 0 or index >= len(self._tab_containers):
            return None

        container = self._tab_containers[index]
        if container.loaded_widget is not None:
            return container.loaded_widget

        attr_name, label, factory = self._tab_specs()[index]
        logger.debug("Lazy-loading tab '%s'", label)
        widget = factory()
        container.set_loaded_widget(widget)
        setattr(self, attr_name, widget)
        return widget

    @Slot(str)
    def _on_status_message(self, message: str) -> None:
        """Handle status message display."""
        self.status_bar.show_status_message(message)

    @Slot(object)
    def _on_workspace_changed(self, path: Path | None) -> None:
        self.status_bar.show_workspace(path)

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
    def _on_set_workspace_folder(self) -> None:
        start_dir = str(self.app_view_model.workspace_dir or DEFAULT_DIR)
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Workspace Folder",
            start_dir,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not path:
            return

        workspace_dir = Path(path)
        logger.info("Workspace folder set to %s", workspace_dir)
        self.app_view_model.set_workspace_dir(workspace_dir)
        self.app_view_model.set_status_message(
            f"Workspace folder set to {workspace_dir}"
        )

    @Slot(bool)
    def _on_busy_changed(self, is_busy: bool) -> None:
        self.tabs.tabBar().setEnabled(not is_busy)

    # ------------------------------------------------------------------------
    # WINDOW FINALIZATION
    # ------------------------------------------------------------------------
    def _finalize_window(self) -> None:
        """Add tabs to window and complete setup."""
        self.setCentralWidget(self.tabs)
