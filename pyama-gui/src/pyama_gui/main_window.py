"""Primary application window for the consolidated MVVM Qt shell."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMenu,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pyama_gui.app_view_model import AppViewModel
from pyama_gui.services import (
    FileDialogService,
    PathRevealService,
    QtPathRevealService,
)

logger = logging.getLogger(__name__)

type TabFactory = Callable[[], QWidget]
type TabSpec = tuple[str, str, TabFactory]
type PathEntry = tuple[str, Path | None]


def _display_path_name(path: Path | None) -> str:
    """Return a short display label for a path."""
    if path is None:
        return "Not set"
    return path.stem or path.name or str(path)


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


class _PathsMenu(QMenu):
    """Anchored menu listing workspace-related paths."""

    def __init__(
        self,
        *,
        path_reveal_service: PathRevealService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._path_reveal_service = path_reveal_service
        self._paths_by_label: dict[str, Path | None] = {}
        self._entry_actions = {}
        self._build_menu()

    def _build_menu(self) -> None:
        self.setTitle("Project Paths")
        for label in ("Workspace", "Microscopy"):
            action = self.addAction("")
            action.triggered.connect(
                lambda _checked=False, entry_label=label: self._on_entry_triggered(
                    entry_label
                )
            )
            self._entry_actions[label] = action

    def show_for_button(
        self, anchor_button: QPushButton, entries: tuple[PathEntry, ...]
    ) -> None:
        self.set_entries(entries)
        global_bottom_left = anchor_button.mapToGlobal(anchor_button.rect().bottomLeft())
        self.popup(global_bottom_left)

    def set_entries(self, entries: tuple[PathEntry, ...]) -> None:
        self._paths_by_label = {}
        for label, path in entries:
            action = self._entry_actions[label]
            self._paths_by_label[label] = path
            if path is None:
                action.setText(f"{label}: Not set")
                action.setToolTip("")
                action.setEnabled(False)
                continue

            action.setText(f"{label}: {_display_path_name(path)}")
            action.setToolTip("")
            action.setEnabled(True)

    def entry_text(self, label: str) -> str:
        text = self._entry_actions[label].text()
        prefix = f"{label}: "
        if text.startswith(prefix):
            return text[len(prefix) :]
        return text

    def entry_action(self, label: str):
        return self._entry_actions[label]

    @Slot(str)
    def _on_entry_triggered(self, label: str) -> None:
        path = self._paths_by_label.get(label)
        if path is None:
            return
        self._path_reveal_service.reveal_path(path)


# =============================================================================
# STATUS BAR
# =============================================================================


class StatusBar(QStatusBar):
    """Status bar for status messages plus a popup path browser."""

    def __init__(
        self,
        *,
        path_reveal_service: PathRevealService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._path_reveal_service = path_reveal_service
        self._workspace_path: Path | None = None
        self._microscopy_path: Path | None = None
        self._paths_menu: _PathsMenu | None = None
        self._build_ui()

    @property
    def paths_button(self) -> QPushButton:
        return self._paths_button

    @property
    def paths_menu(self) -> _PathsMenu:
        return self._paths_menu

    def path_entry_text(self, label: str) -> str:
        return self._paths_menu.entry_text(label)

    def _build_ui(self) -> None:
        self.showMessage("Ready")
        self._paths_menu = _PathsMenu(
            path_reveal_service=self._path_reveal_service, parent=self.window()
        )
        self._paths_button = QPushButton("Info", self)
        self._paths_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._paths_button.clicked.connect(self._toggle_paths_menu)
        self.addPermanentWidget(self._paths_button)
        self._refresh_paths_menu()

    def show_status_message(self, message: str) -> None:
        self.showMessage(message)

    def clear_status(self) -> None:
        self.showMessage("Ready")

    def show_workspace(self, path: Path | None) -> None:
        self._workspace_path = path
        self._refresh_paths_menu()

    def show_microscopy(self, path: Path | None) -> None:
        self._microscopy_path = path
        self._refresh_paths_menu()

    def _path_entries(self) -> tuple[PathEntry, ...]:
        return (
            ("Workspace", self._workspace_path),
            ("Microscopy", self._microscopy_path),
        )

    def _refresh_paths_menu(self) -> None:
        if self._paths_menu is None:
            return
        self._paths_menu.set_entries(self._path_entries())

    @Slot()
    def _toggle_paths_menu(self) -> None:
        if self._paths_menu.isVisible():
            self._paths_menu.hide()
            return
        self._paths_menu.show_for_button(self._paths_button, self._path_entries())


# =============================================================================
# MAIN WINDOW CLASS
# =============================================================================


class MainWindow(QMainWindow):
    """Top-level window assembling the workflow and optional analysis tabs."""

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(
        self,
        *,
        dialog_service: FileDialogService | None = None,
        path_reveal_service: PathRevealService | None = None,
    ) -> None:
        super().__init__()
        self.app_view_model = AppViewModel(self, dialog_service=dialog_service)
        self.path_reveal_service = path_reveal_service or QtPathRevealService()
        self.welcome_tab = None
        self.processing_tab = None
        self.bboxes_tab = None
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
        self.app_view_model.status_changed.connect(self._on_status_message)
        self.app_view_model.workspace_changed.connect(self._on_workspace_changed)
        self.app_view_model.microscopy_changed.connect(self._on_microscopy_changed)
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
        self.status_bar = StatusBar(
            path_reveal_service=self.path_reveal_service, parent=self
        )
        self.status_bar.show_workspace(self.app_view_model.workspace_dir)
        self.status_bar.show_microscopy(self.app_view_model.microscopy_path)
        self.setStatusBar(self.status_bar)

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

    def _tab_specs(self) -> tuple[TabSpec, ...]:
        return (
            ("welcome_tab", "Welcome", self._create_welcome_tab),
            ("bboxes_tab", "Alignment", self._create_bboxes_tab),
            ("processing_tab", "Processing", self._create_processing_tab),
            ("statistics_tab", "Statistics", self._create_statistics_tab),
            ("modeling_tab", "Modeling", self._create_modeling_tab),
            ("visualization_tab", "Visualization", self._create_visualization_tab),
        )

    def _create_welcome_tab(self) -> QWidget:
        from pyama_gui.apps.welcome.view import WelcomeView

        return WelcomeView(
            self.app_view_model,
            set_workspace=self._on_set_workspace_folder,
            set_microscopy=self._on_set_microscopy_file,
            parent=self,
        )

    def _create_processing_tab(self) -> QWidget:
        from pyama_gui.apps.processing.view import ProcessingView

        return ProcessingView(self.app_view_model, self)

    def _create_statistics_tab(self) -> QWidget:
        from pyama_gui.apps.statistics.view import StatisticsView

        return StatisticsView(self.app_view_model, self)

    def _create_bboxes_tab(self) -> QWidget:
        from pyama_gui.apps.bboxes.view import BBoxesView

        return BBoxesView(self.app_view_model, self)

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
        self.status_bar.show_workspace(path)

    @Slot(object)
    def _on_microscopy_changed(self, path: Path | None) -> None:
        self.status_bar.show_microscopy(path)

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

    @Slot()
    def _on_set_microscopy_file(self) -> None:
        self.app_view_model.select_microscopy()

    @Slot()
    def _on_clear_microscopy_file(self) -> None:
        self.app_view_model.clear_microscopy()

    @Slot()
    def _open_alignment_tab(self) -> None:
        self.tabs.setCurrentIndex(1)

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
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(container)
