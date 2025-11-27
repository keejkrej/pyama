"""Cell cropping from tracked segmentation (functional API).

This module extracts bounding box crops for each tracked cell across all frames.
Given the labeled segmentation output from tracking, it computes per-cell bounding
boxes and extracts crops from raw image channels.

The public entrypoint ``crop_cells`` processes a single FOV and returns
crop data organized by cell ID.
"""

import numpy as np
from dataclasses import dataclass
from typing import Callable
from scipy.ndimage import binary_dilation, binary_erosion
from skimage.measure import regionprops


@dataclass
class CellCrop:
    """Container for a single cell's cropped data across frames.

    Attributes:
        cell_id: Unique cell identifier (from tracking).
        bboxes: Per-frame bounding boxes as (t, y0, x0, y1, x1) arrays.
            Shape is (n_frames_present, 5). Frames where cell is absent are excluded.
        frames: Frame indices where this cell is present.
        masks: List of 2D boolean masks for each frame (cropped to bbox size).
        crops: Dict mapping channel name to list of 2D cropped arrays per frame.
        backgrounds: Dict mapping channel name to list of 2D cropped background arrays.
    """

    cell_id: int
    bboxes: np.ndarray
    frames: np.ndarray
    masks: list[np.ndarray]
    crops: dict[str, list[np.ndarray]]
    backgrounds: dict[str, list[np.ndarray]]


def _compute_cell_bboxes(
    labeled: np.ndarray,
    padding: int = 0,
) -> dict[int, list[tuple[int, int, int, int, int]]]:
    """Compute bounding boxes for all cells across all frames.

    Args:
        labeled: 3D labeled array (T, H, W) with cell IDs.
        padding: Pixels to pad around each bounding box.

    Returns:
        Dict mapping cell_id -> list of (frame, y0, x0, y1, x1) tuples.
        Only frames where the cell is present are included.
    """
    n_frames, height, width = labeled.shape
    cell_bboxes: dict[int, list[tuple[int, int, int, int, int]]] = {}

    for t in range(n_frames):
        frame = labeled[t]
        for prop in regionprops(frame):
            cell_id = prop.label
            y0, x0, y1, x1 = prop.bbox

            # Apply padding with bounds checking
            y0 = max(0, y0 - padding)
            x0 = max(0, x0 - padding)
            y1 = min(height, y1 + padding)
            x1 = min(width, x1 + padding)

            if cell_id not in cell_bboxes:
                cell_bboxes[cell_id] = []
            cell_bboxes[cell_id].append((t, y0, x0, y1, x1))

    return cell_bboxes


def _apply_mask_margin(mask: np.ndarray, margin: int) -> np.ndarray:
    """Apply dilation or erosion to a mask based on margin value.

    Args:
        mask: 2D boolean mask.
        margin: Positive = dilate (grow), negative = erode (shrink), 0 = no change.

    Returns:
        Modified mask. Returns original if margin is 0 or mask becomes empty.
    """
    if margin == 0:
        return mask

    size = abs(margin)
    struct = np.ones((size * 2 + 1, size * 2 + 1), dtype=bool)

    if margin > 0:
        return binary_dilation(mask, structure=struct)
    else:
        result = binary_erosion(mask, structure=struct)
        # If erosion makes mask empty, return original
        if not result.any():
            return mask
        return result


def _extract_cell_crops(
    cell_id: int,
    bboxes: list[tuple[int, int, int, int, int]],
    labeled: np.ndarray,
    channels: dict[str, np.ndarray],
    backgrounds: dict[str, np.ndarray],
    mask_margin: int = 0,
) -> CellCrop:
    """Extract crops for a single cell across all its frames.

    Args:
        cell_id: The cell identifier.
        bboxes: List of (frame, y0, x0, y1, x1) for this cell.
        labeled: Full labeled array (T, H, W).
        channels: Dict mapping channel name to (T, H, W) arrays.
        backgrounds: Dict mapping channel name to (T, H, W) background arrays.
        mask_margin: Pixels to dilate (positive) or erode (negative) the mask.

    Returns:
        CellCrop with extracted data.
    """
    frames = []
    bbox_array = []
    masks = []
    crops: dict[str, list[np.ndarray]] = {name: [] for name in channels}
    bg_crops: dict[str, list[np.ndarray]] = {name: [] for name in backgrounds}

    for t, y0, x0, y1, x1 in bboxes:
        frames.append(t)
        bbox_array.append([t, y0, x0, y1, x1])

        # Extract mask for this cell in this frame
        label_crop = labeled[t, y0:y1, x0:x1]
        mask = label_crop == cell_id

        # Apply mask margin (dilation/erosion)
        mask = _apply_mask_margin(mask, mask_margin)
        masks.append(mask)

        # Extract crops from each channel
        for name, data in channels.items():
            crop = data[t, y0:y1, x0:x1].copy()
            crops[name].append(crop)

        # Extract background crops
        for name, data in backgrounds.items():
            bg_crop = data[t, y0:y1, x0:x1].copy()
            bg_crops[name].append(bg_crop)

    return CellCrop(
        cell_id=cell_id,
        bboxes=np.array(bbox_array, dtype=np.int32),
        frames=np.array(frames, dtype=np.int32),
        masks=masks,
        crops=crops,
        backgrounds=bg_crops,
    )


def crop_cells(
    labeled: np.ndarray,
    channels: dict[str, np.ndarray] | None = None,
    backgrounds: dict[str, np.ndarray] | None = None,
    padding: int = 0,
    mask_margin: int = 0,
    min_frames: int = 1,
    progress_callback: Callable | None = None,
    cancel_event=None,
) -> list[CellCrop]:
    """Extract bounding box crops for all tracked cells.

    Given a labeled segmentation array from tracking and optional raw channel
    data, extracts per-cell crops with masks.

    Args:
        labeled: 3D uint16 array (T, H, W) with tracked cell IDs.
            0 = background, 1+ = cell IDs.
        channels: Optional dict mapping channel names to (T, H, W) arrays.
            If None, only masks and bboxes are extracted.
        backgrounds: Optional dict mapping channel names to (T, H, W) background arrays.
            Keys should match the fluorescence channels in `channels`.
        padding: Pixels to pad around each bounding box.
        mask_margin: Pixels to dilate (positive) or erode (negative) the cell mask.
            Positive values grow the mask to include more area around the cell.
            Negative values shrink the mask to exclude edge pixels.
            Default is 0 (no change).
        min_frames: Minimum number of frames a cell must be present.
            Cells with fewer frames are excluded.
        progress_callback: Optional callable (current, total, msg) for progress.
        cancel_event: Optional threading.Event for cancellation.

    Returns:
        List of CellCrop objects, one per cell that meets min_frames threshold.

    Raises:
        ValueError: If labeled is not 3D or channel shapes don't match.
    """
    if labeled.ndim != 3:
        raise ValueError("labeled must be 3D array with shape (T, H, W)")

    if channels is None:
        channels = {}

    if backgrounds is None:
        backgrounds = {}

    for name, data in channels.items():
        if data.shape != labeled.shape:
            raise ValueError(
                f"Channel '{name}' shape {data.shape} doesn't match "
                f"labeled shape {labeled.shape}"
            )

    for name, data in backgrounds.items():
        if data.shape != labeled.shape:
            raise ValueError(
                f"Background '{name}' shape {data.shape} doesn't match "
                f"labeled shape {labeled.shape}"
            )

    # Compute bounding boxes for all cells
    if progress_callback:
        progress_callback(0, 3, "Computing bounding boxes")

    if cancel_event and cancel_event.is_set():
        return []

    cell_bboxes = _compute_cell_bboxes(labeled, padding=padding)

    # Filter cells by minimum frame count
    cell_ids = [
        cid for cid, bboxes in cell_bboxes.items()
        if len(bboxes) >= min_frames
    ]

    if progress_callback:
        progress_callback(1, 3, "Extracting crops")

    if cancel_event and cancel_event.is_set():
        return []

    # Extract crops for each cell
    results = []
    for i, cell_id in enumerate(cell_ids):
        if cancel_event and cancel_event.is_set():
            return results

        crop = _extract_cell_crops(
            cell_id=cell_id,
            bboxes=cell_bboxes[cell_id],
            labeled=labeled,
            channels=channels,
            backgrounds=backgrounds,
            mask_margin=mask_margin,
        )
        results.append(crop)

    if progress_callback:
        progress_callback(2, 3, "Done")

    return results
