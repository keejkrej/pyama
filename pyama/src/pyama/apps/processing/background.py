from pathlib import Path
from threading import Event, Lock
from typing import Callable

import numpy as np

from pyama.io.config import ensure_config
from pyama.io.zarr import open_rois_zarr
from pyama.types.io import MicroscopyMetadata
from pyama.types.processing import ProcessingConfig
from pyama.utils.processing import resolve_processing_positions

_ROIS_ZARR_OPEN_LOCK = Lock()


def _estimate_roi_background_value(raw_roi: np.ndarray) -> int:
    roi = np.asarray(raw_roi, dtype=np.uint16)
    if roi.size == 0:
        return 0

    q25 = float(np.percentile(roi, 25.0))
    samples = roi[roi <= q25]
    if int(samples.size) == 0:
        return 0
    background_value = float(np.mean(samples, dtype=np.float64))
    return int(np.clip(np.rint(background_value), 0.0, 65535.0))


def run_background_to_rois_zarr(
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
    if not config.channels or not config.channels.fl:
        return {
            "background_method": method,
            "background_datasets": 0,
            "background_skipped_datasets": 0,
            "background_frames": 0,
            "background_cancelled": False,
        }

    with _ROIS_ZARR_OPEN_LOCK:
        rois_store = open_rois_zarr(output_dir / "rois.zarr", mode="a")

    resolved_positions = (
        positions_subset
        if positions_subset is not None
        else resolve_processing_positions(metadata, config)
    )
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
        try:
            roi_ids = rois_store.read_roi_ids(position_id)
        except KeyError as exc:
            raise FileNotFoundError(
                f"Missing roi metadata for background estimation at position/{position_id}"
            ) from exc

        for channel_id in fl_channels:
            if cancel_event and cancel_event.is_set():
                cancelled = True
                break
            background_exists = (
                int(roi_ids.size) > 0
                and metadata.n_frames > 0
                and rois_store.dataset_exists(
                    rois_store.roi_background_frame_path(
                        position_id,
                        channel_id,
                        int(roi_ids[0]),
                        0,
                    )
                )
            )
            if background_exists:
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

            for frame_idx in range(metadata.n_frames):
                if cancel_event and cancel_event.is_set():
                    cancelled = True
                    break
                for roi_id in roi_ids:
                    try:
                        raw_roi = rois_store.read_roi_raw_frame(
                            position_id,
                            channel_id,
                            int(roi_id),
                            frame_idx,
                        )
                    except KeyError as exc:
                        raise FileNotFoundError(
                            "Missing roi raw tile for background estimation at "
                            f"position/{position_id}/channel/{channel_id}/roi/{int(roi_id)}/frame/{frame_idx}"
                        ) from exc
                    bg_value = _estimate_roi_background_value(raw_roi)
                    rois_store.write_roi_background_frame(
                        position_id,
                        channel_id,
                        int(roi_id),
                        frame_idx,
                        np.full(raw_roi.shape, bg_value, dtype=np.uint16),
                    )
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
                            "frame_index": frame_idx + 1,
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


__all__ = ["run_background_to_rois_zarr"]
