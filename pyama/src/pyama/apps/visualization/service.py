"""Function-based service entrypoints for visualization."""

from pyama.io.visualization_cache import (
    build_uint8_cache as get_or_build_uint8,
    load_cached_frame as load_frame,
    load_cached_slice as load_slice,
)
from pyama.utils.visualization import (
    normalize_frame,
    normalize_segmentation,
    normalize_stack,
    preprocess_visualization_data,
)

__all__ = [
    "get_or_build_uint8",
    "load_frame",
    "load_slice",
    "normalize_frame",
    "normalize_segmentation",
    "normalize_stack",
    "preprocess_visualization_data",
]
