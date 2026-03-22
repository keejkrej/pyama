"""Visualization-related shared data contracts."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CachedStack:
    """Metadata for a cached, normalized stack."""

    path: Path
    shape: tuple[int, ...]
    n_frames: int
    vmin: int = 0
    vmax: int = 255


@dataclass(frozen=True, slots=True)
class RoiOverlay:
    roi: int
    frame: int
    is_good: bool
    x: float
    y: float
    w: float
    h: float


__all__ = ["CachedStack", "RoiOverlay"]
