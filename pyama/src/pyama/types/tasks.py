"""Consumer-facing task models and request payloads."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal, TypedDict

from pyama.types.io import MicroscopyMetadata
from pyama.types.processing import MergeSample, ProcessingConfig
from pyama.types.rpc import RpcTableHandle
from pyama.types.statistics import StatisticsRequest


class TaskKind(str, Enum):
    PROCESSING = "processing"
    MERGE = "merge"
    MODEL_FIT = "model_fit"
    STATISTICS = "statistics"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProgressPayload(TypedDict, total=False):
    step: str
    message: str
    progress: int | None
    current: int | None
    total: int | None
    event: Literal["frame"]
    position: int
    channel: int
    t: int
    T: int
    worker_id: int
    file: str
    mode: str
    sample: str
    source_path: str
    cached_path: str
    step_current: int
    step_total: int
    overall_current: int
    overall_total: int
    overall_percent: int | None


class FrameProgressPayload(ProgressPayload, total=False):
    event: Literal["frame"]
    position: int
    channel: int
    t: int
    T: int
    worker_id: int


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
    config: ProcessingConfig
    output_dir: Path


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


@dataclass(frozen=True, slots=True)
class ModelFitTaskResultHandle:
    results_table: RpcTableHandle | None = None
    saved_csv_path: Path | None = None


@dataclass(frozen=True, slots=True)
class StatisticsTaskResultHandle:
    results_table: RpcTableHandle
    trace_tables: dict[str, RpcTableHandle]
    output_path: Path

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
    "FrameProgressPayload",
    "MergeTaskRequest",
    "ModelFitTaskResultHandle",
    "ModelFitTaskRequest",
    "ProcessingTaskRequest",
    "ProgressPayload",
    "StatisticsTaskResultHandle",
    "StatisticsTaskRequest",
    "TaskKind",
    "TaskProgress",
    "TaskRecord",
    "TaskStatus",
]
