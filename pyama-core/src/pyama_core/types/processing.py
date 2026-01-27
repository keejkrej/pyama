"""Pydantic models shared across workflow services to avoid circular imports."""

from typing import Any

import numpy as np
from pydantic import BaseModel, Field, create_model, model_validator
from dataclasses import dataclass


class ChannelSelection(BaseModel):
    channel: int
    features: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _accept_list_format(cls, data: Any) -> Any:
        """Accept legacy YAML format: [channel, [features]]."""
        if isinstance(data, (list, tuple)) and len(data) == 2:
            return {"channel": data[0], "features": data[1]}
        return data


class Channels(BaseModel):
    pc: ChannelSelection
    fl: list[ChannelSelection] = Field(default_factory=list)

    def get_pc_channel(self) -> int:
        return self.pc.channel

    def get_pc_features(self) -> list[str]:
        return list(self.pc.features)

    def get_fl_feature_map(self) -> dict[int, list[str]]:
        return {selection.channel: list(selection.features) for selection in self.fl}

    def get_fl_channels(self) -> list[int]:
        return [selection.channel for selection in self.fl]


class ProcessingParams(BaseModel):
    """Typed processing parameters for the pipeline."""

    fovs: str = ""
    batch_size: int = Field(default=2, ge=1)
    n_workers: int = Field(default=2, ge=1)
    background_weight: float = Field(default=1.0, ge=0)
    segmentation_method: str = "logstd"
    tracking_method: str = "iou"
    crop_padding: int = Field(default=5, ge=0)
    mask_margin: int = Field(default=0, ge=0)
    min_frames: int = Field(default=30, ge=1)
    border_margin: int = Field(default=50, ge=0)
    fov_list: list[int] | None = None
    fov_start: int = Field(default=0, ge=0)
    fov_end: int | None = None


class ProcessingConfig(BaseModel):
    """Static configuration for processing pipeline.

    Attributes:
        channels: Channel selection and feature mapping.
        params: Processing parameters.
    """

    channels: Channels | None = None
    params: ProcessingParams = Field(default_factory=ProcessingParams)

    def get_param(self, key: str, default: Any = None) -> Any:
        """Get a parameter value with default. Deprecated: use config.params.<key> directly."""
        return getattr(self.params, key, default)


# =============================================================================
# EXTRACTION TYPES
# =============================================================================


class ProcessingBaseResult(BaseModel):
    """Result from trace extraction for a single cell at a single frame.

    Attributes:
        cell: Cell ID.
        frame: Frame index.
        good: Quality flag.
        xc: Centroid x coordinate (computed from mask, falls back to bbox center).
        yc: Centroid y coordinate (computed from mask, falls back to bbox center).
        x: Bounding box left edge (x0).
        y: Bounding box top edge (y0).
        w: Bounding box width (x1 - x0).
        h: Bounding box height (y1 - y0).
    """

    model_config = {"frozen": True}

    cell: int
    frame: int
    good: bool
    xc: float
    yc: float
    x: float
    y: float
    w: float
    h: float


def get_processing_base_fields() -> list[str]:
    """Get the base field names for the Result model."""
    return list(ProcessingBaseResult.model_fields.keys())


def get_processing_feature_field(feature: str, channel_id: int) -> str:
    """Get the CSV column name for a feature and channel."""
    return f"{feature}_ch_{channel_id}"


def make_processing_result(feature_columns: list[str]) -> type:
    """Dynamically create a Result model with base fields + feature columns.

    The resulting class will inherit from ProcessingBaseResult and be frozen.
    Feature fields will be floats defaulting to NaN.
    """
    field_definitions: dict[str, Any] = {
        col: (float, float("nan")) for col in feature_columns
    }
    return create_model(
        "Result",
        __base__=ProcessingBaseResult,
        **field_definitions,
    )


@dataclass
class ExtractionContext:
    """Context containing all information needed for feature extraction."""

    image: np.ndarray
    mask: np.ndarray
    background: (
        np.ndarray
    )  # Always present; zeros if no background correction available
    background_weight: float = 1.0  # Weight for background subtraction (default: 1.0)


# =============================================================================
# TRACKING TYPES
# =============================================================================


@dataclass
class Region:
    """Connected-component region summary.

    Attributes:
        area: Number of pixels in the region.
        bbox: Bounding box as ``(y0, x0, y1, x1)`` with exclusive end indices.
        coords: Array of ``(y, x)`` coordinates for all pixels in the region.
    """

    area: int
    bbox: tuple[int, int, int, int]
    coords: np.ndarray


# =============================================================================
# BACKGROUND TYPES
# =============================================================================


@dataclass
class TileSupport:
    """Support data for tiled background interpolation.

    Attributes:
        centers_x: 1D array of tile center ``x`` coordinates (pixels).
        centers_y: 1D array of tile center ``y`` coordinates (pixels).
        support: 2D array ``(n_tiles_y, n_tiles_x)`` of tile medians.
        shape: Spatial ``(H, W)`` shape of the original frame.
    """

    centers_x: np.ndarray
    centers_y: np.ndarray
    support: np.ndarray
    shape: tuple[int, int]


# =============================================================================
# MERGE TYPES
# =============================================================================


class ChannelFeatureConfig(BaseModel):
    """Configuration for feature extraction from a single channel.

    Attributes:
        channel_name: Name of the channel in H5 (e.g., 'fl_ch_1', 'pc_ch_0')
        channel_id: Numeric channel ID for CSV column naming (e.g., 1)
        background_name: Name of the background channel, or None for no background
        features: List of feature names to extract
        background_weight: Weight for background subtraction (0.0-1.0)
        use_bbox_as_mask: If True (default), use entire bounding box as mask.
            If False, use the cell segmentation mask.
    """

    channel_name: str
    channel_id: int
    background_name: str | None
    features: list[str]
    background_weight: float = 1.0
    use_bbox_as_mask: bool = True


class FeatureMaps(BaseModel):
    """Container for feature values per frame and cell."""

    model_config = {"arbitrary_types_allowed": True}

    features: dict[str, dict[tuple[int, int], float]]
    frames: list[int]
    cells: list[int]


__all__ = [
    "ChannelSelection",
    "Channels",
    "ProcessingConfig",
    "ProcessingParams",
    "ProcessingBaseResult",
    "get_processing_base_fields",
    "get_processing_feature_field",
    "make_processing_result",
    "ExtractionContext",
    "Region",
    "TileSupport",
    "ChannelFeatureConfig",
    "FeatureMaps",
]
