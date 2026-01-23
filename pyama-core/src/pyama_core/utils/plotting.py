"""Plotting utilities for numpy arrays."""

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)


def plot_numpy_array(
    array_path: Path | str,
    frame: int | None = None,
    output_path: Path | str | None = None,
    cmap: str | None = None,
    dpi: int = 150,
) -> Path:
    """
    Plot a frame from a numpy array file.

    For 3D arrays (time, height, width), plots the specified frame.
    For 2D arrays, plots the entire array.

    Args:
        array_path: Path to the numpy array file (.npy)
        frame: Frame index to plot (for 3D arrays). If None, plots middle frame.
        output_path: Output path for the plot. If None, saves next to input file.
        cmap: Colormap to use. If None, auto-selects based on data characteristics.
        dpi: Resolution for saved plot.

    Returns:
        Path to the saved plot file.

    Raises:
        FileNotFoundError: If array_path doesn't exist.
        ValueError: If array shape is not 2D or 3D, or frame index is out of range.
    """
    array_path = Path(array_path)
    if not array_path.exists():
        raise FileNotFoundError(f"Array file not found: {array_path}")

    # Load array
    arr = np.load(array_path)
    logger.debug(f"Loaded array: shape={arr.shape}, dtype={arr.dtype}")

    # Determine array dimensions
    if arr.ndim == 2:
        # 2D array - plot directly
        frame_data = arr
        frame_info = ""
    elif arr.ndim == 3:
        # 3D array - extract frame
        n_frames, height, width = arr.shape
        if frame is None:
            frame = n_frames // 2
            logger.info(f"No frame specified, using middle frame: {frame}")
        elif frame < 0 or frame >= n_frames:
            raise ValueError(
                f"Frame index {frame} out of range [0, {n_frames - 1}]"
            )
        frame_data = arr[frame]
        frame_info = f" - Frame {frame}/{n_frames - 1}"
    else:
        raise ValueError(
            f"Unsupported array shape: {arr.shape}. Expected 2D or 3D array."
        )

    # Auto-select colormap if not specified
    if cmap is None:
        # Check if this looks like a labeled segmentation mask
        # (integer dtype with discrete values, typically starting from 0 or 1)
        is_labeled = (
            np.issubdtype(arr.dtype, np.integer)
            and arr.min() >= 0
            and arr.max() < 1000  # Reasonable upper bound for cell IDs
        )
        if is_labeled:
            cmap = "nipy_spectral"  # Good for discrete labels
            logger.debug("Detected labeled segmentation mask, using nipy_spectral colormap")
        else:
            cmap = "gray"  # Default for intensity images
            logger.debug("Using gray colormap for intensity data")

    # Create plot
    fig, ax = plt.subplots(figsize=(12, 10))
    im = ax.imshow(frame_data, cmap=cmap, interpolation="nearest")

    # Set title with file info
    file_name = array_path.stem
    title = f"{file_name}{frame_info}"
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel("X (pixels)")
    ax.set_ylabel("Y (pixels)")

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    if np.issubdtype(arr.dtype, np.integer) and arr.min() >= 0:
        # For labeled masks, show cell ID
        cbar.set_label("Cell ID")
    else:
        cbar.set_label("Intensity")

    # Determine output path
    if output_path is None:
        output_path = array_path.parent / f"{array_path.stem}_plot.png"
    else:
        output_path = Path(output_path)
        if output_path.is_dir():
            output_path = output_path / f"{array_path.stem}_plot.png"

    # Save plot
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    logger.info(f"Plot saved to: {output_path}")
    return output_path
