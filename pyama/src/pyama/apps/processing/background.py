from pathlib import Path
import math
from threading import Event, Lock
from typing import Callable

import numpy as np

from pyama.io.config import ensure_config
from pyama.io.zarr import open_raw_zarr
from pyama.types.io import MicroscopyMetadata
from pyama.types.processing import ProcessingConfig
from pyama.utils.processing import resolve_processing_positions
from pyama.utils.roi import build_union_roi_metadata

_RAW_ZARR_OPEN_LOCK = Lock()

def _compute_background_sample_pad(*, roi_h: int, roi_w: int, roi_pixels: int, min_samples: int) -> int:
    c = (roi_h * roi_w) - roi_pixels - min_samples
    if c >= 0:
        return 0
    b = 2.0 * float(roi_h + roi_w)
    disc = max(0.0, b * b - 16.0 * float(c))
    return max(0, int(math.ceil((-b + math.sqrt(disc)) / 8.0)))


def _estimate_bbox_background_value(
    *,
    raw_frame: np.ndarray,
    seg_frame: np.ndarray,
    roi_id: int,
    y0: int,
    x0: int,
    y1: int,
    x1: int,
    background_min_samples: int,
) -> int:
    roi = np.asarray(raw_frame[y0:y1, x0:x1], dtype=np.uint16)
    seg_roi = np.asarray(seg_frame[y0:y1, x0:x1], dtype=np.uint16)
    if roi.size == 0:
        return 0

    base_samples = roi[seg_roi != int(roi_id)]
    if int(base_samples.size) >= int(background_min_samples):
        return int(np.clip(float(np.median(base_samples)), 0.0, 65535.0))

    frame_h, frame_w = raw_frame.shape
    roi_h = max(0, y1 - y0)
    roi_w = max(0, x1 - x0)
    roi_pixels = int(np.count_nonzero(seg_roi == int(roi_id)))
    pad = _compute_background_sample_pad(
        roi_h=roi_h,
        roi_w=roi_w,
        roi_pixels=roi_pixels,
        min_samples=int(background_min_samples),
    )
    ey0 = max(0, y0 - pad)
    ex0 = max(0, x0 - pad)
    ey1 = min(frame_h, y1 + pad)
    ex1 = min(frame_w, x1 + pad)

    raw_region = np.asarray(raw_frame[ey0:ey1, ex0:ex1], dtype=np.uint16)
    seg_region = np.asarray(seg_frame[ey0:ey1, ex0:ex1], dtype=np.uint16)
    samples = raw_region[seg_region != int(roi_id)]
    if int(samples.size) > 0:
        background_value = float(np.median(samples))
    else:
        background_value = 0.0
    return int(np.clip(background_value, 0.0, 65535.0))


def run_background_to_raw_zarr(
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
    method = "mvp"
    raw_zarr_path = output_dir / "raw.zarr"
    with _RAW_ZARR_OPEN_LOCK:
        store = open_raw_zarr(raw_zarr_path, mode="a")

    if not config.channels or not config.channels.fl:
        return {
            "background_method": method,
            "background_datasets": 0,
            "background_skipped_datasets": 0,
            "background_frames": 0,
            "background_cancelled": False,
        }

    resolved_positions = (
        positions_subset
        if positions_subset is not None
        else resolve_processing_positions(metadata, config)
    )
    pc_channel = config.channels.get_pc_channel()
    fl_channels = sorted(config.channels.fl.keys())
    background_datasets = 0
    skipped_datasets = 0
    background_frames = 0
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
        seg_path = store.seg_tracked_path(position_id, pc_channel)
        try:
            seg_tracked = store.read_uint16_3d(seg_path)
        except KeyError as exc:
            raise FileNotFoundError(f"Missing seg_tracked dataset for background estimation: {seg_path}") from exc
        roi_ids, roi_bboxes, roi_is_present = build_union_roi_metadata(seg_tracked)

        for channel_id in fl_channels:
            if cancel_event and cancel_event.is_set():
                cancelled = True
                break
            raw_path = store.raw_path(position_id, channel_id)
            background_path = store.fl_background_path(position_id, channel_id)

            if not store.dataset_exists(raw_path):
                raise FileNotFoundError(f"Missing raw dataset for background estimation: {raw_path}")

            if store.dataset_exists(background_path):
                skipped_datasets += 1
                if progress_callback:
                    progress_callback(
                        {
                            "worker_id": worker_id,
                            "stage": "background",
                            "channel_id": channel_id,
                            "position_id": position_idx,
                            "position_index": position_progress_index,
                            "position_total": position_progress_total,
                            "frame_index": 0,
                            "frame_total": 0,
                            "message": "skipped",
                        }
                    )
                continue

            store.create_fl_background_dataset(
                metadata=metadata,
                position_id=position_id,
                position_index=position_idx,
                channel_id=channel_id,
                method=method,
            )

            for time_idx in range(metadata.n_frames):
                if cancel_event and cancel_event.is_set():
                    cancelled = True
                    break
                frame = store.read_raw_frame(position_id, channel_id, time_idx)
                bg_frame = np.zeros(frame.shape, dtype=np.uint16)
                for roi_idx, roi_id in enumerate(roi_ids):
                    if not bool(roi_is_present[roi_idx, time_idx]):
                        continue
                    x, y, w, h = [int(v) for v in roi_bboxes[roi_idx, time_idx]]
                    if w <= 0 or h <= 0:
                        continue
                    x0 = x
                    y0 = y
                    x1 = x0 + w
                    y1 = y0 + h
                    bg_value = _estimate_bbox_background_value(
                        raw_frame=frame,
                        seg_frame=np.asarray(seg_tracked[time_idx], dtype=np.uint16),
                        roi_id=int(roi_id),
                        y0=y0,
                        x0=x0,
                        y1=y1,
                        x1=x1,
                        background_min_samples=int(config.params.background_min_samples),
                    )
                    bg_frame[y0:y1, x0:x1] = np.uint16(bg_value)
                store.write_fl_background_frame(position_id, channel_id, time_idx, bg_frame)
                background_frames += 1
                if progress_callback:
                    progress_callback(
                        {
                            "worker_id": worker_id,
                            "stage": "background",
                            "channel_id": channel_id,
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
            background_datasets += 1
        if cancelled:
            break

    return {
        "background_method": method,
        "background_datasets": background_datasets,
        "background_skipped_datasets": skipped_datasets,
        "background_frames": background_frames,
        "background_cancelled": cancelled,
    }


__all__ = ["run_background_to_raw_zarr"]
