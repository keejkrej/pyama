from pathlib import Path
from threading import Event, Lock
from typing import Callable

import numpy as np
from scipy.ndimage import (
    binary_closing,
    binary_fill_holes,
    binary_opening,
    uniform_filter,
)
from skimage.measure import label

from pyama.io.config import ensure_config
from pyama.io.zarr import open_raw_zarr
from pyama.types.io import MicroscopyMetadata
from pyama.types.processing import ProcessingConfig
from pyama.utils.processing import resolve_processing_positions

_RAW_ZARR_OPEN_LOCK = Lock()


def _compute_logstd_2d(image: np.ndarray, size: int = 1) -> np.ndarray:
    mask_size = size * 2 + 1
    mean = uniform_filter(image, size=mask_size)
    mean_sq = uniform_filter(image * image, size=mask_size)
    var = mean_sq - mean * mean
    logstd = np.zeros_like(image, dtype=np.float32)
    positive = var > 0
    logstd[positive] = 0.5 * np.log(var[positive])
    return logstd


def _threshold_by_histogram(values: np.ndarray, n_bins: int = 200) -> float:
    flat = values.ravel()
    counts, edges = np.histogram(flat, bins=n_bins)
    bins = (edges[:-1] + edges[1:]) * 0.5
    hist_max = bins[int(np.argmax(counts))]
    background_vals = flat[flat <= hist_max]
    sigma = np.std(background_vals) if background_vals.size else 0.0
    return float(hist_max + (3.0 * sigma))


def _morph_cleanup(mask: np.ndarray, size: int = 7, iterations: int = 3) -> np.ndarray:
    struct = np.ones((size, size))
    out = binary_fill_holes(mask)
    out = binary_opening(out, iterations=iterations, structure=struct)
    out = binary_closing(out, iterations=iterations, structure=struct)
    return out


def _segment_frame_logstd(frame: np.ndarray) -> np.ndarray:
    frame_f = np.asarray(frame, dtype=np.float32)
    logstd = _compute_logstd_2d(frame_f)
    thresh = _threshold_by_histogram(logstd)
    binary = _morph_cleanup(logstd > thresh)
    return np.asarray(label(binary, connectivity=1), dtype=np.uint16)

def run_segment_to_raw_zarr(
    *,
    reader,
    metadata: MicroscopyMetadata,
    config: ProcessingConfig,
    output_dir: Path,
    cancel_event: Event | None = None,
    progress_callback: Callable[[dict[str, int | str]], None] | None = None,
    positions_subset: list[int] | None = None,
    worker_id: int = 0,
    global_position_lookup: dict[int, int] | None = None,
    global_position_total: int | None = None,
) -> dict[str, int | str | bool]:
    del reader
    config = ensure_config(config)
    raw_zarr_path = output_dir / "raw.zarr"
    with _RAW_ZARR_OPEN_LOCK:
        store = open_raw_zarr(raw_zarr_path, mode="a")

    if not config.channels:
        return {
            "segmented_datasets": 0,
            "segmentation_skipped_datasets": 0,
            "segmented_frames": 0,
            "segmentation_cancelled": False,
        }

    resolved_positions = (
        positions_subset
        if positions_subset is not None
        else resolve_processing_positions(metadata, config)
    )
    pc_channel = config.channels.get_pc_channel()

    segmented_datasets = 0
    skipped_datasets = 0
    segmented_frames = 0
    cancelled = False

    for pos_offset, position_idx in enumerate(resolved_positions):
        if cancel_event and cancel_event.is_set():
            cancelled = True
            break
        position_progress_index = (
            global_position_lookup[position_idx] if global_position_lookup is not None else pos_offset + 1
        )
        position_progress_total = global_position_total if global_position_total is not None else len(resolved_positions)
        position_id = metadata.position_list[position_idx]
        raw_path = store.raw_path(position_id, pc_channel)
        seg_path = store.seg_labeled_path(position_id, pc_channel)

        if not store.dataset_exists(raw_path):
            raise FileNotFoundError(f"Missing raw dataset for segmentation: {raw_path}")

        if store.dataset_exists(seg_path):
            skipped_datasets += 1
            if progress_callback:
                progress_callback(
                    {
                        "worker_id": worker_id,
                        "stage": "segment",
                        "channel_id": pc_channel,
                        "position_id": position_idx,
                        "position_index": position_progress_index,
                        "position_total": position_progress_total,
                        "frame_index": 0,
                        "frame_total": 0,
                        "message": "skipped",
                    }
                )
            continue

        store.create_seg_labeled_dataset(
            metadata=metadata,
            position_id=position_id,
            position_index=position_idx,
            channel_id=pc_channel,
        )

        for time_idx in range(metadata.n_frames):
            if cancel_event and cancel_event.is_set():
                cancelled = True
                break
            frame = store.read_raw_frame(position_id, pc_channel, time_idx)
            store.write_seg_labeled_frame(position_id, pc_channel, time_idx, _segment_frame_logstd(frame))
            segmented_frames += 1
            if progress_callback:
                progress_callback(
                    {
                        "worker_id": worker_id,
                        "stage": "segment",
                        "channel_id": pc_channel,
                        "position_id": position_idx,
                        "position_index": position_progress_index,
                        "position_total": position_progress_total,
                        "frame_index": time_idx + 1,
                        "frame_total": metadata.n_frames,
                        "message": "",
                    }
                )
        if cancelled:
            break
        segmented_datasets += 1

    return {
        "segmented_datasets": segmented_datasets,
        "segmentation_skipped_datasets": skipped_datasets,
        "segmented_frames": segmented_frames,
        "segmentation_cancelled": cancelled,
    }


__all__ = [
    "run_segment_to_raw_zarr",
]
