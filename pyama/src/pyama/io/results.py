"""Processing-results discovery and trace path helpers."""

import logging
import re
from pathlib import Path

import pandas as pd

from pyama.io.config import get_config_path, load_config
from pyama.io.zarr import open_raw_zarr
from pyama.types.io import PositionArtifacts, ProcessingResults
from pyama.types.processing import Channels

logger = logging.getLogger(__name__)

_POSITION_TRACE_RE = re.compile(r"^position_(\d+)\.csv$")
_FEATURE_COLUMN_RE = re.compile(r"^(?P<feature>.+)_c(?P<channel>\d+)$")
_DATASET_REF_SEP = "::"


def resolve_trace_path(original_path: Path | None) -> Path | None:
    """Resolve trace CSV path, preferring the inspected trace when present."""
    if original_path is None:
        return None

    inspected_dir_path = original_path.parent / "inspected" / original_path.name
    if inspected_dir_path.exists():
        logger.debug("Using inspected traces file: %s", inspected_dir_path)
        return inspected_dir_path

    inspected_path = original_path.with_name(
        f"{original_path.stem}_inspected{original_path.suffix}"
    )
    if inspected_path.exists():
        logger.debug("Using inspected traces file: %s", inspected_path)
        return inspected_path

    return original_path


def get_trace_csv_path(
    results: ProcessingResults,
    position_id: int,
    *,
    prefer_inspected: bool = False,
) -> Path | None:
    traces_value = results.position_data.get(int(position_id), {}).get("traces")
    if not isinstance(traces_value, Path):
        return None
    if prefer_inspected:
        return resolve_trace_path(traces_value)
    return traces_value


def _dataset_ref(store_path: Path, dataset_path: str) -> str:
    return f"{store_path}{_DATASET_REF_SEP}{dataset_path}"


def _load_channels_from_config(config_path: Path | None) -> Channels | None:
    if config_path is None or not config_path.exists():
        return None
    try:
        config = load_config(config_path)
    except Exception:
        logger.warning("Failed to load processing config from %s", config_path, exc_info=True)
        return None
    return config.channels


def _infer_channels_from_traces(
    position_data: dict[int, PositionArtifacts],
) -> Channels | None:
    pc_features: dict[int, set[str]] = {}
    fl_features: dict[int, set[str]] = {}
    for payload in position_data.values():
        traces = payload.get("traces")
        if not isinstance(traces, Path):
            continue
        try:
            columns = list(pd.read_csv(traces, nrows=0).columns)
        except Exception:
            logger.warning("Failed to inspect traces file %s", traces, exc_info=True)
            continue
        for column in columns:
            match = _FEATURE_COLUMN_RE.match(column)
            if match is None:
                continue
            feature = str(match.group("feature"))
            channel = int(match.group("channel"))
            if feature == "area":
                pc_features.setdefault(channel, set()).add(feature)
            else:
                fl_features.setdefault(channel, set()).add(feature)

    pc_channel = min(pc_features) if pc_features else None
    if pc_channel is None and not fl_features:
        return None

    try:
        return Channels(
            pc={} if pc_channel is None else {pc_channel: sorted(pc_features[pc_channel])},
            fl={
                channel: sorted(features)
                for channel, features in sorted(fl_features.items())
            },
        )
    except ValueError:
        if not fl_features:
            return None
        logger.warning("Skipping inferred channels because no phase-contrast channel was found")
        return None


def _scan_raw_zarr(raw_zarr_path: Path) -> dict[int, PositionArtifacts]:
    store = open_raw_zarr(raw_zarr_path, mode="r")
    position_data: dict[int, PositionArtifacts] = {}

    for position_id in store.list_position_ids():
        payload = position_data.setdefault(position_id, {})
        for channel_id in store.list_channel_ids(position_id):
            base = f"position/{position_id}/channel/{channel_id}"
            for dataset_name, key_prefix in (
                ("raw", "raw"),
                ("seg_labeled", "seg_labeled"),
                ("seg_tracked", "seg_tracked"),
                ("fl_background", "fl_background"),
            ):
                if store.dataset_exists(f"{base}/{dataset_name}"):
                    payload[f"{key_prefix}_ch_{channel_id}"] = _dataset_ref(
                        raw_zarr_path, f"{base}/{dataset_name}"
                    )
    return position_data


def _scan_traces_dir(traces_dir: Path) -> dict[int, PositionArtifacts]:
    position_data: dict[int, PositionArtifacts] = {}
    inspected_dir = traces_dir / "inspected"
    for csv_path in sorted(traces_dir.glob("position_*.csv")):
        match = _POSITION_TRACE_RE.match(csv_path.name)
        if match is None:
            continue
        position_id = int(match.group(1))
        payload = position_data.setdefault(position_id, {})
        payload["traces"] = csv_path
        inspected_path = inspected_dir / csv_path.name
        if inspected_path.exists():
            payload["traces_inspected"] = inspected_path
    return position_data


def scan_processing_results(project_dir: Path) -> ProcessingResults:
    project_dir = project_dir.expanduser()
    if not project_dir.exists() or not project_dir.is_dir():
        raise FileNotFoundError(f"Processing results folder does not exist: {project_dir}")

    config_path = get_config_path(project_dir)
    raw_zarr_path = project_dir / "raw.zarr"
    rois_zarr_path = project_dir / "rois.zarr"
    traces_dir = project_dir / "traces"
    traces_merged_dir = project_dir / "traces_merged"

    position_data: dict[int, PositionArtifacts] = {}
    if raw_zarr_path.exists():
        position_data.update(_scan_raw_zarr(raw_zarr_path))
    if traces_dir.exists():
        for position_id, payload in _scan_traces_dir(traces_dir).items():
            position_data.setdefault(position_id, {}).update(payload)

    if not position_data:
        raise FileNotFoundError(
            f"No recognizable processing outputs found in {project_dir}. "
            "Expected raw.zarr and/or traces/position_*.csv."
        )

    channels = _load_channels_from_config(config_path)
    if channels is None:
        channels = _infer_channels_from_traces(position_data)

    return ProcessingResults(
        project_path=project_dir,
        n_positions=len(position_data),
        position_data=position_data,
        channels=channels,
        config_path=config_path if config_path.exists() else None,
        raw_zarr_path=raw_zarr_path if raw_zarr_path.exists() else None,
        rois_zarr_path=rois_zarr_path if rois_zarr_path.exists() else None,
        traces_dir=traces_dir if traces_dir.exists() else None,
        traces_merged_dir=traces_merged_dir if traces_merged_dir.exists() else None,
    )


__all__ = [
    "get_trace_csv_path",
    "resolve_trace_path",
    "scan_processing_results",
]
