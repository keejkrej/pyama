"""Primary application window for the consolidated MVVM Qt shell."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pyama_gui.app_view_model import AppViewModel
from pyama_gui.services import FileDialogService

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


class WorkspaceBar(QWidget):
    """Top-level workspace selector shown above the main tab widget."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 0)

        self._title_label = QLabel("Workspace:")
        self._path_label = QLabel("Not set")
        self._change_button = QPushButton("Set Workspace...")

        layout.addWidget(self._title_label)
        layout.addWidget(self._path_label, 1)
        layout.addWidget(self._change_button)

    @property
    def change_button(self) -> QPushButton:
        return self._change_button

    def show_workspace(self, path: Path | None) -> None:
        if path is None:
            self._path_label.setText("Not set")
            self._change_button.setText("Set Workspace...")
            return

        self._path_label.setText(str(path))
        self._change_button.setText("Change...")


# =============================================================================
# MAIN WINDOW CLASS
# =============================================================================


class MainWindow(QMainWindow):
    """Top-level window assembling the Processing, Visualization, Modeling, and Statistics tabs."""

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, *, dialog_service: FileDialogService | None = None) -> None:
        super().__init__()
        self.app_view_model = AppViewModel(self, dialog_service=dialog_service)
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
        self._create_workspace_bar()
        self._create_tabs()
        self._finalize_window()

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect all signals and establish communication between components."""
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.workspace_bar.change_button.clicked.connect(self._on_set_workspace_folder)
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

    def _create_workspace_bar(self) -> None:
        self.workspace_bar = WorkspaceBar(self)
        self.workspace_bar.show_workspace(self.app_view_model.workspace_dir)

    def _create_menu_bar(self) -> None:
        menu_bar = self.menuBar()
        menu_bar.clear()

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
        from pyama_gui.apps.processing.view import ProcessingView

        return ProcessingView(self.app_view_model, self)

    def _create_statistics_tab(self) -> QWidget:
        from pyama_gui.apps.statistics.view import StatisticsView

        return StatisticsView(self.app_view_model, self)

    def _create_modeling_tab(self) -> QWidget:
        from pyama_gui.apps.modeling.view import ModelingView

        return ModelingView(self.app_view_model, self)

    def _create_visualization_tab(self) -> QWidget:
        from pyama_gui.apps.visualization.view import VisualizationView

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
        self.workspace_bar.show_workspace(path)

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
        self.app_view_model.select_workspace()

    def prompt_for_workspace_on_startup(self) -> None:
        """Prompt for a workspace folder when the app starts without one."""
        if self.app_view_model.workspace_dir is not None:
            return

        self.app_view_model.select_workspace()

    @Slot(bool)
    def _on_busy_changed(self, is_busy: bool) -> None:
        self.tabs.tabBar().setEnabled(not is_busy)

    # ------------------------------------------------------------------------
    # WINDOW FINALIZATION
    # ------------------------------------------------------------------------
    def _finalize_window(self) -> None:
        """Add tabs to window and complete setup."""
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.workspace_bar)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(container)
