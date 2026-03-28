"""Welcome tab for the guided PyAMA workflow."""

from typing import Callable

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyama_gui.app_view_model import AppViewModel

type ActionCallback = Callable[[], None]


class WelcomeView(QWidget):
    """Guided landing tab for the current analysis workflow."""

    def __init__(
        self,
        app_view_model: AppViewModel,
        *,
        set_workspace: ActionCallback,
        set_microscopy: ActionCallback,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_view_model = app_view_model
        self._set_workspace = set_workspace
        self._set_microscopy = set_microscopy
        self._build_ui()
        self._connect_signals()

    @property
    def workspace_button(self) -> QPushButton:
        return self._workspace_button

    @property
    def microscopy_button(self) -> QPushButton:
        return self._microscopy_button

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        title = QLabel("Welcome to PyAMA")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(title)

        intro = QLabel(
            "Follow the workflow in order: Alignment first, then Processing, "
            "then Statistics. Modeling and Visualization are optional."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        steps = QFrame(self)
        steps_layout = QVBoxLayout(steps)
        steps_layout.setContentsMargins(20, 20, 20, 20)
        steps_layout.setSpacing(12)
        for step in (
            "1. Set a workspace folder for results.",
            "2. Choose the microscopy file you want to analyze.",
            "3. Go to Alignment and save bbox CSVs for the positions you need.",
            "4. Run Processing to generate extracted traces.",
            "5. Run Statistics on the processed outputs.",
            "6. Use Modeling or Visualization only if you need them.",
        ):
            label = QLabel(step)
            label.setWordWrap(True)
            steps_layout.addWidget(label)
        layout.addWidget(steps)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        self._workspace_button = QPushButton("Set Workspace...")
        self._microscopy_button = QPushButton("Set Microscopy...")
        actions.addWidget(self._workspace_button)
        actions.addWidget(self._microscopy_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(1)

    def _connect_signals(self) -> None:
        self._workspace_button.clicked.connect(self._on_set_workspace)
        self._microscopy_button.clicked.connect(self._on_set_microscopy)

    @Slot()
    def _on_set_workspace(self) -> None:
        self._set_workspace()

    @Slot()
    def _on_set_microscopy(self) -> None:
        self._set_microscopy()
