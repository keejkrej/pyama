from pathlib import Path
from threading import Event, Lock
from typing import Callable

import numpy as np
import pandas as pd
import zarr

from pyama.io.config import ensure_config
from pyama.types.microscopy import MicroscopyMetadata
from pyama.types.pipeline import ProcessingConfig
from pyama.utils.position import parse_position_range

_ROIS_ZARR_OPEN_LOCK = Lock()

_BASE_COLUMNS = ["position", "roi", "frame", "is_good", "x", "y", "w", "h"]


def _resolve_positions(metadata: MicroscopyMetadata, config: ProcessingConfig) -> list[int]:
    if config.params.positions.strip().lower() == "all":
        return list(range(metadata.n_positions))
    return parse_position_range(config.params.positions, length=metadata.n_positions)


def _feature_column(feature_name: str, channel_id: int) -> str:
    return f"{feature_name}_c{channel_id}"


def _pc_area(seg_mask: np.ndarray) -> float:
    return float(np.count_nonzero(seg_mask))


def _fl_intensity_total(
    raw_roi: np.ndarray,
    bg_roi: np.ndarray,
    seg_mask: np.ndarray,
    *,
    background_weight: float,
) -> float:
    corrected = raw_roi.astype(np.float32) - (
        float(background_weight) * bg_roi.astype(np.float32)
    )
    return float(corrected[np.asarray(seg_mask, dtype=bool)].sum())


def list_phase_features() -> list[str]:
    return ["area"]


def list_fluorescence_features() -> list[str]:
    return ["intensity_total"]


def extract_trace(
    image: np.ndarray,
    seg_labeled: np.ndarray,
    background: np.ndarray,
    progress_callback: Callable[[int, int, str], None] | None = None,
    features: list[str] | None = None,
    cancel_event=None,
    background_weight: float = 1.0,
) -> pd.DataFrame:
    if image.ndim != 3 or seg_labeled.ndim != 3 or background.ndim != 3:
        raise ValueError("image, seg_labeled, and background must be 3D arrays")
    if image.shape != seg_labeled.shape or image.shape != background.shape:
        raise ValueError("image, seg_labeled, and background must have the same shape")

    feature_names = list(features or ["area", "intensity_total"])
    rows: list[dict[str, float | int | bool]] = []
    n_frames = image.shape[0]
    for frame_idx in range(n_frames):
        if cancel_event and cancel_event.is_set():
            break
        roi_ids = np.unique(seg_labeled[frame_idx])
        roi_ids = roi_ids[roi_ids > 0]
        for roi_id in roi_ids:
            mask = seg_labeled[frame_idx] == roi_id
            ys, xs = np.where(mask)
            if ys.size == 0 or xs.size == 0:
                continue
            x0 = int(xs.min())
            y0 = int(ys.min())
            x1 = int(xs.max()) + 1
            y1 = int(ys.max()) + 1
            row: dict[str, float | int | bool] = {
                "position": 0,
                "roi": int(roi_id),
                "frame": int(frame_idx),
                "is_good": True,
                "x": x0,
                "y": y0,
                "w": x1 - x0,
                "h": y1 - y0,
            }
            if "area" in feature_names:
                row["area_c0"] = _pc_area(mask)
            if "intensity_total" in feature_names:
                row["intensity_total_c1"] = _fl_intensity_total(
                    image[frame_idx],
                    background[frame_idx],
                    mask,
                    background_weight=background_weight,
                )
            rows.append(row)
        if progress_callback is not None:
            progress_callback(frame_idx, n_frames, "Extract")
    return pd.DataFrame(rows)


def run_extract_to_csv(
    *,
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
            "extract_method": method,
            "extracted_positions": 0,
            "extract_skipped_positions": 0,
            "extracted_rows": 0,
            "extract_cancelled": False,
        }

    resolved_positions = positions_subset if positions_subset is not None else _resolve_positions(metadata, config)
    pc_channel = config.channels.get_pc_channel()
    pc_features = sorted(dict.fromkeys(config.channels.get_pc_features()))
    fl_feature_map = {
        channel_id: sorted(dict.fromkeys(features))
        for channel_id, features in config.channels.fl.items()
    }

    feature_columns: list[str] = []
    for feature_name in pc_features:
        feature_columns.append(_feature_column(feature_name, pc_channel))
    for channel_id in sorted(fl_feature_map):
        for feature_name in fl_feature_map[channel_id]:
            feature_columns.append(_feature_column(feature_name, channel_id))

    with _ROIS_ZARR_OPEN_LOCK:
        rois_store = zarr.open_group(output_dir / "rois.zarr", mode="r")

    extracted_positions = 0
    skipped_positions = 0
    extracted_rows = 0
    cancelled = False
    background_weight = float(config.params.background_weight)

    for pos_offset, position_idx in enumerate(resolved_positions):
        if cancel_event and cancel_event.is_set():
            cancelled = True
            break

        position_progress_index = (
            global_position_lookup[position_idx] if global_position_lookup is not None else pos_offset + 1
        )
        position_progress_total = global_position_total if global_position_total is not None else len(resolved_positions)
        position_id = int(metadata.position_list[position_idx])
        traces_dir = output_dir / "traces"
        traces_dir.mkdir(parents=True, exist_ok=True)
        output_csv = traces_dir / f"position_{position_id}.csv"
        if output_csv.exists():
            skipped_positions += 1
            if progress_callback:
                progress_callback(
                    {
                        "worker_id": worker_id,
                        "stage": "extract",
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

        metadata_prefix = f"position/{position_id}/metadata"
        try:
            roi_ids = np.asarray(rois_store[f"{metadata_prefix}/roi_ids"][:], dtype=np.int32)
            roi_bboxes = np.asarray(rois_store[f"{metadata_prefix}/roi_bboxes"][:], dtype=np.int32)
            roi_is_present = np.asarray(rois_store[f"{metadata_prefix}/roi_is_present"][:], dtype=bool)
        except KeyError as exc:
            raise FileNotFoundError(f"Missing roi metadata for extraction at position/{position_id}") from exc

        rows: list[dict[str, float | int | bool]] = []
        n_frames = int(roi_is_present.shape[1]) if roi_is_present.ndim == 2 else 0
        n_rois = int(roi_ids.size)
        for roi_idx, roi_id in enumerate(roi_ids):
            roi_int = int(roi_id)
            for frame_idx in range(n_frames):
                if cancel_event and cancel_event.is_set():
                    cancelled = True
                    break
                if not bool(roi_is_present[roi_idx, frame_idx]):
                    continue

                x, y, w, h = [int(v) for v in roi_bboxes[roi_idx, frame_idx]]
                row: dict[str, float | int | bool] = {
                    "position": position_id,
                    "roi": roi_int,
                    "frame": int(frame_idx),
                    "is_good": True,
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                }
                seg_mask: np.ndarray | None = None
                seg_mask_loaded = False

                def _load_seg_mask() -> np.ndarray | None:
                    nonlocal seg_mask, seg_mask_loaded
                    if seg_mask_loaded:
                        return seg_mask
                    try:
                        seg_mask = np.asarray(
                            rois_store[
                                f"position/{position_id}/channel/{pc_channel}/roi/{roi_int}/seg_mask/frame/{frame_idx}"
                            ][:],
                            dtype=bool,
                        )
                    except (KeyError, IndexError):
                        seg_mask = None
                    seg_mask_loaded = True
                    return seg_mask

                for feature_name in pc_features:
                    col = _feature_column(feature_name, pc_channel)
                    seg_mask = _load_seg_mask()
                    row[col] = np.nan if seg_mask is None else _pc_area(seg_mask)

                for channel_id in sorted(fl_feature_map):
                    for feature_name in fl_feature_map[channel_id]:
                        col = _feature_column(feature_name, channel_id)
                        try:
                            raw_roi = np.asarray(
                                rois_store[
                                    f"position/{position_id}/channel/{channel_id}/roi/{roi_int}/raw/frame/{frame_idx}"
                                ][:],
                                dtype=np.float32,
                            )
                        except (KeyError, IndexError):
                            row[col] = np.nan
                            continue
                        try:
                            bg_roi = np.asarray(
                                rois_store[
                                    f"position/{position_id}/channel/{channel_id}/roi/{roi_int}/fl_background/frame/{frame_idx}"
                                ][:],
                                dtype=np.float32,
                            )
                        except (KeyError, IndexError):
                            bg_roi = np.zeros_like(raw_roi, dtype=np.float32)
                        seg_mask = _load_seg_mask()
                        if seg_mask is None or seg_mask.shape != raw_roi.shape:
                            row[col] = np.nan
                            continue
                        row[col] = _fl_intensity_total(
                            raw_roi,
                            bg_roi,
                            seg_mask,
                            background_weight=background_weight,
                        )

                rows.append(row)
                extracted_rows += 1
            if cancelled:
                break
            if progress_callback:
                progress_callback(
                    {
                        "worker_id": worker_id,
                        "stage": "extract",
                        "channel_id": pc_channel,
                        "position_id": position_idx,
                        "position_index": position_progress_index,
                        "position_total": position_progress_total,
                        "frame_index": roi_idx + 1,
                        "frame_total": n_rois,
                        "message": "",
                    }
                )
        if cancelled:
            break

        df = pd.DataFrame(rows, columns=[*_BASE_COLUMNS, *feature_columns])
        if not df.empty:
            df.sort_values(["roi", "frame"], inplace=True)
        df.to_csv(output_csv, index=False, float_format="%.6f")
        extracted_positions += 1

    return {
        "extract_method": method,
        "extracted_positions": extracted_positions,
        "extract_skipped_positions": skipped_positions,
        "extracted_rows": extracted_rows,
        "extract_cancelled": cancelled,
    }


__all__ = [
    "extract_trace",
    "list_fluorescence_features",
    "list_phase_features",
    "run_extract_to_csv",
]
