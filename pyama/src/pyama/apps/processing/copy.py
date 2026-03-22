from pathlib import Path
from threading import Event, Lock
from typing import Callable

import numpy as np

from pyama.io import get_microscopy_frame
from pyama.io.config import ensure_config
from pyama.io.zarr import open_raw_zarr
from pyama.types.io import MicroscopyMetadata
from pyama.types.processing import ProcessingConfig
from pyama.utils.processing import resolve_processing_positions

_RAW_ZARR_OPEN_LOCK = Lock()

def _resolve_channels(config: ProcessingConfig) -> list[int]:
    if not config.channels:
        return []
    channel_ids: list[int] = [config.channels.get_pc_channel()]
    channel_ids.extend(sorted(config.channels.fl.keys()))
    return channel_ids


def run_copy_to_raw_zarr(
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
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_zarr_path = output_dir / "raw.zarr"
    with _RAW_ZARR_OPEN_LOCK:
        store = open_raw_zarr(raw_zarr_path, mode="a")

    resolved_positions = (
        positions_subset
        if positions_subset is not None
        else resolve_processing_positions(metadata, config)
    )
    channel_ids = _resolve_channels(config)
    copied_datasets = 0
    skipped_datasets = 0
    copied_frames = 0
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
        for channel_id in channel_ids:
            path = store.raw_path(position_id, channel_id)
            if store.dataset_exists(path):
                skipped_datasets += 1
                if progress_callback:
                    progress_callback(
                        {
                            "worker_id": worker_id,
                            "stage": "copy",
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

            store.create_raw_dataset(
                metadata=metadata,
                position_id=position_id,
                position_index=position_idx,
                channel_id=channel_id,
            )

            for time_idx in range(metadata.n_frames):
                if cancel_event and cancel_event.is_set():
                    cancelled = True
                    break
                frame = get_microscopy_frame(
                    img=reader,
                    position=position_idx,
                    channel=channel_id,
                    time=time_idx,
                    z=0,
                )
                store.write_raw_frame(position_id, channel_id, time_idx, np.asarray(frame, dtype=np.uint16))
                copied_frames += 1
                if progress_callback:
                    progress_callback(
                        {
                            "worker_id": worker_id,
                            "stage": "copy",
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
            copied_datasets += 1
        if cancelled:
            break

    return {
        "raw_zarr_path": str(raw_zarr_path),
        "selected_positions": len(resolved_positions),
        "selected_channels": len(channel_ids),
        "copied_datasets": copied_datasets,
        "skipped_datasets": skipped_datasets,
        "copied_frames": copied_frames,
        "cancelled": cancelled,
    }


__all__ = ["run_copy_to_raw_zarr"]
