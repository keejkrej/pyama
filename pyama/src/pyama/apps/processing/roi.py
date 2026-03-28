from pathlib import Path
from threading import Event, Lock
from typing import Callable

import numpy as np

from pyama.apps.processing.bbox import load_bbox_rows
from pyama.io import get_microscopy_frame
from pyama.io.config import ensure_config
from pyama.io.zarr import open_rois_zarr
from pyama.types.io import MicroscopyMetadata
from pyama.types.processing import ProcessingConfig
from pyama.utils.processing import resolve_processing_positions

_ROIS_ZARR_OPEN_LOCK = Lock()


def run_roi_to_rois_zarr(
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
    config = ensure_config(config)
    method = "mvp"
    if not config.channels:
        return {
            "roi_method": method,
            "roi_positions": 0,
            "roi_skipped_positions": 0,
            "roi_count": 0,
            "roi_frames": 0,
            "roi_cancelled": False,
        }

    rois_zarr_path = output_dir / "rois.zarr"
    with _ROIS_ZARR_OPEN_LOCK:
        rois_store = open_rois_zarr(rois_zarr_path, mode="a")

    resolved_positions = (
        positions_subset
        if positions_subset is not None
        else resolve_processing_positions(metadata, config)
    )
    channel_ids = [config.channels.get_pc_channel(), *sorted(config.channels.fl.keys())]
    pc_channel = config.channels.get_pc_channel()

    roi_positions = 0
    skipped_positions = 0
    roi_count = 0
    roi_frames = 0
    cancelled = False

    for pos_offset, position_idx in enumerate(resolved_positions):
        if cancel_event and cancel_event.is_set():
            cancelled = True
            break
        position_progress_index = (
            global_position_lookup[position_idx]
            if global_position_lookup is not None
            else pos_offset + 1
        )
        position_progress_total = (
            global_position_total
            if global_position_total is not None
            else len(resolved_positions)
        )
        position_id = metadata.position_list[position_idx]
        roi_ids_path = rois_store.roi_ids_path(position_id)

        if rois_store.dataset_exists(roi_ids_path):
            skipped_positions += 1
            if progress_callback:
                progress_callback(
                    {
                        "worker_id": worker_id,
                        "stage": "roi",
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

        roi_ids, roi_bboxes = load_bbox_rows(
            output_dir=output_dir,
            position_id=position_id,
            frame_width=metadata.width,
            frame_height=metadata.height,
        )
        n_rois = int(roi_ids.size)
        n_frames = int(metadata.n_frames)

        rois_store.write_roi_ids(position_id, roi_ids)
        rois_store.write_roi_bboxes(position_id, roi_bboxes)

        for channel_id in channel_ids:
            for frame_idx in range(n_frames):
                if cancel_event and cancel_event.is_set():
                    cancelled = True
                    break
                raw_frame = get_microscopy_frame(
                    img=reader,
                    position=position_idx,
                    channel=channel_id,
                    time=frame_idx,
                    z=0,
                )
                raw_frame = np.asarray(raw_frame, dtype=np.uint16)
                for roi_idx, roi_id in enumerate(roi_ids):
                    x, y, w, h = [int(v) for v in roi_bboxes[int(roi_idx)]]
                    if w <= 0 or h <= 0:
                        continue
                    x1 = x + w
                    y1 = y + h
                    rois_store.write_roi_raw_frame(
                        position_id,
                        channel_id,
                        int(roi_id),
                        frame_idx,
                        raw_frame[y:y1, x:x1],
                    )
                roi_frames += n_rois
                if progress_callback:
                    progress_callback(
                        {
                            "worker_id": worker_id,
                            "stage": "roi",
                            "channel_id": channel_id,
                            "position_id": position_idx,
                            "position_index": position_progress_index,
                            "position_total": position_progress_total,
                            "frame_index": frame_idx + 1,
                            "frame_total": n_frames,
                            "message": "raw",
                        }
                    )
            if cancelled:
                break

        roi_positions += 1
        roi_count += n_rois
        if cancelled:
            break

    return {
        "roi_method": method,
        "roi_positions": roi_positions,
        "roi_skipped_positions": skipped_positions,
        "roi_count": roi_count,
        "roi_frames": roi_frames,
        "roi_cancelled": cancelled,
    }


__all__ = ["run_roi_to_rois_zarr"]
