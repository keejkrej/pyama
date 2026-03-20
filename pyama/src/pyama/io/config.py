import logging
import re
from pathlib import Path

import pandas as pd
import yaml
import zarr

from pyama.types.io import ProcessingResults
from pyama.types.pipeline import ProcessingConfig

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "processing_config.yaml"
_POSITION_TRACE_RE = re.compile(r"^position_(\d+)\.csv$")
_FEATURE_COLUMN_RE = re.compile(r"^(?P<feature>.+)_c(?P<channel>\d+)$")
_DATASET_REF_SEP = "::"


def load_config(path: Path) -> ProcessingConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return ProcessingConfig.model_validate(data)


def save_config(config: ProcessingConfig, path: Path) -> None:
    data = config.model_dump(mode="json", exclude_none=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, default_flow_style=False)
    logger.info("Saved processing config to %s", path)


def ensure_config(config: ProcessingConfig | None) -> ProcessingConfig:
    if config is None:
        return ProcessingConfig()
    return config


def get_config_path(output_dir: Path) -> Path:
    return output_dir / CONFIG_FILENAME


def get_trace_csv_path(target: Path | ProcessingResults | dict, position_id: int) -> Path | None:
    if isinstance(target, Path):
        return target / "traces" / f"position_{int(position_id)}.csv"
    if isinstance(target, ProcessingResults):
        value = target.position_data.get(int(position_id), {}).get("traces")
        return None if value is None else Path(value)
    if isinstance(target, dict):
        position_data = target.get("position_data", {})
        value = position_data.get(int(position_id), {}).get("traces")
        return None if value is None else Path(value)
    raise TypeError("target must be a Path, ProcessingResults, or dict")


def _dataset_ref(store_path: Path, dataset_path: str) -> str:
    return f"{store_path}{_DATASET_REF_SEP}{dataset_path}"


def _load_channels_from_config(config_path: Path | None) -> dict[str, object]:
    if config_path is None or not config_path.exists():
        return {}
    try:
        config = load_config(config_path)
    except Exception:
        logger.warning("Failed to load processing config from %s", config_path, exc_info=True)
        return {}
    if config.channels is None:
        return {}
    return config.channels.model_dump(mode="json")


def _infer_channels_from_traces(position_data: dict[int, dict[str, object]]) -> dict[str, object]:
    pc_features: dict[int, set[str]] = {}
    fl_features: dict[int, set[str]] = {}
    for payload in position_data.values():
        traces = payload.get("traces")
        if traces is None:
            continue
        try:
            columns = list(pd.read_csv(Path(traces), nrows=0).columns)
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

    if not pc_features and not fl_features:
        return {}
    pc_channel = min(pc_features) if pc_features else None
    payload: dict[str, object] = {"pc": None, "fl": {}}
    if pc_channel is not None:
        payload["pc"] = {pc_channel: sorted(pc_features[pc_channel])}
    payload["fl"] = {
        channel: sorted(features)
        for channel, features in sorted(fl_features.items())
    }
    return payload


def _scan_raw_zarr(raw_zarr_path: Path) -> dict[int, dict[str, object]]:
    store = zarr.open_group(raw_zarr_path, mode="r")
    position_data: dict[int, dict[str, object]] = {}

    position_group = store.get("position")
    if position_group is None:
        return position_data

    for position_name in sorted(position_group.group_keys(), key=lambda value: int(value)):
        position_id = int(position_name)
        payload = position_data.setdefault(position_id, {})
        channel_group = store.get(f"position/{position_id}/channel")
        if channel_group is None:
            continue
        for channel_name in sorted(channel_group.group_keys(), key=lambda value: int(value)):
            channel_id = int(channel_name)
            base = f"position/{position_id}/channel/{channel_id}"
            for dataset_name, key_prefix in (
                ("raw", "raw"),
                ("seg_labeled", "seg_labeled"),
                ("seg_tracked", "seg_tracked"),
                ("fl_background", "fl_background"),
            ):
                if store.get(f"{base}/{dataset_name}") is not None:
                    payload[f"{key_prefix}_ch_{channel_id}"] = _dataset_ref(
                        raw_zarr_path, f"{base}/{dataset_name}"
                    )
    return position_data


def _scan_traces_dir(traces_dir: Path) -> dict[int, dict[str, object]]:
    position_data: dict[int, dict[str, object]] = {}
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

    position_data: dict[int, dict[str, object]] = {}
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
    if not channels:
        channels = _infer_channels_from_traces(position_data)

    extra: dict[str, object] = {}
    if config_path.exists():
        extra["config_path"] = config_path
    if raw_zarr_path.exists():
        extra["raw_zarr_path"] = raw_zarr_path
    if rois_zarr_path.exists():
        extra["rois_zarr_path"] = rois_zarr_path
    if traces_dir.exists():
        extra["traces_dir"] = traces_dir
    if traces_merged_dir.exists():
        extra["traces_merged_dir"] = traces_merged_dir

    return ProcessingResults(
        project_path=project_dir,
        n_positions=len(position_data),
        position_data=position_data,
        channels=channels,
        extra=extra,
    )


__all__ = [
    "CONFIG_FILENAME",
    "ensure_config",
    "get_config_path",
    "get_trace_csv_path",
    "load_config",
    "save_config",
    "scan_processing_results",
]
