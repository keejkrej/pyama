"""Workflow model for processing configuration."""

import logging
from pathlib import Path
from typing import List
from dataclasses import dataclass, field

from pyama_core.io import MicroscopyMetadata

from PySide6.QtCore import QObject, Signal, Property

logger = logging.getLogger(__name__)


@dataclass
class ChannelSelection:
    phase: int | None = None
    fluorescence: list[int] = field(default_factory=list)


@dataclass
class Parameters:
    fov_start: int
    fov_end: int
    batch_size: int
    n_workers: int


class WorkflowModel(QObject):
    """Model for workflow configuration: paths, metadata, channels, parameters."""

    microscopyPathChanged = Signal(Path)
    metadataChanged = Signal(object)  # MicroscopyMetadata
    outputDirChanged = Signal(Path)
    phaseChanged = Signal(int)
    fluorescenceChanged = Signal(list)
    fovStartChanged = Signal(int)
    fovEndChanged = Signal(int)
    batchSizeChanged = Signal(int)
    nWorkersChanged = Signal(int)
    isProcessingChanged = Signal(bool)
    statusMessageChanged = Signal(str)
    errorMessageChanged = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._microscopy_path: Path | None = None
        self._metadata: MicroscopyMetadata | None = None
        self._output_dir: Path | None = None
        self._phase: int | None = None
        self._fluorescence: List[int] = []
        self._fov_start: int = -1
        self._fov_end: int = -1
        self._batch_size: int = 2
        self._n_workers: int = 2
        self._is_processing: bool = False
        self._status_message: str = ""
        self._error_message: str = ""

    @Property(
        object,
        notify=microscopyPathChanged,  # type: ignore[arg-type]
    )
    def microscopyPath(self) -> Path | None:
        return self._microscopy_path

    @microscopyPath.setter  # type: ignore[arg-type]
    def microscopyPath(self, path: Path | None) -> None:
        if self._microscopy_path == path:
            return
        self._microscopy_path = path
        self.microscopyPathChanged.emit(path)

    @Property(
        object,
        notify=metadataChanged,  # type: ignore[arg-type]
    )
    def metadata(self) -> MicroscopyMetadata | None:
        return self._metadata

    @metadata.setter  # type: ignore[arg-type]
    def metadata(self, metadata: MicroscopyMetadata | None) -> None:
        """Set metadata from microscopy loading."""
        if self._metadata is metadata:
            return
        self._metadata = metadata
        self.metadataChanged.emit(metadata)

    def load_microscopy(self, path: Path) -> None:
        """Load microscopy metadata from path."""
        logger.info("Loading microscopy from %s", path)
        try:
            # Initialize with empty metadata which will be populated by worker
            self.microscopyPath = path
            self.metadata = None  # Clear any previous metadata
        except Exception:
            logger.exception("Failed to load microscopy")
            raise

    @Property(
        object,
        notify=outputDirChanged,  # type: ignore[arg-type]
    )
    def outputDir(self) -> Path | None:
        return self._output_dir

    @outputDir.setter  # type: ignore[arg-type]
    def outputDir(self, path: Path | None) -> None:
        if self._output_dir == path:
            return
        self._output_dir = path
        self.outputDirChanged.emit(path)

    @Property(
        int,
        notify=phaseChanged,  # type: ignore[arg-type]
    )
    def phase(self) -> int | None:
        return self._phase

    @phase.setter  # type: ignore[arg-type]
    def phase(self, phase: int | None) -> None:
        if self._phase == phase:
            return
        self._phase = phase
        self.phaseChanged.emit(phase)

    @Property(
        object,
        notify=fluorescenceChanged,  # type: ignore[arg-type]
    )
    def fluorescence(self) -> List[int] | None:
        return self._fluorescence if self._fluorescence else None

    @fluorescence.setter  # type: ignore[arg-type]
    def fluorescence(self, fluorescence: List[int] | None) -> None:
        if fluorescence is None:
            fluorescence = []
        if self._fluorescence == fluorescence:
            return
        self._fluorescence = fluorescence
        self.fluorescenceChanged.emit(self._fluorescence)

    def channels(self) -> ChannelSelection:
        return ChannelSelection(phase=self._phase, fluorescence=self._fluorescence)

    @Property(
        int,
        notify=fovStartChanged,  # type: ignore[arg-type]
    )
    def fovStart(self) -> int:
        return self._fov_start

    @fovStart.setter  # type: ignore[arg-type]
    def fovStart(self, fov_start: int) -> None:
        if self._fov_start == fov_start:
            return
        self._fov_start = fov_start
        self.fovStartChanged.emit(fov_start)

    @Property(
        int,
        notify=fovEndChanged,  # type: ignore[arg-type]
    )
    def fovEnd(self) -> int:
        return self._fov_end

    @fovEnd.setter  # type: ignore[arg-type]
    def fovEnd(self, fov_end: int) -> None:
        if self._fov_end == fov_end:
            return
        self._fov_end = fov_end
        self.fovEndChanged.emit(fov_end)

    @Property(
        int,
        notify=batchSizeChanged,  # type: ignore[arg-type]
    )
    def batchSize(self) -> int:
        return self._batch_size

    @batchSize.setter  # type: ignore[arg-type]
    def batchSize(self, batch_size: int) -> None:
        if self._batch_size == batch_size:
            return
        self._batch_size = batch_size
        self.batchSizeChanged.emit(batch_size)

    @Property(
        int,
        notify=nWorkersChanged,  # type: ignore[arg-type]
    )
    def nWorkers(self) -> int:
        return self._n_workers

    @nWorkers.setter  # type: ignore[arg-type]
    def nWorkers(self, n_workers: int) -> None:
        if self._n_workers == n_workers:
            return
        self._n_workers = n_workers
        self.nWorkersChanged.emit(n_workers)

    def update_channels(
        self, phase: int | None = None, fluorescence: List[int] | None = None
    ) -> None:
        """Update channel selection."""
        if phase is not None:
            self.phase = phase
        if fluorescence is not None:
            self.fluorescence = fluorescence

    def parameters(self) -> Parameters:
        """Return processing parameters as a structured object."""
        return Parameters(
            fov_start=self._fov_start,
            fov_end=self._fov_end,
            batch_size=self._batch_size,
            n_workers=self._n_workers,
        )

    def update_parameters(
        self,
        fov_start: int | None = None,
        fov_end: int | None = None,
        batch_size: int | None = None,
        n_workers: int | None = None,
    ) -> None:
        """Update processing parameters."""
        if fov_start is not None:
            self.fovStart = fov_start
        if fov_end is not None:
            self.fovEnd = fov_end
        if batch_size is not None:
            self.batchSize = batch_size
        if n_workers is not None:
            self.nWorkers = n_workers

    @Property(
        bool,
        notify=isProcessingChanged,  # type: ignore[arg-type]
    )
    def isProcessing(self) -> bool:
        return self._is_processing

    @isProcessing.setter  # type: ignore[arg-type]
    def isProcessing(self, is_processing: bool) -> None:
        if self._is_processing == is_processing:
            return
        self._is_processing = is_processing
        self.isProcessingChanged.emit(is_processing)

    @Property(
        str,
        notify=statusMessageChanged,  # type: ignore[arg-type]
    )
    def statusMessage(self) -> str:
        return self._status_message

    @statusMessage.setter  # type: ignore[arg-type]
    def statusMessage(self, message: str) -> None:
        if self._status_message == message:
            return
        self._status_message = message
        self.statusMessageChanged.emit(message)

    @Property(
        str,
        notify=errorMessageChanged,  # type: ignore[arg-type]
    )
    def errorMessage(self) -> str:
        return self._error_message

    @errorMessage.setter  # type: ignore[arg-type]
    def errorMessage(self, message: str) -> None:
        if self._error_message == message:
            return
        self._error_message = message
        self.errorMessageChanged.emit(message)
