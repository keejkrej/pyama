from pathlib import Path
from threading import Event, Lock
from typing import Callable

import numpy as np
import zarr
from scipy.ndimage import (
    binary_closing,
    binary_fill_holes,
    binary_opening,
    uniform_filter,
)
from skimage.measure import label

from pyama.io.config import ensure_config
from pyama.types.microscopy import MicroscopyMetadata
from pyama.types.pipeline import ProcessingConfig
from pyama.utils.position import parse_position_range

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


def segment_frame_logstd(frame: np.ndarray) -> np.ndarray:
    frame_f = np.asarray(frame, dtype=np.float32)
    logstd = _compute_logstd_2d(frame_f)
    thresh = _threshold_by_histogram(logstd)
    binary = _morph_cleanup(logstd > thresh)
    return np.asarray(label(binary, connectivity=1), dtype=np.uint16)


def segment_cell(
    image: np.ndarray,
    out: np.ndarray,
    progress_callback: Callable[[int, int, str], None] | None = None,
    cancel_event=None,
) -> None:
    if image.ndim != 3 or out.ndim != 3:
        raise ValueError("image and out must be 3D arrays")
    if image.shape != out.shape:
        raise ValueError("image and out must have the same shape (T, H, W)")

    n_frames = image.shape[0]
    for time_idx in range(n_frames):
        if cancel_event and cancel_event.is_set():
            return
        segmented = segment_frame_logstd(image[time_idx])
        if out.dtype == bool:
            out[time_idx] = segmented > 0
        else:
            out[time_idx] = segmented.astype(out.dtype, copy=False)
        if progress_callback is not None:
            progress_callback(time_idx, n_frames, "Segmentation")


def segment_frame_cellpose(frame: np.ndarray) -> np.ndarray:
    try:
        from cellpose import models
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("cellpose is unavailable in this environment") from exc

    model = models.Cellpose(model_type="cyto")
    masks, _flows, _styles, _diams = model.eval(np.asarray(frame, dtype=np.float32), channels=[0, 0])
    return np.asarray(masks, dtype=np.uint16)


def _resolve_positions(metadata: MicroscopyMetadata, config: ProcessingConfig) -> list[int]:
    if config.params.positions.strip().lower() == "all":
        return list(range(metadata.n_positions))
    return parse_position_range(config.params.positions, length=metadata.n_positions)


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
    method = config.params.segmentation_method.value
    raw_zarr_path = output_dir / "raw.zarr"
    with _RAW_ZARR_OPEN_LOCK:
        store = zarr.open_group(raw_zarr_path, mode="a")

    if not config.channels:
        return {
            "segmentation_method": method,
            "segmented_datasets": 0,
            "segmentation_skipped_datasets": 0,
            "segmented_frames": 0,
            "segmentation_cancelled": False,
        }

    resolved_positions = positions_subset if positions_subset is not None else _resolve_positions(metadata, config)
    pc_channel = config.channels.get_pc_channel()
    if method == "logstd":
        segment_frame = segment_frame_logstd
    elif method == "cellpose":
        segment_frame = segment_frame_cellpose
    else:
        raise ValueError(f"Unknown segmentation method: {method}")

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
        raw_path = f"position/{position_id}/channel/{pc_channel}/raw"
        seg_path = f"position/{position_id}/channel/{pc_channel}/seg_labeled"

        try:
            raw_ds = store[raw_path]
        except KeyError as exc:
            raise FileNotFoundError(f"Missing raw dataset for segmentation: {raw_path}") from exc

        try:
            store[seg_path]
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
        except KeyError:
            pass

        seg_ds = store.create_array(
            name=seg_path,
            shape=(metadata.n_frames, metadata.height, metadata.width),
            chunks=(1, metadata.height, metadata.width),
            dtype="uint16",
            compressors=[zarr.codecs.BloscCodec(cname="zstd", clevel=5, shuffle="shuffle")],
        )
        seg_ds.attrs.update(
            {
                "source_file_path": str(metadata.file_path),
                "source_file_type": metadata.file_type,
                "position_id": int(position_id),
                "position_index": int(position_idx),
                "channel_id": int(pc_channel),
                "segmentation_method": method,
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
            seg_ds[time_idx] = segment_frame(frame)
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
        "segmentation_method": method,
        "segmented_datasets": segmented_datasets,
        "segmentation_skipped_datasets": skipped_datasets,
        "segmented_frames": segmented_frames,
        "segmentation_cancelled": cancelled,
    }


__all__ = [
    "run_segment_to_raw_zarr",
    "segment_cell",
    "segment_frame_cellpose",
    "segment_frame_logstd",
]
