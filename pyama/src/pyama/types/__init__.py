"""Consumer-facing type definitions for the pyama library."""

from pyama.types.io import (
    MicroscopyMetadata,
    PositionArtifacts,
    ProcessingResults,
)
from pyama.types.modeling import (
    FittingResult,
    ModelParameter,
    ParameterPreset,
)
from pyama.types.processing import (
    Channels,
    MergeSample,
    MergeSamplePayload,
    ProcessingConfig,
    ProcessingParams,
    SamplesFilePayload,
)
from pyama.types.rpc import (
    RpcArrayHandle,
    RpcError,
    RpcFileHandle,
    RpcJsonHandle,
    RpcTableHandle,
)
from pyama.types.statistics import SamplePair, StatisticsRequest
from pyama.types.tasks import (
    FrameProgressPayload,
    MergeTaskRequest,
    ModelFitTaskResultHandle,
    ModelFitTaskRequest,
    ProcessingTaskRequest,
    ProgressPayload,
    StatisticsTaskResultHandle,
    StatisticsTaskRequest,
    TaskKind,
    TaskProgress,
    TaskRecord,
    TaskStatus,
)
from pyama.types.visualization import CachedStack, RoiOverlay

__all__ = [
    "CachedStack",
    "Channels",
    "FittingResult",
    "FrameProgressPayload",
    "MergeSample",
    "MergeSamplePayload",
    "MergeTaskRequest",
    "MicroscopyMetadata",
    "ModelFitTaskRequest",
    "ModelFitTaskResultHandle",
    "ModelParameter",
    "ParameterPreset",
    "PositionArtifacts",
    "ProcessingConfig",
    "ProcessingParams",
    "ProcessingResults",
    "ProcessingTaskRequest",
    "ProgressPayload",
    "RpcArrayHandle",
    "RpcError",
    "RpcFileHandle",
    "RpcJsonHandle",
    "RpcTableHandle",
    "RoiOverlay",
    "SamplePair",
    "SamplesFilePayload",
    "StatisticsRequest",
    "StatisticsTaskResultHandle",
    "StatisticsTaskRequest",
    "TaskKind",
    "TaskProgress",
    "TaskRecord",
    "TaskStatus",
]
