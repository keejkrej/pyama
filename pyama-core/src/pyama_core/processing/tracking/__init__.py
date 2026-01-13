from pyama_core.processing.tracking.iou import track_cell as track_cell_iou
from pyama_core.processing.tracking.btrack import track_cell as track_cell_btrack
from typing import Callable, List

_TRACKERS = {
    "iou": track_cell_iou,
    "btrack": track_cell_btrack,
}


def get_tracker(method: str = "iou") -> Callable:
    """Get tracking function by method name.

    Args:
        method: "iou" or "btrack"

    Returns:
        track_cell function for the specified method.

    Raises:
        ValueError: If method is not recognized.
    """
    if method not in _TRACKERS:
        raise ValueError(
            f"Unknown tracking method: {method}. Available: {list(_TRACKERS.keys())}"
        )
    return _TRACKERS[method]


def list_trackers() -> List[str]:
    """List available tracking methods.

    Returns:
        List of method names.
    """
    return list(_TRACKERS.keys())


__all__ = ["get_tracker", "list_trackers", "track_cell_iou", "track_cell_btrack"]
