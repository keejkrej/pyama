"""Compute per-cell trajectory statistics."""

import numpy as np

from pyama_core.benchmark.trajectory import CellFrame, TrajectoryStats


def compute_trajectory_stats(
    cell_id: int,
    frames: list[CellFrame],
    fov: int = 0,
) -> TrajectoryStats:
    """Compute statistics for a single cell trajectory.

    Args:
        cell_id: Unique cell identifier.
        frames: List of CellFrame measurements sorted by frame.
        fov: Field of view index.

    Returns:
        TrajectoryStats with computed metrics.
    """
    frames = sorted(frames, key=lambda f: f.frame)
    n_frames = len(frames)

    duration_frames = n_frames

    # Velocities (frame-to-frame displacement)
    velocities: list[float] = []
    for i in range(1, n_frames):
        dx = frames[i].centroid_x - frames[i - 1].centroid_x
        dy = frames[i].centroid_y - frames[i - 1].centroid_y
        velocity = np.sqrt(dx**2 + dy**2)
        velocities.append(velocity)

    if velocities:
        mean_velocity = float(np.mean(velocities))
        std_velocity = float(np.std(velocities))
    else:
        mean_velocity = 0.0
        std_velocity = 0.0

    # Circularity
    circularities = [f.circularity for f in frames]
    mean_circularity = float(np.mean(circularities))
    std_circularity = float(np.std(circularities))

    # Area
    areas = [f.area for f in frames]
    mean_area = float(np.mean(areas))
    std_area = float(np.std(areas))

    return TrajectoryStats(
        cell_id=cell_id,
        fov=fov,
        duration_frames=duration_frames,
        mean_velocity=mean_velocity,
        std_velocity=std_velocity,
        mean_circularity=mean_circularity,
        std_circularity=std_circularity,
        mean_area=mean_area,
        std_area=std_area,
    )
