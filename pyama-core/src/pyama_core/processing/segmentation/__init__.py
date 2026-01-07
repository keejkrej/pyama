from pyama_core.processing.segmentation.logstd import (
    segment_cell as segment_cell_logstd,
)
from pyama_core.processing.segmentation.cellpose import (
    segment_cell as segment_cell_cellpose,
)
from typing import Callable, List

_SEGMENTERS = {
    "logstd": segment_cell_logstd,
    "cellpose": segment_cell_cellpose,
}


def get_segmenter(method: str = "logstd") -> Callable:
    """Get segmentation function by method name.

    Args:
        method: "logstd" or "cellpose"

    Returns:
        segment_cell function for the specified method.

    Raises:
        ValueError: If method is not recognized.
    """
    if method not in _SEGMENTERS:
        raise ValueError(
            f"Unknown segmentation method: {method}. Available: {list(_SEGMENTERS.keys())}"
        )
    return _SEGMENTERS[method]


def list_segmenters() -> List[str]:
    """List available segmentation methods.

    Returns:
        List of method names.
    """
    return list(_SEGMENTERS.keys())


__all__ = [
    "get_segmenter",
    "list_segmenters",
    "segment_cell_logstd",
    "segment_cell_cellpose",
]
