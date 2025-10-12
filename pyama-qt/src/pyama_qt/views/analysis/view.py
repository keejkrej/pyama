"""Analysis tab composed of data, fitting, and results panels."""

from PySide6.QtWidgets import QHBoxLayout, QWidget

from .data_view import DataView
from .fitting_view import FittingView
from .results_view import ResultsView


class AnalysisView(QWidget):
    """Embeddable analysis page comprising data, fitting, and results panels."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.build()
        self.bind()

    def build(self) -> None:
        layout = QHBoxLayout(self)

        self.data_panel = DataView(self)
        self.fitting_panel = FittingView(self)
        self.results_panel = ResultsView(self)

        layout.addWidget(self.data_panel, 1)
        layout.addWidget(self.fitting_panel, 1)
        layout.addWidget(self.results_panel, 1)

    def bind(self) -> None:
        """Views expose only local signal connections; controllers attach externally."""
        # Panels manage their internal widget wiring; no external connections here.
        return


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setCentralWidget(AnalysisView())
    window.show()
    sys.exit(app.exec())
