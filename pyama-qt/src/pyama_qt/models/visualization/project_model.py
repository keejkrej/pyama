"""Project model for visualization."""

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from PySide6.QtCore import QObject, Signal

from pyama_core.io.processing_csv import (
    get_dataframe,
)

logger = logging.getLogger(__name__)


class ProjectModel(QObject):
    """Model managing project data and state."""

    projectPathChanged = Signal(object)
    projectDataChanged = Signal(dict)
    availableChannelsChanged = Signal(list)
    statusMessageChanged = Signal(str)
    errorMessageChanged = Signal(str)
    isLoadingChanged = Signal(bool)
    projectLoaded = Signal()
    projectCleared = Signal()
    processingDataChanged = Signal(pd.DataFrame)
    sampleYamlChanged = Signal(Path)
    processingResultsChanged = Signal(Path)

    def __init__(self) -> None:
        super().__init__()
        self._processing_df: pd.DataFrame | None = None
        self._sample_yaml: Path | None = None
        self._processing_results: Path | None = None
        self._project_path: Any | None = None
        self._project_data: dict[str, Any] | None = None
        self._available_channels: list[str] = []
        self._status_message: str = ""
        self._error_message: str = ""
        self._is_loading = False

    def processing_df(self) -> pd.DataFrame | None:
        return self._processing_df

    def sample_yaml(self) -> Path | None:
        return self._sample_yaml

    def processing_results(self) -> Path | None:
        return self._processing_results

    def project_path(self) -> Any | None:
        return self._project_path

    def project_data(self) -> dict[str, Any] | None:
        return self._project_data

    def available_channels(self) -> list[str]:
        return self._available_channels

    def status_message(self) -> str:
        return self._status_message

    def error_message(self) -> str:
        return self._error_message

    def is_loading(self) -> bool:
        return self._is_loading

    def set_project_path(self, path: Any | None) -> None:
        if self._project_path == path:
            return
        self._project_path = path
        self.projectPathChanged.emit(path)

    def set_project_data(self, data: dict[str, Any] | None) -> None:
        if self._project_data == data:
            return
        self._project_data = data
        self.projectDataChanged.emit(data)

    def set_available_channels(self, channels: list[str]) -> None:
        if self._available_channels == channels:
            return
        self._available_channels = channels
        self.availableChannelsChanged.emit(channels)

    def set_status_message(self, message: str) -> None:
        if self._status_message == message:
            return
        self._status_message = message
        self.statusMessageChanged.emit(message)

    def set_error_message(self, message: str) -> None:
        if self._error_message == message:
            return
        self._error_message = message
        self.errorMessageChanged.emit(message)

    def set_is_loading(self, loading: bool) -> None:
        if self._is_loading == loading:
            return
        self._is_loading = loading
        self.isLoadingChanged.emit(loading)

    def load_project(self, sample_yaml: Path, processing_results: Path) -> bool:
        """Load project data from sample YAML and processing results.

        Args:
            sample_yaml: Path to the sample YAML file
            processing_results: Path to the processing results directory

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(
                "Loading project from %s and %s", sample_yaml, processing_results
            )

            # Load processing dataframe
            processing_df = get_dataframe(processing_results)
            if processing_df is None:
                logger.error("Failed to load processing dataframe")
                return False

            # Update model state
            self._sample_yaml = sample_yaml
            self._processing_results = processing_results
            self._processing_df = processing_df

            # Emit signals
            self.sampleYamlChanged.emit(sample_yaml)
            self.processingResultsChanged.emit(processing_results)
            self.processingDataChanged.emit(processing_df)
            self.projectLoaded.emit()

            return True

        except Exception as e:
            logger.error(f"Failed to load project: {str(e)}")
            return False

    def clear_project(self) -> None:
        """Clear all project data."""
        self._processing_df = None
        self._sample_yaml = None
        self._processing_results = None

        self.processingDataChanged.emit(pd.DataFrame())
        self.sampleYamlChanged.emit(None)
        self.processingResultsChanged.emit(None)
        self.projectCleared.emit()
