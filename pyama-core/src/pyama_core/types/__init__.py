"""Type definitions for PyAMA core."""

from pyama_core.types.microscopy import MicroscopyMetadata
from pyama_core.types.processing import (
    ChannelSelection,
    Channels,
    ProcessingParams,
    ProcessingConfig,
    ProcessingBaseResult,
    get_processing_base_fields,
    get_processing_feature_field,
    make_processing_result,
    ExtractionContext,
    Region,
    TileSupport,
    ChannelFeatureConfig,
    FeatureMaps,
)
from pyama_core.types.analysis import (
    EventResult,
    FixedParam,
    FitParam,
    FixedParams,
    FitParams,
    FittingResult,
)
from pyama_core.types.merge import MergeResult, get_merge_fields
from pyama_core.types.api import (
    MicroscopyLoadRequest,
    MicroscopyMetadataSchema,
    metadata_to_schema,
    TaskStatus,
    TaskCreate,
    TaskProgress,
    TaskResult,
    TaskResponse,
    TaskListResponse,
)

__all__ = [
    # Microscopy
    "MicroscopyMetadata",
    # Processing
    "ChannelSelection",
    "Channels",
    "ProcessingParams",
    "ProcessingConfig",
    "ProcessingBaseResult",
    "get_processing_base_fields",
    "get_processing_feature_field",
    "make_processing_result",
    "ExtractionContext",
    "Region",
    "TileSupport",
    "ChannelFeatureConfig",
    "FeatureMaps",
    # Analysis
    "EventResult",
    "FixedParam",
    "FitParam",
    "FixedParams",
    "FitParams",
    "FittingResult",
    # Merge
    "MergeResult",
    "get_merge_fields",
    # API
    "MicroscopyLoadRequest",
    "MicroscopyMetadataSchema",
    "metadata_to_schema",
    "TaskStatus",
    "TaskCreate",
    "TaskProgress",
    "TaskResult",
    "TaskResponse",
    "TaskListResponse",
]
