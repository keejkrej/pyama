"""Consumer-facing task models and request payloads."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pyama.io.microscopy.base import MicroscopyMetadata
from pyama.types.processing import ProcessingContext
from pyama.types.statistics import StatisticsRequest


class TaskKind(str, Enum):
    PROCESSING = "processing"
    MERGE = "merge"
    MODEL_FIT = "model_fit"
    STATISTICS = "statistics"
    VISUALIZATION = "visualization"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class WorkflowProgressEvent:
    worker_id: int
    step: str
    fov: int
    frame_index: int
    frame_total: int
    message: str


@dataclass(slots=True)
class WorkflowStatusEvent:
    completed_fovs: int
    total_fovs: int
    progress_percent: int
    message: str


@dataclass(slots=True)
class TaskProgress:
    task_id: str
    kind: TaskKind
    step: str
    current: int | None = None
    total: int | None = None
    percent: int | None = None
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProcessingTaskRequest:
    metadata: MicroscopyMetadata
    context: ProcessingContext
    fov_start: int
    fov_end: int
    n_workers: int


@dataclass(slots=True)
class MergeTaskRequest:
    samples: list[dict[str, Any]]
    processing_results_dir: Path


@dataclass(slots=True)
class ModelFitTaskRequest:
    csv_file: Path
    model_type: str
    model_params: dict[str, float] | None = None
    model_bounds: dict[str, tuple[float, float]] | None = None


StatisticsTaskRequest = StatisticsRequest


@dataclass(slots=True)
class VisualizationTaskRequest:
    source_path: Path
    channel_id: str
    cache_root: Path | None = None
    force_rebuild: bool = False


@dataclass(slots=True)
class TaskRecord:
    id: str
    kind: TaskKind
    status: TaskStatus
    request: Any
    progress: TaskProgress | None = None
    result: Any = None
    error_message: str | None = None


__all__ = [
    "MergeTaskRequest",
    "ModelFitTaskRequest",
    "ProcessingTaskRequest",
    "StatisticsTaskRequest",
    "TaskKind",
    "TaskProgress",
    "TaskRecord",
    "TaskStatus",
    "VisualizationTaskRequest",
    "WorkflowProgressEvent",
    "WorkflowStatusEvent",
]
