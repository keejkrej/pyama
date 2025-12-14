"""Trajectory extraction from tracked segmentation masks."""

from dataclasses import dataclass

import numpy as np
from skimage.measure import regionprops


@dataclass
class TrajectoryStats:
    """Statistics for a single cell trajectory."""

    cell_id: int
    fov: int
    duration_frames: int
    mean_velocity: float
    std_velocity: float
    mean_circularity: float
    std_circularity: float
    mean_area: float
    std_area: float


@dataclass
class CellFrame:
    """Per-frame measurements for a single cell."""

    frame: int
    centroid_x: float
    centroid_y: float
    area: float
    perimeter: float
    circularity: float


def _compute_circularity(area: float, perimeter: float) -> float:
    """Compute circularity: 4*pi*area / perimeter^2."""
    if perimeter <= 0:
        return 0.0
    return (4.0 * np.pi * area) / (perimeter**2)


def extract_trajectories(
    tracked: np.ndarray,
    fov: int = 0,
    min_duration: int = 2,
) -> dict[int, list[CellFrame]]:
    """Extract per-cell trajectories from tracked segmentation.

    Args:
        tracked: 3D array (T, H, W) of tracked cell labels (uint16).
            Background is 0, each cell has a unique positive ID.
        fov: Field of view index for labeling.
        min_duration: Minimum number of frames a cell must appear in.

    Returns:
        Dictionary mapping cell_id -> list of CellFrame measurements.
    """
    n_frames = tracked.shape[0]
    trajectories: dict[int, list[CellFrame]] = {}

    for t in range(n_frames):
        frame_labels = tracked[t]
        props = regionprops(frame_labels)

        for prop in props:
            cell_id = prop.label
            centroid_y, centroid_x = prop.centroid
            area = float(prop.area)
            perimeter = float(prop.perimeter)
            circularity = _compute_circularity(area, perimeter)

            cell_frame = CellFrame(
                frame=t,
                centroid_x=centroid_x,
                centroid_y=centroid_y,
                area=area,
                perimeter=perimeter,
                circularity=circularity,
            )

            if cell_id not in trajectories:
                trajectories[cell_id] = []
            trajectories[cell_id].append(cell_frame)

    # Filter by minimum duration
    trajectories = {
        cell_id: frames
        for cell_id, frames in trajectories.items()
        if len(frames) >= min_duration
    }

    return trajectories
