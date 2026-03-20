from pathlib import Path
from threading import Event, Lock
from typing import Callable

import numpy as np
import zarr
from skimage.measure import regionprops

from pyama.io.config import ensure_config
from pyama.types.microscopy import MicroscopyMetadata
from pyama.types.pipeline import ProcessingConfig
from pyama.utils.position import parse_position_range

_RAW_ZARR_OPEN_LOCK = Lock()
_ROIS_ZARR_OPEN_LOCK = Lock()


def _resolve_positions(metadata: MicroscopyMetadata, config: ProcessingConfig) -> list[int]:
    if config.params.positions.strip().lower() == "all":
        return list(range(metadata.n_positions))
    return parse_position_range(config.params.positions, length=metadata.n_positions)


def _regions_from_labeled(labeled: np.ndarray) -> dict[int, tuple[int, int, int, int]]:
    regions: dict[int, tuple[int, int, int, int]] = {}
    for prop in regionprops(labeled):
        regions[int(prop.label)] = (
            int(prop.bbox[0]),
            int(prop.bbox[1]),
            int(prop.bbox[2]),
            int(prop.bbox[3]),
        )
    return regions


def _build_roi_metadata(seg_tracked: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n_frames = seg_tracked.shape[0]
    regions_all = [_regions_from_labeled(seg_tracked[t]) for t in range(n_frames)]
    roi_ids = np.array(
        sorted({roi_id for regions in regions_all for roi_id in regions.keys()}),
        dtype=np.int32,
    )
    n_rois = int(roi_ids.size)

    roi_bboxes = np.zeros((n_rois, n_frames, 4), dtype=np.int32)
    roi_is_present = np.zeros((n_rois, n_frames), dtype=bool)
    if n_rois == 0:
        return roi_ids, roi_bboxes, roi_is_present

    for roi_idx, roi_id in enumerate(roi_ids):
        for frame_idx, regions in enumerate(regions_all):
            bbox = regions.get(int(roi_id))
            if bbox is None:
                continue
            roi_is_present[roi_idx, frame_idx] = True
            roi_bboxes[roi_idx, frame_idx] = np.array(
                [bbox[1], bbox[0], bbox[3] - bbox[1], bbox[2] - bbox[0]],
                dtype=np.int32,
            )

    return roi_ids, roi_bboxes, roi_is_present


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
        raw_store = zarr.open_group(raw_zarr_path, mode="a")
    with _ROIS_ZARR_OPEN_LOCK:
        rois_store = zarr.open_group(rois_zarr_path, mode="a")

    resolved_positions = positions_subset if positions_subset is not None else _resolve_positions(metadata, config)
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
        pos_prefix = f"position/{position_id}"
        meta_prefix = f"{pos_prefix}/metadata"
        roi_ids_path = f"{meta_prefix}/roi_ids"

        try:
            rois_store[roi_ids_path]
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
        except KeyError:
            pass

        seg_tracked_path = f"{pos_prefix}/channel/{pc_channel}/seg_tracked"
        try:
            seg_tracked = np.asarray(raw_store[seg_tracked_path][:], dtype=np.uint16)
        except KeyError as exc:
            raise FileNotFoundError(f"Missing seg_tracked dataset for roi extraction: {seg_tracked_path}") from exc

        roi_ids, roi_bboxes, roi_is_present = _build_roi_metadata(seg_tracked)
        n_rois = int(roi_ids.size)
        n_frames = int(seg_tracked.shape[0])

        rois_store.create_array(
            name=roi_ids_path,
            data=roi_ids,
            compressors=[zarr.codecs.BloscCodec(cname="zstd", clevel=5, shuffle="shuffle")],
        )
        rois_store.create_array(
            name=f"{meta_prefix}/roi_bboxes",
            data=roi_bboxes,
            compressors=[zarr.codecs.BloscCodec(cname="zstd", clevel=5, shuffle="shuffle")],
        )
        rois_store.create_array(
            name=f"{meta_prefix}/roi_is_present",
            data=roi_is_present,
            compressors=[zarr.codecs.BloscCodec(cname="zstd", clevel=5, shuffle="shuffle")],
        )

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
                rois_store.create_array(
                    name=f"{pos_prefix}/channel/{pc_channel}/roi/{roi_id}/seg_mask/frame/{frame_idx}",
                    data=np.asarray(seg_frame[y0:y1, x0:x1] == roi_id, dtype=bool),
                    compressors=[zarr.codecs.BloscCodec(cname="zstd", clevel=5, shuffle="shuffle")],
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
            raw_path = f"{pos_prefix}/channel/{channel_id}/raw"
            try:
                raw_ds = raw_store[raw_path]
            except KeyError as exc:
                raise FileNotFoundError(f"Missing raw dataset for roi extraction: {raw_path}") from exc
            bg_ds = None
            if channel_id in config.channels.fl:
                bg_path = f"{pos_prefix}/channel/{channel_id}/fl_background"
                try:
                    bg_ds = raw_store[bg_path]
                except KeyError:
                    bg_ds = None

            for frame_idx in range(n_frames):
                if cancel_event and cancel_event.is_set():
                    cancelled = True
                    break
                raw_frame = np.asarray(raw_ds[frame_idx], dtype=np.uint16)
                bg_frame = np.asarray(bg_ds[frame_idx], dtype=np.uint16) if bg_ds is not None else None
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

                    frame_prefix = f"{pos_prefix}/channel/{channel_id}/roi/{roi_id}"
                    frame_suffix = f"frame/{frame_idx}"
                    rois_store.create_array(
                        name=f"{frame_prefix}/raw/{frame_suffix}",
                        data=np.asarray(raw_frame[y0:y1, x0:x1], dtype=np.uint16),
                        compressors=[zarr.codecs.BloscCodec(cname="zstd", clevel=5, shuffle="shuffle")],
                    )
                    if bg_frame is not None:
                        rois_store.create_array(
                            name=f"{frame_prefix}/fl_background/{frame_suffix}",
                            data=np.asarray(bg_frame[y0:y1, x0:x1], dtype=np.uint16),
                            compressors=[zarr.codecs.BloscCodec(cname="zstd", clevel=5, shuffle="shuffle")],
                        )
                roi_frames += n_rois
                if progress_callback:
                    src = "raw" if bg_ds is None else "fl_background"
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
