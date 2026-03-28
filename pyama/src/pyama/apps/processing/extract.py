from pathlib import Path
from threading import Event, Lock
from typing import Callable

import numpy as np
import pandas as pd

from pyama.io.config import ensure_config
from pyama.io.zarr import open_rois_zarr
from pyama.types.io import MicroscopyMetadata
from pyama.types.processing import ProcessingConfig
from pyama.utils.processing import resolve_processing_positions

_ROIS_ZARR_OPEN_LOCK = Lock()

_BASE_COLUMNS = ["position", "roi", "frame", "is_good", "x", "y", "w", "h"]


def _feature_column(feature_name: str, channel_id: int) -> str:
    return f"{feature_name}_c{channel_id}"


def _bbox_area(*, w: int, h: int) -> float:
    return float(max(0, int(w)) * max(0, int(h)))


def _pc_area(seg_mask: np.ndarray) -> float:
    return float(np.count_nonzero(seg_mask))


def _fl_intensity_total(
    raw_roi: np.ndarray,
    bg_roi: np.ndarray,
    *,
    background_weight: float,
    seg_mask: np.ndarray | None = None,
) -> float:
    corrected = raw_roi.astype(np.float32) - (
        float(background_weight) * bg_roi.astype(np.float32)
    )
    if seg_mask is None:
        return float(corrected.sum())
    return float(corrected[np.asarray(seg_mask, dtype=bool)].sum())


def list_phase_features() -> list[str]:
    return ["area"]


def list_fluorescence_features() -> list[str]:
    return ["intensity_total"]


def _resolve_feature_columns(
    config: ProcessingConfig,
) -> tuple[int, list[str], dict[int, list[str]], list[str]]:
    channels = config.channels
    if channels is None:
        raise ValueError("Extraction requires channel configuration")

    pc_channel = channels.get_pc_channel()
    pc_features = sorted(dict.fromkeys(channels.get_pc_features()))
    fl_feature_map = {
        channel_id: sorted(dict.fromkeys(features))
        for channel_id, features in channels.fl.items()
    }

    feature_columns = [
        _feature_column(feature_name, pc_channel)
        for feature_name in pc_features
    ]
    for channel_id in sorted(fl_feature_map):
        feature_columns.extend(
            _feature_column(feature_name, channel_id)
            for feature_name in fl_feature_map[channel_id]
        )
    return pc_channel, pc_features, fl_feature_map, feature_columns


def _add_pc_features(
    row: dict[str, float | int | bool],
    *,
    pc_channel: int,
    pc_features: list[str],
    bbox: np.ndarray,
) -> None:
    x, y, w, h = [int(v) for v in bbox]
    del x, y
    for feature_name in pc_features:
        row[_feature_column(feature_name, pc_channel)] = _bbox_area(w=w, h=h)


def _add_fluorescence_features(
    row: dict[str, float | int | bool],
    *,
    rois_store,
    position_id: int,
    roi_id: int,
    frame_idx: int,
    fl_feature_map: dict[int, list[str]],
    background_weight: float,
) -> None:
    for channel_id in sorted(fl_feature_map):
        for feature_name in fl_feature_map[channel_id]:
            col = _feature_column(feature_name, channel_id)
            try:
                raw_roi = np.asarray(
                    rois_store.read_roi_raw_frame(position_id, channel_id, roi_id, frame_idx),
                    dtype=np.float32,
                )
            except (KeyError, IndexError):
                row[col] = np.nan
                continue
            try:
                bg_roi = np.asarray(
                    rois_store.read_roi_background_frame(position_id, channel_id, roi_id, frame_idx),
                    dtype=np.float32,
                )
            except (KeyError, IndexError):
                bg_roi = np.zeros_like(raw_roi, dtype=np.float32)
            row[col] = _fl_intensity_total(
                raw_roi,
                bg_roi,
                background_weight=background_weight,
            )


def _build_extract_row(
    *,
    rois_store,
    position_id: int,
    roi_id: int,
    frame_idx: int,
    bbox: np.ndarray,
    pc_channel: int,
    pc_features: list[str],
    fl_feature_map: dict[int, list[str]],
    background_weight: float,
) -> dict[str, float | int | bool]:
    x, y, w, h = [int(v) for v in bbox]
    row: dict[str, float | int | bool] = {
        "position": position_id,
        "roi": roi_id,
        "frame": int(frame_idx),
        "is_good": True,
        "x": x,
        "y": y,
        "w": w,
        "h": h,
    }
    _add_pc_features(
        row,
        pc_channel=pc_channel,
        pc_features=pc_features,
        bbox=bbox,
    )
    _add_fluorescence_features(
        row,
        rois_store=rois_store,
        position_id=position_id,
        roi_id=roi_id,
        frame_idx=frame_idx,
        fl_feature_map=fl_feature_map,
        background_weight=background_weight,
    )
    return row


def _extract_position_rows(
    *,
    rois_store,
    position_id: int,
    pc_channel: int,
    pc_features: list[str],
    fl_feature_map: dict[int, list[str]],
    background_weight: float,
    n_frames: int,
    cancel_event: Event | None,
    progress_callback: Callable[[dict[str, int | str]], None] | None,
    worker_id: int,
    position_idx: int,
    position_progress_index: int,
    position_progress_total: int,
) -> tuple[list[dict[str, float | int | bool]], int, bool]:
    try:
        roi_ids = rois_store.read_roi_ids(position_id)
        roi_bboxes = rois_store.read_roi_bboxes(position_id)
    except KeyError as exc:
        raise FileNotFoundError(f"Missing roi metadata for extraction at position/{position_id}") from exc

    rows: list[dict[str, float | int | bool]] = []
    extracted_rows = 0
    n_rois = int(roi_ids.size)

    for roi_idx, roi_id in enumerate(roi_ids):
        roi_int = int(roi_id)
        for frame_idx in range(n_frames):
            if cancel_event and cancel_event.is_set():
                return rows, extracted_rows, True
            rows.append(
                _build_extract_row(
                    rois_store=rois_store,
                    position_id=position_id,
                    roi_id=roi_int,
                    frame_idx=frame_idx,
                    bbox=roi_bboxes[roi_idx],
                    pc_channel=pc_channel,
                    pc_features=pc_features,
                    fl_feature_map=fl_feature_map,
                    background_weight=background_weight,
                )
            )
            extracted_rows += 1
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
    return rows, extracted_rows, False


def _extract_trace_dataframe(
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
                    background_weight=background_weight,
                    seg_mask=mask,
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

    resolved_positions = (
        positions_subset
        if positions_subset is not None
        else resolve_processing_positions(metadata, config)
    )
    pc_channel, pc_features, fl_feature_map, feature_columns = _resolve_feature_columns(config)

    with _ROIS_ZARR_OPEN_LOCK:
        rois_store = open_rois_zarr(output_dir / "rois.zarr", mode="r")

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
        rows, position_rows, cancelled = _extract_position_rows(
            rois_store=rois_store,
            position_id=position_id,
            pc_channel=pc_channel,
            pc_features=pc_features,
            fl_feature_map=fl_feature_map,
            background_weight=background_weight,
            n_frames=int(metadata.n_frames),
            cancel_event=cancel_event,
            progress_callback=progress_callback,
            worker_id=worker_id,
            position_idx=position_idx,
            position_progress_index=position_progress_index,
            position_progress_total=position_progress_total,
        )
        extracted_rows += position_rows
        if cancelled:
            break

        df = pd.DataFrame(rows, columns=pd.Index([*_BASE_COLUMNS, *feature_columns]))
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


__all__ = ["list_fluorescence_features", "list_phase_features", "run_extract_to_csv"]
