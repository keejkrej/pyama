"""Visualization page composed of project, image, and trace panels."""

from PySide6.QtWidgets import QHBoxLayout, QWidget

from .image_view import ImageView
from .project_view import ProjectView
from .trace_view import TraceView


class VisualizationView(QWidget):
    """Embeddable visualization page comprising project, image, and trace panels."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.build()
        self.bind()

    def build(self) -> None:
        layout = QHBoxLayout(self)

        self.project_view = ProjectView(self)
        self.image_view = ImageView(self)
        self.trace_view = TraceView(self)

        layout.addWidget(self.project_view, 1)
        layout.addWidget(self.image_view, 1)
        layout.addWidget(self.trace_view, 1)

    def bind(self) -> None:
        """No wiring; controller attaches all external signals."""
        return


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setCentralWidget(VisualizationView())
    window.show()
    sys.exit(app.exec())
