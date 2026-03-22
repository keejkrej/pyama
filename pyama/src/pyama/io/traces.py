"""Trace-file discovery and inspection helpers."""

import re
from pathlib import Path

import pandas as pd

from pyama.types.io import ProcessingResults

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


def infer_channel_feature_config(results: ProcessingResults) -> list[tuple[int, list[str]]]:
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


__all__ = [
    "POSITION_FILE_PATTERN",
    "collect_position_trace_files",
    "infer_channel_feature_config",
]
