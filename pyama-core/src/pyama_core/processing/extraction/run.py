"""Trace extraction for microscopy time-series analysis (functional API).

Pipeline:
- Track cells across time using IoU-based tracking
- Extract features for each cell in each frame
- Filter traces by length and quality criteria

This implementation follows the functional style used in other processing modules
and is designed for performance with time-series datasets:
- Processes stacks frame-by-frame to manage memory usage
- Uses vectorized operations for feature extraction
- Provides progress callbacks for long-running operations
- Filters traces to remove short-lived or low-quality cells
"""

from dataclasses import dataclass
from typing import Callable, Any

import numpy as np
import pandas as pd

from pyama_core.processing.extraction.features import (
    ExtractionContext,
    get_feature_extractor,
)


@dataclass
class ChannelFeatureConfig:
    """Configuration for feature extraction from a single channel.

    Attributes:
        channel_name: Name of the channel in H5 (e.g., 'fl_ch_1', 'pc_ch_0')
        channel_id: Numeric channel ID for CSV column naming (e.g., 1)
        background_name: Name of the background channel, or None for no background
        features: List of feature names to extract
        background_weight: Weight for background subtraction (0.0-1.0)
        use_bbox_as_mask: If True (default), use entire bounding box as mask.
            If False, use the cell segmentation mask.
    """
    channel_name: str
    channel_id: int
    background_name: str | None
    features: list[str]
    background_weight: float = 1.0
    use_bbox_as_mask: bool = True


def extract_trace_from_crops(
    crops_h5_path,
    channel_configs: list[ChannelFeatureConfig],
    progress_callback: Callable | None = None,
    cancel_event=None,
) -> pd.DataFrame:
    """Extract cell traces from pre-cropped HDF5 data.

    This function works with the cropped cell data saved by CroppingService,
    iterating over cells once and extracting all features from all channels.

    Parameters:
    - crops_h5_path: Path to the HDF5 file containing cropped cell data
    - channel_configs: List of ChannelFeatureConfig specifying which features
        to extract from which channels
    - progress_callback: Optional function(current, total, message) for progress
    - cancel_event: Optional threading.Event for cancellation support

    Returns:
    - DataFrame with columns [cell, frame, good, position_x, position_y,
      bbox_x0, bbox_y0, bbox_x1, bbox_y1, <feature>_<channel>, ...]
    """
    import h5py

    if not channel_configs:
        return pd.DataFrame()

    # Build column names: base columns + feature_channel columns
    base_fields = ["cell", "frame", "good", "position_x", "position_y",
                   "bbox_x0", "bbox_y0", "bbox_x1", "bbox_y1"]
    feature_columns = []
    for cfg in channel_configs:
        for feat in cfg.features:
            feature_columns.append(f"{feat}_ch_{cfg.channel_id}")

    col_names = base_fields + feature_columns
    rows: list[dict[str, Any]] = []

    with h5py.File(crops_h5_path, "r") as f:
        cell_groups = [k for k in f.keys() if k.startswith("cell_")]
        total_cells = len(cell_groups)

        for cell_idx, cell_key in enumerate(sorted(cell_groups)):
            if cancel_event and cancel_event.is_set():
                break

            cell_grp = f[cell_key]
            cell_id = int(cell_key.split("_")[1])

            # Load cell metadata
            bboxes = cell_grp["bboxes"][:]  # (n_frames, 5)
            frames = cell_grp["frames"][:]  # (n_frames,)
            masks_grp = cell_grp["masks"]
            channels_grp = cell_grp.get("channels")
            backgrounds_grp = cell_grp.get("backgrounds")

            # Process each frame for this cell
            for i, (frame_idx, bbox) in enumerate(zip(frames, bboxes)):
                if cancel_event and cancel_event.is_set():
                    break

                frame_key = f"frame_{frame_idx:04d}"

                # Load mask
                if frame_key not in masks_grp:
                    continue
                mask = masks_grp[frame_key][:]

                # Compute position from mask (global coordinates)
                _, y0, x0, y1, x1 = bbox
                row_inds = np.where(mask.any(axis=1))[0]
                col_inds = np.where(mask.any(axis=0))[0]
                if row_inds.size == 0 or col_inds.size == 0:
                    position_x = float((x0 + x1) / 2.0)
                    position_y = float((y0 + y1) / 2.0)
                else:
                    local_x = float((col_inds[0] + col_inds[-1]) / 2.0)
                    local_y = float((row_inds[0] + row_inds[-1]) / 2.0)
                    position_x = float(x0) + local_x
                    position_y = float(y0) + local_y

                # Start building row with base columns
                row: dict[str, Any] = {
                    "cell": cell_id,
                    "frame": int(frame_idx),
                    "good": True,
                    "position_x": position_x,
                    "position_y": position_y,
                    "bbox_x0": float(x0),
                    "bbox_y0": float(y0),
                    "bbox_x1": float(x1),
                    "bbox_y1": float(y1),
                }

                # Extract features from each channel
                for cfg in channel_configs:
                    col_suffix = f"_ch_{cfg.channel_id}"

                    # Get channel data
                    if channels_grp is None or cfg.channel_name not in channels_grp:
                        # Fill with NaN if channel not available
                        for feat in cfg.features:
                            row[f"{feat}{col_suffix}"] = np.nan
                        continue

                    ch_grp = channels_grp[cfg.channel_name]
                    if frame_key not in ch_grp:
                        for feat in cfg.features:
                            row[f"{feat}{col_suffix}"] = np.nan
                        continue

                    image_crop = ch_grp[frame_key][:]

                    # Get background data
                    if cfg.background_name and backgrounds_grp and cfg.background_name in backgrounds_grp:
                        bg_grp = backgrounds_grp[cfg.background_name]
                        if frame_key in bg_grp:
                            bg_crop = bg_grp[frame_key][:]
                        else:
                            bg_crop = np.zeros_like(image_crop, dtype=np.float32)
                    else:
                        bg_crop = np.zeros_like(image_crop, dtype=np.float32)

                    # Determine which mask to use
                    if cfg.use_bbox_as_mask:
                        # Use entire bounding box as mask (all True)
                        effective_mask = np.ones_like(image_crop, dtype=bool)
                    else:
                        # Use the cell mask
                        effective_mask = mask

                    # Create extraction context
                    ctx = ExtractionContext(
                        image=image_crop.astype(np.float32),
                        mask=effective_mask,
                        background=bg_crop.astype(np.float32),
                        background_weight=cfg.background_weight,
                    )

                    # Extract each feature
                    for feat in cfg.features:
                        extractor = get_feature_extractor(feat)
                        row[f"{feat}{col_suffix}"] = float(extractor(ctx))

                rows.append(row)

            if progress_callback:
                progress_callback(cell_idx, total_cells, "Extracting features")

    df = pd.DataFrame(rows, columns=col_names)
    return df
