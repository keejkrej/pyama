"""Model for merge-related state in processing."""

from pathlib import Path
from PySide6.QtCore import QObject, Signal, Property


class MergeModel(QObject):
    """Model for merge functionality state."""

    # Signals for merge paths
    sampleYamlPathChanged = Signal(object)  # Path | None
    processingResultsPathChanged = Signal(object)  # Path | None
    mergeOutputDirChanged = Signal(object)  # Path | None

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        # Private storage for merge paths
        self._sample_yaml_path: Path | None = None
        self._processing_results_path: Path | None = None
        self._merge_output_dir: Path | None = None

    @Property(object, notify=sampleYamlPathChanged)
    def sampleYamlPath(self) -> Path | None:
        return self._sample_yaml_path

    @Property(object, notify=processingResultsPathChanged)
    def processingResultsPath(self) -> Path | None:
        return self._processing_results_path

    @Property(object, notify=mergeOutputDirChanged)
    def mergeOutputDir(self) -> Path | None:
        return self._merge_output_dir

    @sampleYamlPath.setter
    def sampleYamlPath(self, path: Path | None) -> None:
        if self._sample_yaml_path != path:
            self._sample_yaml_path = path
            self.sampleYamlPathChanged.emit(path)

    @processingResultsPath.setter
    def processingResultsPath(self, path: Path | None) -> None:
        if self._processing_results_path != path:
            self._processing_results_path = path
            self.processingResultsPathChanged.emit(path)

    @mergeOutputDir.setter
    def mergeOutputDir(self, path: Path | None) -> None:
        if self._merge_output_dir != path:
            self._merge_output_dir = path
            self.mergeOutputDirChanged.emit(path)
