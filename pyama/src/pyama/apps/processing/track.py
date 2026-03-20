from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock
from typing import Callable

import numpy as np
import zarr
from scipy.optimize import linear_sum_assignment
from skimage.measure import regionprops

from pyama.io.config import ensure_config
from pyama.types.microscopy import MicroscopyMetadata
from pyama.types.pipeline import ProcessingConfig
from pyama.utils.position import parse_position_range

_RAW_ZARR_OPEN_LOCK = Lock()


@dataclass
class Region:
    bbox: tuple[int, int, int, int]
    coords: np.ndarray


LabeledRegions = dict[int, Region]
Trace = dict[int, int]
TraceMap = dict[int, int]


@dataclass
class IterationState:
    traces: list[Trace]
    prev_map: TraceMap
    prev_regions: LabeledRegions


def _regions_from_labeled(labeled: np.ndarray) -> LabeledRegions:
    regions: LabeledRegions = {}
    for prop in regionprops(labeled):
        regions[int(prop.label)] = Region(
            bbox=(
                int(prop.bbox[0]),
                int(prop.bbox[1]),
                int(prop.bbox[2]),
                int(prop.bbox[3]),
            ),
            coords=prop.coords,
        )
    return regions


def _iou_from_bboxes(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ay0, ax0, ay1, ax1 = a
    by0, bx0, by1, bx1 = b
    inter_y0 = max(ay0, by0)
    inter_x0 = max(ax0, bx0)
    inter_y1 = min(ay1, by1)
    inter_x1 = min(ax1, bx1)
    inter_h = inter_y1 - inter_y0
    inter_w = inter_x1 - inter_x0
    if inter_h <= 0 or inter_w <= 0:
        return 0.0
    inter_area = int(inter_h) * int(inter_w)
    a_area = max(0, (ay1 - ay0) * (ax1 - ax0))
    b_area = max(0, (by1 - by0) * (bx1 - bx0))
    union = a_area + b_area - inter_area
    if union <= 0:
        return 0.0
    return float(inter_area) / float(union)


def _build_cost_matrix(
    prev_regions: list[Region],
    curr_regions: list[Region],
    min_iou: float,
) -> tuple[np.ndarray, np.ndarray]:
    n_prev = len(prev_regions)
    n_curr = len(curr_regions)
    if n_prev == 0 or n_curr == 0:
        return np.ones((n_prev, n_curr), dtype=float), np.zeros((n_prev, n_curr), dtype=bool)

    cost = np.ones((n_prev, n_curr), dtype=float)
    valid = np.zeros((n_prev, n_curr), dtype=bool)
    for i, prev_region in enumerate(prev_regions):
        for j, curr_region in enumerate(curr_regions):
            iou = _iou_from_bboxes(prev_region.bbox, curr_region.bbox)
            if iou >= min_iou:
                cost[i, j] = 1.0 - iou
                valid[i, j] = True
    return cost, valid


def _process_frame(state: IterationState, regions_all: list[LabeledRegions], min_iou: float, frame: int) -> None:
    prev_labels = list(state.prev_map.keys())
    prev_regions = [state.prev_regions[label] for label in prev_labels]
    curr_regions_by_label = regions_all[frame]
    curr_labels = list(curr_regions_by_label.keys())
    curr_regions = list(curr_regions_by_label.values())

    cost, valid = _build_cost_matrix(prev_regions, curr_regions, min_iou=min_iou)
    if cost.size == 0:
        state.prev_map = {}
        state.prev_regions = {}
        return

    row_ind, col_ind = linear_sum_assignment(cost)
    new_prev_map: TraceMap = {}
    new_prev_regions: LabeledRegions = {}
    for row, col in zip(row_ind, col_ind):
        if not valid[row, col]:
            continue
        if row >= len(prev_labels):
            continue
        prev_label = prev_labels[row]
        curr_label = curr_labels[col]
        trace_id = state.prev_map.get(prev_label)
        if trace_id is None:
            continue
        state.traces[trace_id][frame] = curr_label
        new_prev_map[curr_label] = trace_id
        new_prev_regions[curr_label] = curr_regions[col]

    state.prev_map = new_prev_map
    state.prev_regions = new_prev_regions


def track_cell(
    image: np.ndarray,
    out: np.ndarray,
    min_iou: float = 0.1,
    progress_callback: Callable[[int, int, str], None] | None = None,
    cancel_event=None,
) -> None:
    if image.ndim != 3 or out.ndim != 3:
        raise ValueError("image and out must be 3D arrays")
    if image.shape != out.shape:
        raise ValueError("image and out must have the same shape (T, H, W)")

    image = image.astype(np.uint16, copy=False)
    out = out.astype(np.uint16, copy=False)
    n_frames = image.shape[0]

    regions_all: list[LabeledRegions] = []
    for t in range(n_frames):
        if cancel_event and cancel_event.is_set():
            return
        regions_all.append(_regions_from_labeled(image[t]))

    if not regions_all:
        return
    seed_frame = 0
    while seed_frame < n_frames and not regions_all[seed_frame]:
        seed_frame += 1
    if seed_frame >= n_frames:
        return

    init_labels = list(regions_all[seed_frame].keys())
    state = IterationState(
        traces=[{seed_frame: label} for label in init_labels],
        prev_map={label: idx for idx, label in enumerate(init_labels)},
        prev_regions=regions_all[seed_frame],
    )

    for t in range(seed_frame + 1, n_frames):
        if cancel_event and cancel_event.is_set():
            return
        _process_frame(state=state, regions_all=regions_all, min_iou=min_iou, frame=t)
        if progress_callback is not None:
            progress_callback(t, n_frames, "Tracking")

    out[...] = 0
    for roi_id, trace in enumerate(state.traces, start=1):
        for frame_idx, label in trace.items():
            region = regions_all[frame_idx].get(label)
            if region is None:
                continue
            ys = region.coords[:, 0]
            xs = region.coords[:, 1]
            out[frame_idx, ys, xs] = roi_id


def _resolve_positions(metadata: MicroscopyMetadata, config: ProcessingConfig) -> list[int]:
    if config.params.positions.strip().lower() == "all":
        return list(range(metadata.n_positions))
    return parse_position_range(config.params.positions, length=metadata.n_positions)


def run_track_to_raw_zarr(
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
    method = config.params.tracking_method.value
    raw_zarr_path = output_dir / "raw.zarr"
    with _RAW_ZARR_OPEN_LOCK:
        store = zarr.open_group(raw_zarr_path, mode="a")

    if not config.channels:
        return {
            "tracking_method": method,
            "tracked_datasets": 0,
            "tracking_skipped_datasets": 0,
            "tracked_frames": 0,
            "tracking_cancelled": False,
        }

    resolved_positions = positions_subset if positions_subset is not None else _resolve_positions(metadata, config)
    pc_channel = config.channels.get_pc_channel()
    if method not in {"iou", "btrack"}:
        raise ValueError(f"Unknown tracking method: {method}")

    tracked_datasets = 0
    skipped_datasets = 0
    tracked_frames = 0
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
        seg_path = f"position/{position_id}/channel/{pc_channel}/seg_labeled"
        tracked_path = f"position/{position_id}/channel/{pc_channel}/seg_tracked"

        try:
            seg_ds = store[seg_path]
        except KeyError as exc:
            raise FileNotFoundError(f"Missing seg_labeled dataset for tracking: {seg_path}") from exc

        try:
            store[tracked_path]
            skipped_datasets += 1
            if progress_callback:
                progress_callback(
                    {
                        "worker_id": worker_id,
                        "stage": "track",
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

        tracked_ds = store.create_array(
            name=tracked_path,
            shape=(metadata.n_frames, metadata.height, metadata.width),
            chunks=(1, metadata.height, metadata.width),
            dtype="uint16",
            compressors=[zarr.codecs.BloscCodec(cname="zstd", clevel=5, shuffle="shuffle")],
        )
        tracked_ds.attrs.update(
            {
                "source_file_path": str(metadata.file_path),
                "source_file_type": metadata.file_type,
                "position_id": int(position_id),
                "position_index": int(position_idx),
                "channel_id": int(pc_channel),
                "tracking_method": method,
                "n_frames": int(metadata.n_frames),
                "height": int(metadata.height),
                "width": int(metadata.width),
            }
        )

        seg = np.asarray(seg_ds[:], dtype=np.uint16)
        tracked = np.zeros_like(seg, dtype=np.uint16)

        def _track_progress_callback(frame_idx: int, frame_total: int, _message: str) -> None:
            nonlocal tracked_frames
            tracked_frames += 1
            if progress_callback:
                progress_callback(
                    {
                        "worker_id": worker_id,
                        "stage": "track",
                        "channel_id": pc_channel,
                        "position_id": position_idx,
                        "position_index": position_progress_index,
                        "position_total": position_progress_total,
                        "frame_index": frame_idx + 1,
                        "frame_total": frame_total,
                        "message": "",
                    }
                )

        track_cell(
            image=seg,
            out=tracked,
            progress_callback=_track_progress_callback,
            cancel_event=cancel_event,
        )
        if cancel_event and cancel_event.is_set():
            cancelled = True
            break

        tracked_ds[:] = tracked
        tracked_datasets += 1

    return {
        "tracking_method": method,
        "tracked_datasets": tracked_datasets,
        "tracking_skipped_datasets": skipped_datasets,
        "tracked_frames": tracked_frames,
        "tracking_cancelled": cancelled,
    }


__all__ = ["run_track_to_raw_zarr", "track_cell"]
