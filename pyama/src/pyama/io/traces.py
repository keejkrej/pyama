"""Trace-file discovery and inspection helpers."""

import re
from pathlib import Path

import pandas as pd

from pyama.io.csv import (
    extract_all_rois_data,
    get_dataframe,
    update_roi_quality,
    write_dataframe,
)
from pyama.io.results import resolve_trace_path
from pyama.types.io import ProcessingResults
from pyama.types.visualization import RoiOverlay

POSITION_FILE_PATTERN = re.compile(r"^position_(\d+)\.csv$")
_FEATURE_COLUMN_RE = re.compile(r"^(?P<feature>.+)_c(?P<channel>\d+)$")


def collect_position_trace_files(
    traces_dir: Path,
    position_ids: set[int] | None = None,
) -> dict[int, Path]:
    selected: dict[int, Path] = {}
    inspected_dir = traces_dir / "inspected"

    for candidate in sorted(traces_dir.glob("position_*.csv")):
        match = POSITION_FILE_PATTERN.match(candidate.name)
        if match is None:
            continue
        position_id = int(match.group(1))
        if position_ids is not None and position_id not in position_ids:
            continue
        selected[position_id] = candidate

    if inspected_dir.exists():
        for candidate in sorted(inspected_dir.glob("position_*.csv")):
            match = POSITION_FILE_PATTERN.match(candidate.name)
            if match is None:
                continue
            position_id = int(match.group(1))
            if position_ids is not None and position_id not in position_ids:
                continue
            selected[position_id] = candidate

    return selected


def infer_channel_feature_config(
    results: ProcessingResults,
) -> list[tuple[int, list[str]]]:
    config: dict[int, set[str]] = {}
    for traces_info in results.position_data.values():
        traces_path = traces_info.get("traces")
        if not isinstance(traces_path, Path):
            continue
        columns = list(pd.read_csv(traces_path, nrows=0).columns)
        for column in columns:
            match = _FEATURE_COLUMN_RE.match(column)
            if match is None:
                continue
            feature = str(match.group("feature"))
            channel = int(match.group("channel"))
            config.setdefault(channel, set()).add(feature)
    return [
        (channel, sorted(features))
        for channel, features in sorted(config.items(), key=lambda item: item[0])
        if features
    ]


def load_trace_bundle(trace_path: Path) -> dict[str, object]:
    """Load a trace CSV and return the serialized bundle expected by the GUI."""
    csv_path = resolve_trace_path(trace_path)
    if csv_path is None:
        raise ValueError(f"Invalid trace path: {trace_path}")
    df = get_dataframe(csv_path)
    base_fields = ["position"] + [
        field.name for field in RoiOverlay.__dataclass_fields__.values()
    ]
    missing = [column for column in base_fields if column not in df.columns]
    if missing:
        raise ValueError(
            f"Trace CSV is missing required columns: {', '.join(sorted(missing))}"
        )
    base_columns = [column for column in base_fields if column in df.columns]
    feature_columns = [
        column for column in df.columns if column not in set(base_fields)
    ]
    if not feature_columns:
        raise ValueError("Trace CSV contains no feature columns.")
    processing_df = df[list(dict.fromkeys(base_columns + feature_columns))].copy()
    cells_data = extract_all_rois_data(processing_df)
    return {
        "source_path": str(trace_path),
        "resolved_path": str(csv_path),
        "feature_options": sorted(feature_columns),
        "cells": {
            cell_id: {
                "quality": bool(data["quality"]),
                "features": {
                    key: value.tolist() if hasattr(value, "tolist") else list(value)
                    for key, value in data["features"].items()
                },
                "positions": {
                    key: value.tolist() if hasattr(value, "tolist") else list(value)
                    for key, value in data["positions"].items()
                },
            }
            for cell_id, data in cells_data.items()
        },
    }


def write_trace_quality_update(
    resolved_trace_path: Path,
    quality_by_roi: dict[str, bool],
) -> Path:
    """Persist GUI-edited ROI quality flags to the inspected trace CSV."""
    df = get_dataframe(resolved_trace_path)
    updated_quality = pd.DataFrame(
        [(int(roi), bool(is_good)) for roi, is_good in quality_by_roi.items()],
        columns=pd.Index(["roi", "is_good"]),
    )
    updated_df = update_roi_quality(df, updated_quality)
    if resolved_trace_path.name.endswith("_inspected.csv"):
        save_path = resolved_trace_path
    else:
        save_path = resolved_trace_path.with_name(
            f"{resolved_trace_path.stem}_inspected{resolved_trace_path.suffix}"
        )
    write_dataframe(updated_df, save_path)
    return save_path


__all__ = [
    "POSITION_FILE_PATTERN",
    "collect_position_trace_files",
    "infer_channel_feature_config",
    "load_trace_bundle",
    "write_trace_quality_update",
]
