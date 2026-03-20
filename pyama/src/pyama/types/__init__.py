"""Consumer-facing type definitions for the pyama library."""

from pyama.types.io import ProcessingResults
from pyama.types.microscopy import MicroscopyMetadata
from pyama.types.modeling import (
    FittingResult,
    ModelParameter,
    ParameterPreset,
)
from pyama.types.pipeline import (
    Channels,
    ProcessingConfig,
    ProcessingParams,
    SegmentationMethod,
    TrackingMethod,
)
from pyama.types.processing import (
    MergeSample,
    MergeSamplePayload,
    Result,
    SamplesFilePayload,
)
from pyama.types.progress_payload import FrameProgressPayload, ProgressPayload
from pyama.types.statistics import SamplePair, StatisticsRequest
from pyama.types.tasks import (
    MergeTaskRequest,
    ModelFitTaskRequest,
    ProcessingTaskRequest,
    StatisticsTaskRequest,
    TaskKind,
    TaskProgress,
    TaskRecord,
    TaskStatus,
    VisualizationTaskRequest,
)

__all__ = [
    "Channels",
    "FittingResult",
    "FrameProgressPayload",
    "MergeSample",
    "MergeSamplePayload",
    "MergeTaskRequest",
    "MicroscopyMetadata",
    "ModelFitTaskRequest",
    "ModelParameter",
    "ParameterPreset",
    "ProcessingConfig",
    "ProcessingParams",
    "ProcessingResults",
    "ProcessingTaskRequest",
    "ProgressPayload",
    "Result",
    "SamplePair",
    "SamplesFilePayload",
    "SegmentationMethod",
    "StatisticsRequest",
    "StatisticsTaskRequest",
    "TaskKind",
    "TaskProgress",
    "TaskRecord",
    "TaskStatus",
    "TrackingMethod",
    "VisualizationTaskRequest",
]
