"""Folder-based processing results discovery helpers."""

import logging
import re
from pathlib import Path

import pandas as pd

from pyama.types.io import ProcessingResults
from pyama.types.processing import ChannelSelection, Channels

logger = logging.getLogger(__name__)

_FOV_DIR_RE = re.compile(r"^fov_(\d+)$")
_TRACES_RE = re.compile(r"_traces(?:_inspected)?\.csv$")
_CHANNEL_KEY_RE = re.compile(
    r"_(pc|seg|seg_labeled|fl|fl_corrected|fl_background)_ch_(\d+)\.npy$"
)
_FEATURE_COLUMN_RE = re.compile(r"^(?P<feature>.+)_ch_(?P<channel>\d+)$")
_BASE_TRACE_COLUMNS = {
    "frame",
    "time",
    "fov",
    "cell",
    "good",
    "position_x",
    "position_y",
    "bbox_x",
    "bbox_y",
    "bbox_w",
    "bbox_h",
}


def scan_processing_results(project_dir: Path) -> ProcessingResults:
    """Scan a processing output folder and build a ProcessingResults object."""
    project_dir = project_dir.expanduser()
    if not project_dir.exists() or not project_dir.is_dir():
        raise FileNotFoundError(f"Processing results folder does not exist: {project_dir}")

    fov_data: dict[int, dict[str, Path]] = {}
    inferred_channels = Channels()

    for fov_dir in sorted(project_dir.iterdir()):
        if not fov_dir.is_dir():
            continue
        match = _FOV_DIR_RE.match(fov_dir.name)
        if match is None:
            continue

        fov = int(match.group(1))
        files = _scan_fov_dir(fov_dir)
        if not files:
            continue

        fov_data[fov] = files
        _merge_channels(inferred_channels, _infer_channels_from_fov(files))

    if not fov_data:
        raise FileNotFoundError(f"No recognizable processing outputs found in {project_dir}")

    return ProcessingResults(
        project_path=project_dir,
        n_fov=len(fov_data),
        fov_data=fov_data,
        channels=inferred_channels.to_raw(),
        time_units="min",
        extra={},
    )


def get_trace_csv_path(processing_results: ProcessingResults, fov: int) -> Path | None:
    """Return the unified trace CSV path for a given FOV, if present."""
    return processing_results["fov_data"].get(fov, {}).get("traces")


def _scan_fov_dir(fov_dir: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for file_path in sorted(fov_dir.iterdir()):
        if not file_path.is_file():
            continue

        if file_path.suffix == ".csv" and _TRACES_RE.search(file_path.name):
            if file_path.name.endswith("_inspected.csv"):
                continue
            files["traces"] = file_path
            continue

        if file_path.suffix != ".npy":
            continue

        match = _CHANNEL_KEY_RE.search(file_path.name)
        if match is None:
            continue

        prefix, channel = match.groups()
        key = f"{prefix}_ch_{int(channel)}"
        files[key] = file_path

    return files


def _infer_channels_from_fov(fov_files: dict[str, Path]) -> Channels:
    feature_map: dict[int, set[str]] = {}
    traces_path = fov_files.get("traces")
    if traces_path is not None:
        try:
            columns = list(pd.read_csv(traces_path, nrows=0).columns)
        except Exception as exc:
            logger.warning("Failed to inspect trace CSV %s: %s", traces_path, exc)
            columns = []

        for column in columns:
            if column in _BASE_TRACE_COLUMNS:
                continue
            match = _FEATURE_COLUMN_RE.match(column)
            if match is None:
                continue
            feature = match.group("feature")
            channel = int(match.group("channel"))
            feature_map.setdefault(channel, set()).add(feature)

    pc_channel: int | None = None
    if any(key.startswith(("pc_ch_", "seg_ch_", "seg_labeled_ch_")) for key in fov_files):
        pc_candidates = {
            int(key.rsplit("_", 1)[-1])
            for key in fov_files
            if key.startswith(("pc_ch_", "seg_ch_", "seg_labeled_ch_"))
        }
        if pc_candidates:
            pc_channel = min(pc_candidates)

    fl_channels = {
        int(key.rsplit("_", 1)[-1])
        for key in fov_files
        if key.startswith(("fl_ch_", "fl_corrected_ch_", "fl_background_ch_"))
    }

    if pc_channel is not None and pc_channel in feature_map:
        pc = ChannelSelection(pc_channel, sorted(feature_map.pop(pc_channel)))
    elif pc_channel is not None:
        pc = ChannelSelection(pc_channel, [])
    else:
        pc = None

    fl = []
    for channel in sorted(set(feature_map) | fl_channels):
        fl.append(ChannelSelection(channel, sorted(feature_map.get(channel, set()))))

    return Channels(pc=pc, fl=fl)


def _merge_channels(target: Channels, incoming: Channels) -> None:
    target.merge_from(incoming)
