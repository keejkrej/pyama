"""Merge functionality for combining CSV outputs from PyAMA processing."""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd
import yaml

from pyama_core.io import load_config, naming
from pyama_core.io.processing_csv import get_dataframe
from pyama_core.io.trace_paths import resolve_trace_path
from pyama_core.types.merge import MergeResult, get_merge_fields
from pyama_core.types.processing import (
    Channels,
    FeatureMaps,
    get_processing_base_fields,
    get_processing_feature_field,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CHANNEL CONFIGURATION
# =============================================================================


def get_channel_feature_config_from_channels(
    channels: Channels,
) -> list[tuple[int, list[str]]]:
    """Determine the channel/feature selections from Channels config.

    Returns:
        List of (channel_id, features) tuples.
    """
    config: list[tuple[int, list[str]]] = []

    pc_channel = channels.get_pc_channel()
    if pc_channel is not None:
        pc_features = channels.get_pc_features()
        if pc_features:
            config.append((pc_channel, sorted(set(pc_features))))

    fl_feature_map = channels.get_fl_feature_map()
    for channel in sorted(fl_feature_map):
        features = fl_feature_map[channel]
        if features:
            config.append((channel, sorted(set(features))))

    if not config:
        raise ValueError("No channels found in processing config")

    return config


# =============================================================================
# SAMPLE PARSING
# =============================================================================


def parse_fov_range(text: str) -> list[int]:
    """Parse comma-separated FOV ranges (e.g., '0-5, 7, 9-11')."""
    normalized = text.replace(" ", "").strip()
    if not normalized:
        raise ValueError("FOV specification cannot be empty")
    if ";" in normalized:
        raise ValueError("Use commas to separate FOVs; semicolons are not supported")

    fovs: list[int] = []
    parts = [part for part in normalized.split(",") if part]

    for part in parts:
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            if not start_str or not end_str:
                raise ValueError(f"Invalid range '{part}': missing start or end value")
            try:
                start, end = int(start_str), int(end_str)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid range '{part}': values must be integers"
                ) from exc
            if start < 0 or end < 0:
                raise ValueError(f"Invalid range '{part}': negative values not allowed")
            if start > end:
                raise ValueError(f"Invalid range '{part}': start must be <= end")
            fovs.extend(range(start, end + 1))
        else:
            try:
                value = int(part)
            except ValueError as exc:
                raise ValueError(f"Invalid FOV '{part}': must be an integer") from exc
            if value < 0:
                raise ValueError(f"FOV '{part}' must be >= 0")
            fovs.append(value)

    return sorted(set(fovs))


def parse_fovs_field(value: Any) -> list[int]:
    """Normalize a FOV specification originating from YAML."""
    if isinstance(value, list):
        normalized: list[int] = []
        for entry in value:
            try:
                fov = int(entry)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"FOV value '{entry}' is not a valid integer") from exc
            if fov < 0:
                raise ValueError(f"FOV value '{entry}' must be >= 0")
            normalized.append(fov)
        return sorted(set(normalized))
    if isinstance(value, str):
        return parse_fov_range(value)
    raise ValueError(
        "FOV specification must be a list of integers or a comma-separated string"
    )


def read_samples_yaml(path: Path) -> dict[str, Any]:
    """Load a samples YAML specification."""
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("Samples YAML must contain a mapping at the top level")
    samples = data.get("samples")
    if not isinstance(samples, list):
        raise ValueError("Samples YAML must include a 'samples' list")
    return data


# =============================================================================
# FEATURE PROCESSING
# =============================================================================


def build_feature_maps(rows: list[dict], feature_names: list[str]) -> FeatureMaps:
    """Build feature maps filtered by 'good' rows."""
    feature_maps: dict[str, dict[tuple[int, int], float]] = {
        feature_name: {} for feature_name in feature_names
    }
    frames_set: set[int] = set()
    cells_set: set[int] = set()

    for row in rows:
        if "good" in row and not row["good"]:
            continue
        frame = row.get("frame")
        cell = row.get("cell")
        if frame is None or cell is None:
            continue

        key = (int(frame), int(cell))
        frames_set.add(int(frame))
        cells_set.add(int(cell))

        for feature_name in feature_names:
            if feature_name in row:
                value = row[feature_name]
                if value is not None:
                    feature_maps[feature_name][key] = float(value)

    return FeatureMaps(
        features=feature_maps,
        frames=sorted(frames_set),
        cells=sorted(cells_set),
    )


def extract_channel_dataframe(
    df: pd.DataFrame, channel: int, configured_features: list[str]
) -> pd.DataFrame:
    """Return a dataframe containing only configured features for a single channel.

    Args:
        df: Unified trace DataFrame with channel-suffixed columns
        channel: Channel ID to extract
        configured_features: List of feature names configured for this channel

    Returns:
        DataFrame with base columns and only the configured features for this channel
    """
    base_fields = ["fov"] + get_processing_base_fields()
    base_cols = [col for col in base_fields if col in df.columns]

    # Only extract features that are configured for this channel
    feature_cols = []
    rename_map = {}
    for feature_name in configured_features:
        feature_col = get_processing_feature_field(feature_name, channel)
        if feature_col in df.columns:
            feature_cols.append(feature_col)
            rename_map[feature_col] = feature_name

    selected_cols = base_cols + feature_cols
    if not selected_cols:
        return pd.DataFrame()

    channel_df = df[selected_cols].copy()
    if rename_map:
        channel_df.rename(columns=rename_map, inplace=True)
    return channel_df


def get_all_frames(
    feature_maps_by_fov: dict[int, FeatureMaps], fovs: Iterable[int]
) -> list[int]:
    """Collect sorted unique frame indices across FOVs."""
    frames: set[int] = set()
    for fov in fovs:
        feature_maps = feature_maps_by_fov.get(fov)
        if feature_maps:
            frames.update(feature_maps.frames)
    return sorted(frames)


def write_feature_csv(
    out_path: Path,
    frames: list[int],
    fovs: Iterable[int],
    feature_name: str,
    feature_maps_by_fov: dict[int, FeatureMaps],
) -> None:
    """Write a feature CSV in tidy/long format.

    Output format: frame, fov, cell, value
    Only includes FOVs and cells that have data available.
    """
    fov_list = list(fovs)

    # Filter to only include FOVs that have data
    available_fovs = [fov for fov in fov_list if fov in feature_maps_by_fov]

    # Get column names for DataFrame
    col_names = get_merge_fields()

    # Build rows in long format: frame, fov, cell, value
    rows = []
    for frame in frames:
        for fov in available_fovs:
            feature_maps = feature_maps_by_fov.get(fov)
            if not feature_maps:
                continue

            if feature_name not in feature_maps.features:
                continue

            feature_map = feature_maps.features[feature_name]
            for cell in sorted(feature_maps.cells):
                value = feature_map.get((frame, cell))
                if value is not None:
                    result = MergeResult(frame=frame, fov=fov, cell=cell, value=value)
                    rows.append(dataclasses.asdict(result))

    try:
        df = pd.DataFrame(rows, columns=col_names)
    except Exception:
        raise ValueError(f"Failed to create DataFrame. Expected columns: {col_names}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, float_format="%.6f")


# =============================================================================
# MAIN MERGE FUNCTION
# =============================================================================


def run_merge(
    sample_yaml: Path,
    output_dir: Path,
    input_dir: Path | None = None,
    config_path: Path | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> str:
    """Execute merge logic - return success message or raise error.

    Args:
        sample_yaml: Path to samples YAML file
        output_dir: Directory to write merged CSV files
        input_dir: Directory containing processed FOV folders (default: sample_yaml parent)
        config_path: Path to processing_config.yaml (default: input_dir/processing_config.yaml)
        progress_callback: Optional callback(current, total, message) for progress updates
    """
    samples_config = read_samples_yaml(sample_yaml)
    samples = samples_config["samples"]

    # Determine input directory
    if input_dir is None:
        input_dir = sample_yaml.parent

    # Load processing config
    if config_path is None:
        config_path = input_dir / "processing_config.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Processing config not found: {config_path}")

    proc_config = load_config(config_path)
    channel_feature_config = get_channel_feature_config_from_channels(
        proc_config.channels
    )

    # Collect all FOVs from samples
    all_fovs: set[int] = set()
    for sample in samples:
        fovs = parse_fovs_field(sample.get("fovs", []))
        all_fovs.update(fovs)

    feature_maps_by_fov_channel: dict[tuple[int, int], FeatureMaps] = {}
    traces_cache: dict[Path, pd.DataFrame] = {}

    # Load trace CSVs per FOV using file discovery
    sorted_fovs = sorted(all_fovs)
    total_fovs = len(sorted_fovs)
    loaded_fovs = 0

    for fov in sorted_fovs:
        # Discover trace CSV for this FOV
        fov_path = naming.fov_dir(input_dir, fov)
        if not fov_path.exists():
            logger.debug("FOV directory not found: %s", fov_path)
            continue

        # Find trace CSV file
        trace_files = list(fov_path.glob("*_traces.csv"))
        if not trace_files:
            logger.debug("No trace CSV found for FOV %s", fov)
            continue

        original_path = trace_files[0]
        csv_path = resolve_trace_path(original_path)

        if csv_path is None or not csv_path.exists():
            logger.warning("Trace CSV file does not exist: %s", original_path)
            continue

        # Load the unified CSV once per FOV
        if csv_path not in traces_cache:
            try:
                traces_cache[csv_path] = get_dataframe(csv_path)
                loaded_fovs += 1
                if progress_callback is not None:
                    progress_callback(loaded_fovs, total_fovs, "Loading FOV CSVs")
            except Exception as exc:
                logger.warning("Failed to read %s: %s", csv_path, exc)
                continue

        # Extract channel-specific data from the unified CSV using configured features
        for channel, features in channel_feature_config:
            channel_df = extract_channel_dataframe(
                traces_cache[csv_path], channel, features
            )
            if channel_df.empty:
                logger.debug(
                    "Trace CSV %s contains no data for channel %s", csv_path, channel
                )
                continue

            rows = channel_df.to_dict("records")
            feature_maps_by_fov_channel[(fov, channel)] = build_feature_maps(
                rows, features
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    created_files: list[Path] = []
    for sample in samples:
        sample_name = sample["name"]
        sample_fovs = parse_fovs_field(sample.get("fovs", []))
        logger.info("Processing sample '%s' with FOVs: %s", sample_name, sample_fovs)

        for channel, features in channel_feature_config:
            channel_feature_maps: dict[int, FeatureMaps] = {}
            for fov in sample_fovs:
                key = (fov, channel)
                feature_maps = feature_maps_by_fov_channel.get(key)
                if feature_maps:
                    channel_feature_maps[fov] = feature_maps

            if not channel_feature_maps:
                logger.warning(
                    "No data for sample %s, channel %s", sample_name, channel
                )
                continue

            frames = get_all_frames(channel_feature_maps, sample_fovs)

            for feature_name in features:
                # Only write CSV if the feature actually has data in any FOV
                has_data = False
                for fov in sample_fovs:
                    feature_maps = channel_feature_maps.get(fov)
                    if feature_maps and feature_name in feature_maps.features:
                        if feature_maps.features[feature_name]:
                            has_data = True
                            break

                if not has_data:
                    logger.debug(
                        "Skipping feature '%s' for sample '%s', channel %s: no data found",
                        feature_name,
                        sample_name,
                        channel,
                    )
                    continue

                output_filename = f"{sample_name}_{feature_name}_ch_{channel}.csv"
                output_path = output_dir / output_filename
                write_feature_csv(
                    output_path,
                    frames,
                    sample_fovs,
                    feature_name,
                    channel_feature_maps,
                )
                created_files.append(output_path)
                logger.info("Created: %s", output_filename)

    logger.info("Merge completed successfully")
    logger.info("Created %d files in %s", len(created_files), output_dir)
    return f"Merge completed. Created {len(created_files)} files in {output_dir}"
