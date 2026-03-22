from pathlib import Path
from threading import Event, Lock
from typing import Callable

import numpy as np

from pyama.io.config import ensure_config
from pyama.io.zarr import open_raw_zarr, open_rois_zarr
from pyama.types.io import MicroscopyMetadata
from pyama.types.processing import ProcessingConfig
from pyama.utils.processing import resolve_processing_positions
from pyama.utils.roi import build_frame_roi_metadata

_RAW_ZARR_OPEN_LOCK = Lock()
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
    del reader
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

    raw_zarr_path = output_dir / "raw.zarr"
    rois_zarr_path = output_dir / "rois.zarr"
    with _RAW_ZARR_OPEN_LOCK:
        raw_store = open_raw_zarr(raw_zarr_path, mode="a")
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
            global_position_lookup[position_idx] if global_position_lookup is not None else pos_offset + 1
        )
        position_progress_total = global_position_total if global_position_total is not None else len(resolved_positions)
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

        seg_tracked_path = raw_store.seg_tracked_path(position_id, pc_channel)
        try:
            seg_tracked = raw_store.read_uint16_3d(seg_tracked_path)
        except KeyError as exc:
            raise FileNotFoundError(f"Missing seg_tracked dataset for roi extraction: {seg_tracked_path}") from exc

        roi_ids, roi_bboxes, roi_is_present = build_frame_roi_metadata(seg_tracked)
        n_rois = int(roi_ids.size)
        n_frames = int(seg_tracked.shape[0])

        rois_store.write_roi_ids(position_id, roi_ids)
        rois_store.write_roi_bboxes(position_id, roi_bboxes)
        rois_store.write_roi_is_present(position_id, roi_is_present)

        for frame_idx in range(n_frames):
            if cancel_event and cancel_event.is_set():
                cancelled = True
                break
            seg_frame = seg_tracked[frame_idx]
            present_roi_indices = np.where(roi_is_present[:, frame_idx])[0]
            for roi_idx in present_roi_indices:
                roi_id = int(roi_ids[int(roi_idx)])
                x, y, w, h = [int(v) for v in roi_bboxes[int(roi_idx), frame_idx]]
                roi_w = max(0, w)
                roi_h = max(0, h)
                if roi_h == 0 or roi_w == 0:
                    continue
                x0 = x
                y0 = y
                x1 = x0 + roi_w
                y1 = y0 + roi_h
                rois_store.write_seg_mask_frame(
                    position_id,
                    pc_channel,
                    roi_id,
                    frame_idx,
                    np.asarray(seg_frame[y0:y1, x0:x1] == roi_id, dtype=bool),
                )
            if progress_callback:
                progress_callback(
                    {
                        "worker_id": worker_id,
                        "stage": "roi",
                        "channel_id": pc_channel,
                        "position_id": position_idx,
                        "position_index": position_progress_index,
                        "position_total": position_progress_total,
                        "frame_index": frame_idx + 1,
                        "frame_total": n_frames,
                        "message": "seg",
                    }
                )
        if cancelled:
            break

        for channel_id in channel_ids:
            raw_path = raw_store.raw_path(position_id, channel_id)
            if not raw_store.dataset_exists(raw_path):
                raise FileNotFoundError(f"Missing raw dataset for roi extraction: {raw_path}")
            has_background = False
            if channel_id in config.channels.fl:
                bg_path = raw_store.fl_background_path(position_id, channel_id)
                has_background = raw_store.get_optional_array(bg_path) is not None

            for frame_idx in range(n_frames):
                if cancel_event and cancel_event.is_set():
                    cancelled = True
                    break
                raw_frame = raw_store.read_raw_frame(position_id, channel_id, frame_idx)
                bg_frame = (
                    raw_store.read_fl_background_frame(position_id, channel_id, frame_idx)
                    if has_background
                    else None
                )
                present_roi_indices = np.where(roi_is_present[:, frame_idx])[0]
                for roi_idx in present_roi_indices:
                    roi_id = int(roi_ids[int(roi_idx)])
                    x, y, w, h = [int(v) for v in roi_bboxes[int(roi_idx), frame_idx]]
                    roi_w = max(0, w)
                    roi_h = max(0, h)
                    if roi_h == 0 or roi_w == 0:
                        continue
                    x0 = x
                    y0 = y
                    x1 = x0 + roi_w
                    y1 = y0 + roi_h

                    rois_store.write_roi_raw_frame(
                        position_id,
                        channel_id,
                        roi_id,
                        frame_idx,
                        np.asarray(raw_frame[y0:y1, x0:x1], dtype=np.uint16),
                    )
                    if bg_frame is not None:
                        rois_store.write_roi_background_frame(
                            position_id,
                            channel_id,
                            roi_id,
                            frame_idx,
                            np.asarray(bg_frame[y0:y1, x0:x1], dtype=np.uint16),
                        )
                roi_frames += n_rois
                if progress_callback:
                    src = "raw" if not has_background else "fl_background"
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
                            "message": src,
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
