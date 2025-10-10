"""Visualization page composed of project, image, and trace panels."""

from PySide6.QtWidgets import QHBoxLayout, QStatusBar, QWidget

from .image_panel import ImagePanel
from .project_panel import ProjectPanel
from .trace_panel import TracePanel


class VisualizationPage(QWidget):
    """Embeddable visualization page comprising project, image, and trace panels."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.build()
        self.bind()

    def build(self) -> None:
        self._status_bar = QStatusBar(self)
        layout = QHBoxLayout(self)

        self.project_panel = ProjectPanel(self)
        self.image_panel = ImagePanel(self)
        self.trace_panel = TracePanel(self)

        layout.addWidget(self.project_panel, 1)
        layout.addWidget(self.image_panel, 1)
        layout.addWidget(self.trace_panel, 1)
        layout.addWidget(self._status_bar)

    def bind(self) -> None:
        """No wiring; controller attaches all external signals."""
        return

    @property
    def status_bar(self) -> QStatusBar:
        return self._status_bar
