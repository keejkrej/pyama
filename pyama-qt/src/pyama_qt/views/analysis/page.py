"""Analysis tab composed of data, fitting, and results panels."""

from PySide6.QtWidgets import QHBoxLayout, QStatusBar, QWidget

from .data_panel import AnalysisDataPanel
from .fitting_panel import AnalysisFittingPanel
from .results_panel import AnalysisResultsPanel


class AnalysisPage(QWidget):
    """Embeddable analysis page comprising data, fitting, and results panels."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.build()
        self.bind()

    def build(self) -> None:
        self._status_bar = QStatusBar(self)
        layout = QHBoxLayout(self)

        self.data_panel = AnalysisDataPanel(self)
        self.fitting_panel = AnalysisFittingPanel(self)
        self.results_panel = AnalysisResultsPanel(self)

        layout.addWidget(self.data_panel, 1)
        layout.addWidget(self.fitting_panel, 1)
        layout.addWidget(self.results_panel, 1)
        layout.addWidget(self._status_bar)

    def bind(self) -> None:
        """Views expose only local signal connections; controllers attach externally."""
        # Panels manage their internal widget wiring; no external connections here.
        return

    @property
    def status_bar(self) -> QStatusBar:
        """Expose the status bar so controllers can manage status updates."""
        return self._status_bar
