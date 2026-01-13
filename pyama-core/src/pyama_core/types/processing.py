"""Dataclasses shared across workflow services to avoid circular imports."""

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(slots=True)
class ChannelSelection:
    channel: int
    features: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Channels:
    pc: ChannelSelection
    fl: list[ChannelSelection] = field(default_factory=list)

    def get_pc_channel(self) -> int:
        return self.pc.channel

    def get_pc_features(self) -> list[str]:
        return list(self.pc.features)

    def get_fl_feature_map(self) -> dict[int, list[str]]:
        return {selection.channel: list(selection.features) for selection in self.fl}

    def get_fl_channels(self) -> list[int]:
        return [selection.channel for selection in self.fl]


# =============================================================================
# EXTRACTION TYPES
# =============================================================================


@dataclass(frozen=True)
class ProcessingBaseResult:
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
    """Get the base field names for the Result dataclass."""
    return [f.name for f in dataclasses.fields(ProcessingBaseResult)]


def get_processing_feature_field(feature: str, channel_id: int) -> str:
    """Get the CSV column name for a feature and channel."""
    return f"{feature}_ch_{channel_id}"


def make_processing_result(feature_columns: list[str]) -> type:
    """Dynamically create a Result dataclass with base fields + feature columns.

    The resulting class will inherit from BaseResult and be frozen.
    Feature fields will be floats defaulting to NaN.
    """
    feature_fields = [
        (col, float, field(default=float("nan"))) for col in feature_columns
    ]
    return dataclasses.make_dataclass(
        "Result",
        feature_fields,
        bases=(ProcessingBaseResult,),
        frozen=True,
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


@dataclass
class FeatureMaps:
    """Container for feature values per frame and cell."""

    features: dict[str, dict[tuple[int, int], float]]
    frames: list[int]
    cells: list[int]


# =============================================================================
# CONTEXT TYPES
# =============================================================================


@dataclass
class ProcessingContext:
    """Context passing through the processing pipeline."""

    output_dir: Path
    channels: Channels
    params: dict[str, Any] = field(default_factory=dict)
    results: dict[int, Any] = field(default_factory=dict)


__all__ = [
    "ChannelSelection",
    "Channels",
    "ProcessingBaseResult",
    "get_processing_base_fields",
    "get_processing_feature_field",
    "make_processing_result",
    "ExtractionContext",
    "Region",
    "TileSupport",
    "FeatureMaps",
    "ProcessingContext",
]
