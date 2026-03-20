from pathlib import Path
import math
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


def _resolve_positions(metadata: MicroscopyMetadata, config: ProcessingConfig) -> list[int]:
    if config.params.positions.strip().lower() == "all":
        return list(range(metadata.n_positions))
    return parse_position_range(config.params.positions, length=metadata.n_positions)


def _estimate_background(frame: np.ndarray, background_weight: float) -> np.ndarray:
    frame_f = frame.astype(np.float32, copy=False)
    p10 = float(np.percentile(frame_f, 10.0))
    bg_value = np.clip(p10 * background_weight, 0.0, 65535.0)
    return np.full(frame.shape, bg_value, dtype=np.uint16)


def estimate_background(
    image: np.ndarray,
    seg_labeled: np.ndarray,
    out: np.ndarray,
    progress_callback: Callable[[int, int, str], None] | None = None,
    *,
    background_weight: float = 1.0,
    cancel_event=None,
) -> None:
    del seg_labeled
    if image.ndim != 3 or out.ndim != 3:
        raise ValueError("image and out must be 3D arrays")
    if image.shape != out.shape:
        raise ValueError("image and out must have the same shape (T, H, W)")
    for time_idx in range(image.shape[0]):
        if cancel_event and cancel_event.is_set():
            return
        out[time_idx] = _estimate_background(image[time_idx], background_weight)
        if progress_callback is not None:
            progress_callback(time_idx, image.shape[0], "Background")


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

    roi_union_bboxes = np.zeros((n_rois, 4), dtype=np.int32)
    for roi_idx, roi_id in enumerate(roi_ids):
        y0s: list[int] = []
        x0s: list[int] = []
        y1s: list[int] = []
        x1s: list[int] = []
        for frame_idx, regions in enumerate(regions_all):
            bbox = regions.get(int(roi_id))
            if bbox is None:
                continue
            roi_is_present[roi_idx, frame_idx] = True
            y0s.append(bbox[0])
            x0s.append(bbox[1])
            y1s.append(bbox[2])
            x1s.append(bbox[3])
        if y0s:
            x0 = min(x0s)
            y0 = min(y0s)
            x1 = max(x1s)
            y1 = max(y1s)
            roi_union_bboxes[roi_idx] = np.array([x0, y0, x1 - x0, y1 - y0], dtype=np.int32)

    for roi_idx in range(n_rois):
        for frame_idx in range(n_frames):
            if roi_is_present[roi_idx, frame_idx]:
                roi_bboxes[roi_idx, frame_idx] = roi_union_bboxes[roi_idx]

    return roi_ids, roi_bboxes, roi_is_present


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
    background_weight: float,
    background_min_samples: int,
) -> int:
    roi = np.asarray(raw_frame[y0:y1, x0:x1], dtype=np.uint16)
    seg_roi = np.asarray(seg_frame[y0:y1, x0:x1], dtype=np.uint16)
    if roi.size == 0:
        return int(np.clip(np.percentile(np.asarray(raw_frame, dtype=np.float32), 10.0) * background_weight, 0.0, 65535.0))

    base_samples = roi[seg_roi != int(roi_id)]
    if int(base_samples.size) >= int(background_min_samples):
        return int(np.clip(float(np.median(base_samples)) * float(background_weight), 0.0, 65535.0))

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
        background_value = float(np.percentile(np.asarray(raw_frame, dtype=np.float32), 10.0))
    return int(np.clip(background_value * float(background_weight), 0.0, 65535.0))


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
        store = zarr.open_group(raw_zarr_path, mode="a")

    if not config.channels or not config.channels.fl:
        return {
            "background_method": method,
            "background_datasets": 0,
            "background_skipped_datasets": 0,
            "background_frames": 0,
            "background_cancelled": False,
        }

    resolved_positions = positions_subset if positions_subset is not None else _resolve_positions(metadata, config)
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
        seg_path = f"position/{position_id}/channel/{pc_channel}/seg_tracked"
        try:
            seg_tracked = np.asarray(store[seg_path][:], dtype=np.uint16)
        except KeyError as exc:
            raise FileNotFoundError(f"Missing seg_tracked dataset for background estimation: {seg_path}") from exc
        roi_ids, roi_bboxes, roi_is_present = _build_roi_metadata(seg_tracked)

        for channel_id in fl_channels:
            if cancel_event and cancel_event.is_set():
                cancelled = True
                break
            raw_path = f"position/{position_id}/channel/{channel_id}/raw"
            background_path = f"position/{position_id}/channel/{channel_id}/fl_background"

            try:
                raw_ds = store[raw_path]
            except KeyError as exc:
                raise FileNotFoundError(f"Missing raw dataset for background estimation: {raw_path}") from exc

            try:
                store[background_path]
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
            except KeyError:
                pass

            bg_ds = store.create_array(
                name=background_path,
                shape=(metadata.n_frames, metadata.height, metadata.width),
                chunks=(1, metadata.height, metadata.width),
                dtype="uint16",
                compressors=[zarr.codecs.BloscCodec(cname="zstd", clevel=5, shuffle="shuffle")],
            )
            bg_ds.attrs.update(
                {
                    "source_file_path": str(metadata.file_path),
                    "source_file_type": metadata.file_type,
                    "position_id": int(position_id),
                    "position_index": int(position_idx),
                    "channel_id": int(channel_id),
                    "background_method": method,
                    "background_weight": float(config.params.background_weight),
                    "n_frames": int(metadata.n_frames),
                    "height": int(metadata.height),
                    "width": int(metadata.width),
                }
            )

            for time_idx in range(metadata.n_frames):
                if cancel_event and cancel_event.is_set():
                    cancelled = True
                    break
                frame = np.asarray(raw_ds[time_idx], dtype=np.uint16)
                bg_frame = _estimate_background(frame, config.params.background_weight)
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
                        background_weight=float(config.params.background_weight),
                        background_min_samples=int(config.params.background_min_samples),
                    )
                    bg_frame[y0:y1, x0:x1] = np.uint16(bg_value)
                bg_ds[time_idx] = bg_frame
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


__all__ = ["estimate_background", "run_background_to_raw_zarr"]
