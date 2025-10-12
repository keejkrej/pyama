"""Primary application window hosting the major PyAMA views."""

from PySide6.QtWidgets import QMainWindow, QTabWidget

from pyama_qt.controllers.analysis import AnalysisController
from pyama_qt.controllers.processing import ProcessingController
from pyama_qt.controllers.visualization import VisualizationController
from pyama_qt.models.analysis import AnalysisModel
from pyama_qt.models.processing import ProcessingModel
from pyama_qt.models.visualization import VisualizationModel
from pyama_qt.views.analysis import AnalysisView
from pyama_qt.views.processing import WorkflowView
from pyama_qt.views.visualization import VisualizationView


class MainWindow(QMainWindow):
    """Top-level window assembling the Processing, Analysis, and Visualization tabs."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PyAMA-Qt")
        self.resize(1600, 640)

        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.TabPosition.North)
        tabs.setMovable(False)
        tabs.setTabsClosable(False)
        tabs.setDocumentMode(True)

        # Create models
        self.analysis_model = AnalysisModel()
        self.processing_model = ProcessingModel()
        self.visualization_model = VisualizationModel()

        # Create views
        self.processing_page = WorkflowView(self)
        self.analysis_page = AnalysisView(self)
        self.visualization_page = VisualizationView(self)

        # Create controllers with injected models
        self.processing_controller = ProcessingController(
            self.processing_page, self.processing_model
        )
        self.analysis_controller = AnalysisController(
            self.analysis_page, self.analysis_model
        )
        self.visualization_controller = VisualizationController(
            self.visualization_page, self.visualization_model
        )

        tabs.addTab(self.processing_page, "Processing")
        tabs.addTab(self.analysis_page, "Analysis")
        tabs.addTab(self.visualization_page, "Visualization")

        self.setCentralWidget(tabs)
