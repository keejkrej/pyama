"""Processing tab embedding configuration and merge panels."""

from PySide6.QtWidgets import QHBoxLayout, QWidget

from .merge_view import MergeView
from .workflow_view import WorkflowView


class ProcessingView(QWidget):
    """Embeddable processing page providing workflow and merge tools."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.build()
        self.bind()

    def build(self) -> None:
        layout = QHBoxLayout(self)

        self.workflow_view = WorkflowView(self)
        self.merge_view = MergeView(self)

        layout.addWidget(self.workflow_view, 2)
        layout.addWidget(self.merge_view, 1)

    def bind(self) -> None:
        """No external connections inside the view; controllers handle wiring."""
        return


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setCentralWidget(ProcessingView())
    window.show()
    sys.exit(app.exec())
