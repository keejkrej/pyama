"""Log-STD based segmentation (functional API).

Pipeline per frame:
- compute log standard deviation with a uniform filter
- select a threshold from the log-STD histogram
- threshold and clean the mask with basic morphology

This implementation is optimized for performance and memory usage:
- Uses ``scipy.ndimage.uniform_filter`` to compute window statistics in O(1)
  time per pixel (independent of window size).
- Processes 3D inputs frame-by-frame to keep peak memory low.
- Provides an optional progress callback.
"""

import numpy as np
from scipy.ndimage import (
    uniform_filter,
    binary_fill_holes,
    binary_opening,
    binary_closing,
)
from skimage.measure import label, regionprops
from typing import Callable


def _compute_logstd_2d(image: np.ndarray, size: int = 1) -> np.ndarray:
    """Compute per-pixel log standard deviation for a 2D frame.

    Uses a uniform filter to compute local mean and mean-of-squares efficiently.
    Where the variance is not positive (e.g., constant window), the log-STD is
    set to 0.

    Args:
        image: 2D float-like array ``(H, W)``.
        size: Neighborhood half-size; effective window is ``2*size+1``.

    Returns:
        ``float32``-like array of log standard deviation with the same shape as
        ``image``.
    """
    mask_size = size * 2 + 1
    mean = uniform_filter(image, size=mask_size)
    mean_sq = uniform_filter(image * image, size=mask_size)
    var = mean_sq - mean * mean
    logstd = np.zeros_like(image)
    positive = var > 0
    logstd[positive] = 0.5 * np.log(var[positive])

    return logstd


def _threshold_by_histogram(values: np.ndarray, n_bins: int = 200) -> float:
    """Compute a threshold from the histogram of values.

    Finds the histogram peak as background mode and sets the threshold to
    ``mode + 3 * sigma``, where ``sigma`` is the standard deviation of values
    less than or equal to the mode.

    Args:
        values: 1D or ND array of values; flattened internally.
        n_bins: Number of histogram bins.

    Returns:
        Threshold value as a float.
    """
    flat = values.ravel()
    counts, edges = np.histogram(flat, bins=n_bins)
    bins = (edges[:-1] + edges[1:]) * 0.5
    hist_max = bins[int(np.argmax(counts))]
    background_vals = flat[flat <= hist_max]
    sigma = np.std(background_vals) if background_vals.size else 0

    return hist_max + 3 * sigma


def _morph_cleanup(mask: np.ndarray, size: int = 7, iterations: int = 3) -> np.ndarray:
    """Clean a 2D binary mask using simple morphology.

    Args:
        mask: 2D boolean array ``(H, W)``.
        size: Structuring element size (square ``size x size``).
        iterations: Number of opening/closing iterations.

    Returns:
        Cleaned boolean mask with the same shape as ``mask``.
    """
    struct = np.ones((size, size))
    out = binary_fill_holes(mask)
    out = binary_opening(out, iterations=iterations, structure=struct)
    out = binary_closing(out, iterations=iterations, structure=struct)

    return out


def segment_cell(
    image: np.ndarray,
    out: np.ndarray,
    min_size: int | None = None,
    max_size: int | None = None,
    progress_callback: Callable | None = None,
    cancel_event=None,
) -> None:
    """Segment a 3D stack using log-STD thresholding and morphology.

    For each frame, computes a log-STD image, selects a histogram-based
    threshold, applies basic morphological cleanup, and labels connected
    components. Writes results into ``out`` in-place.

    Args:
        image: 3D float-like array ``(T, H, W)``.
        out: Preallocated integer array ``(T, H, W)`` for labeled masks (uint16).
        min_size: Minimum region size in pixels (inclusive). Regions smaller than
            this are removed.
        max_size: Maximum region size in pixels (inclusive). Regions larger than
            this are removed.
        progress_callback: Optional callable ``(t, total, msg)`` for progress.
        cancel_event: Optional threading.Event for cancellation support.

    Returns:
        None. Results are written to ``out``.

    Raises:
        ValueError: If ``image`` and ``out`` are not 3D arrays or shapes differ.
    """
    if image.ndim != 3 or out.ndim != 3:
        raise ValueError("image and out must be 3D arrays")

    if out.shape != image.shape:
        raise ValueError("image and out must have the same shape (T, H, W)")

    image = image.astype(np.float32, copy=False)
    out = out.astype(np.uint16, copy=False)

    for t in range(image.shape[0]):
        # Check for cancellation before processing each frame
        if cancel_event and cancel_event.is_set():
            import logging

            logger = logging.getLogger(__name__)
            logger.info("Segmentation cancelled at frame %d", t)
            return

        logstd = _compute_logstd_2d(image[t])
        thresh = _threshold_by_histogram(logstd)
        binary = logstd > thresh
        cleaned = _morph_cleanup(binary)

        # Label connected components
        labeled = label(cleaned, connectivity=1).astype(np.uint16)

        # Filter by size if needed
        if min_size is not None or max_size is not None:
            props = regionprops(labeled)
            mask_to_remove = np.zeros_like(labeled, dtype=bool)

            for p in props:
                area = p.area
                if (min_size is not None and area < min_size) or (
                    max_size is not None and area > max_size
                ):
                    # Mark pixels for removal
                    # Using coords is faster than boolean indexing for sparse removals,
                    # but boolean indexing is simpler. Let's use simple boolean masking
                    # on the label ID since we have the labeled array.
                    mask_to_remove |= labeled == p.label

            labeled[mask_to_remove] = 0

            # Relabel to ensure consecutive IDs (optional, but good practice)
            # Actually, for tracking it doesn't strictly matter if IDs are consecutive,
            # but it keeps the max ID lower. However, relabeling can be expensive.
            # Tracking usually handles non-consecutive IDs fine.
            # Let's skip relabeling for performance unless necessary.

        out[t] = labeled

        if progress_callback is not None:
            progress_callback(t, image.shape[0], "Segmentation")
