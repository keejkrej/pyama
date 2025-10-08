"""Consolidated processing model."""

from dataclasses import dataclass
from pathlib import Path
from typing import List
from PySide6.QtCore import QObject

from .config_model import ProcessingConfigModel
from .status_model import WorkflowStatusModel


@dataclass(slots=True)
class WorkflowStartRequest:
    """Request to start processing workflow."""

    microscopy_path: Path
    output_dir: Path
    phase: int | None = None
    fluorescence: List[int] | None = None
    fov_start: int = -1
    fov_end: int = -1
    batch_size: int = 2
    n_workers: int = 2


@dataclass(frozen=True)
class MergeRequest:
    """Typed request for merge operation."""

    sample_yaml: Path
    processing_results: Path
    input_dir: Path
    output_dir: Path


class ProcessingModel(QObject):
    """Consolidated model for processing functionality."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.config_model = ProcessingConfigModel()
        self.status_model = WorkflowStatusModel()
