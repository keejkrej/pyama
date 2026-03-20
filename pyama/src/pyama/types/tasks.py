"""Consumer-facing task models and request payloads."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pyama.io.microscopy import MicroscopyMetadata
from pyama.types.pipeline import ProcessingConfig
from pyama.types.processing import MergeSample
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


@dataclass(frozen=True, slots=True)
class TaskProgress:
    task_id: str
    kind: TaskKind
    step: str
    current: int | None = None
    total: int | None = None
    percent: int | None = None
    message: str = ""
    details: Mapping[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ProcessingTaskRequest:
    metadata: MicroscopyMetadata
    config: ProcessingConfig | None = None
    output_dir: Path | None = None
    context: Any = None
    fov_start: int | None = None
    fov_end: int | None = None
    n_workers: int | None = None


@dataclass(slots=True)
class MergeTaskRequest:
    samples: list[MergeSample]
    input_dir: Path | None = None
    output_dir: Path | None = None
    processing_results_dir: Path | None = None


@dataclass(slots=True)
class ModelFitTaskRequest:
    csv_file: Path
    model_type: str
    frame_interval_minutes: float = 10.0
    model_params: dict[str, float] | None = None
    model_bounds: dict[str, tuple[float, float]] | None = None


StatisticsTaskRequest = StatisticsRequest


@dataclass(slots=True)
class VisualizationTaskRequest:
    source_path: Path
    channel_id: str
    cache_root: Path | None = None
    force_rebuild: bool = False


@dataclass(frozen=True, slots=True)
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
]
