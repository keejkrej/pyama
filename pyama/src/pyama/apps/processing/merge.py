import re
from pathlib import Path
from threading import Event
from typing import Any, Callable

import pandas as pd
import yaml

from pyama.io.config import ensure_config
from pyama.types.microscopy import MicroscopyMetadata
from pyama.types.pipeline import ProcessingConfig
from pyama.types.processing import MergeSample, MergeSamplePayload, SamplesFilePayload
from pyama.utils.position import parse_position_range

POSITION_FILE_PATTERN = re.compile(r"^position_(\d+)\.csv$")


def parse_fov_range(text: str) -> list[int]:
    return parse_position_range(text)


def parse_positions_field(value: Any) -> list[int]:
    if isinstance(value, list):
        return sorted({int(v) for v in value})
    if isinstance(value, str):
        return parse_position_range(value)
    raise ValueError("Position specification must be a list of integers or a slice string")


def normalize_samples(samples: list[MergeSamplePayload]) -> list[MergeSample]:
    normalized: list[MergeSample] = []
    seen_names: set[str] = set()

    for index, sample in enumerate(samples, start=1):
        name = str(sample.get("name", "")).strip()
        if not name:
            raise ValueError(f"Sample {index} is missing a name")
        if name in seen_names:
            raise ValueError(f"Duplicate sample name '{name}'")
        seen_names.add(name)
        positions_value = sample.get("positions", sample.get("fovs"))
        normalized.append(
            MergeSample(
                name=name,
                positions=tuple(parse_positions_field(positions_value)),
            )
        )
    return normalized


def read_samples_yaml(path: Path) -> SamplesFilePayload:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("Samples YAML must contain a mapping at top level")
    samples = data.get("samples")
    if not isinstance(samples, list):
        raise ValueError("Samples YAML must contain a 'samples' list")

    validated_samples: list[MergeSamplePayload] = []
    for index, sample in enumerate(samples, start=1):
        if not isinstance(sample, dict):
            raise ValueError(f"Sample {index} must be a mapping")
        name = sample.get("name")
        positions = sample.get("positions", sample.get("fovs"))
        if not isinstance(name, str):
            raise ValueError(f"Sample {index} is missing a name")
        if not isinstance(positions, (str, list)):
            raise ValueError(f"Sample {index} must include a string or list of positions")
        validated_samples.append({"name": name, "positions": positions})
    return {"samples": validated_samples}


def _resolve_positions(metadata: MicroscopyMetadata, config: ProcessingConfig) -> list[int]:
    if config.params.positions.strip().lower() == "all":
        return list(range(metadata.n_positions))
    return parse_position_range(config.params.positions, length=metadata.n_positions)


def _collect_position_files(
    traces_dir: Path, position_ids: set[int] | None = None
) -> dict[int, Path]:
    selected: dict[int, Path] = {}
    inspected_dir = traces_dir / "inspected"

    for candidate in sorted(traces_dir.glob("position_*.csv")):
        match = POSITION_FILE_PATTERN.match(candidate.name)
        if not match:
            continue
        position_id = int(match.group(1))
        if position_ids is not None and position_id not in position_ids:
            continue
        selected[position_id] = candidate

    if inspected_dir.exists():
        for candidate in sorted(inspected_dir.glob("position_*.csv")):
            match = POSITION_FILE_PATTERN.match(candidate.name)
            if not match:
                continue
            position_id = int(match.group(1))
            if position_ids is not None and position_id not in position_ids:
                continue
            selected[position_id] = candidate

    return selected


def _parse_sample_positions(
    value: Any, available_position_ids: list[int], available_index_set: set[int]
) -> set[int]:
    if isinstance(value, list):
        return {int(v) for v in value if int(v) in available_position_ids}
    if not isinstance(value, str):
        raise ValueError("Sample positions must be a list or string")

    text = value.strip()
    if text.lower() == "all":
        return set(available_position_ids)
    if not text:
        return set()

    if "-" in text and ":" not in text:
        parsed_ids: set[int] = set()
        for segment in text.split(","):
            token = segment.strip()
            if not token:
                continue
            if "-" in token:
                start_text, end_text = token.split("-", 1)
                start = int(start_text.strip())
                end = int(end_text.strip())
                lo, hi = (start, end) if start <= end else (end, start)
                parsed_ids.update(pid for pid in available_position_ids if lo <= pid <= hi)
            else:
                pid = int(token)
                if pid in available_position_ids:
                    parsed_ids.add(pid)
        return parsed_ids

    indices = parse_position_range(text, length=len(available_position_ids))
    return {
        int(available_position_ids[index])
        for index in indices
        if int(index) in available_index_set
    }


def run_merge_to_csv(
    *,
    metadata: MicroscopyMetadata,
    config: ProcessingConfig,
    output_dir: Path,
    sample_yaml: Path,
    merged_dir: Path | None = None,
    cancel_event: Event | None = None,
    progress_callback: Callable[[dict[str, int | str]], None] | None = None,
    positions_subset: list[int] | None = None,
    worker_id: int = 0,
    global_position_lookup: dict[int, int] | None = None,
    global_position_total: int | None = None,
) -> dict[str, int | str | bool]:
    config = ensure_config(config)
    method = "mvp"
    traces_dir = output_dir / "traces"
    if not traces_dir.exists():
        raise FileNotFoundError(f"Traces directory not found: {traces_dir}")

    selected_positions = positions_subset if positions_subset is not None else _resolve_positions(metadata, config)
    selected_position_ids = {int(metadata.position_list[position_idx]) for position_idx in selected_positions}
    selected_files = _collect_position_files(traces_dir, position_ids=selected_position_ids)
    if not selected_files:
        raise FileNotFoundError(f"No position CSV files found in {traces_dir} for selected positions")

    target_dir = merged_dir if merged_dir is not None else (output_dir / "traces_merged")
    target_dir.mkdir(parents=True, exist_ok=True)

    samples = read_samples_yaml(sample_yaml)["samples"]
    available_position_ids = sorted(selected_position_ids)
    available_index_set = set(range(len(available_position_ids)))

    cache: dict[int, pd.DataFrame] = {}
    inspected_count = 0
    merged_rows = 0
    merged_files = 0
    merged_positions = 0
    skipped_positions = 0
    cancelled = False

    id_to_index = {int(position_id): idx for idx, position_id in enumerate(metadata.position_list)}
    selected_index_lookup = {pos_idx: i + 1 for i, pos_idx in enumerate(selected_positions)}

    for sample in samples:
        sample_name = str(sample.get("name", "")).strip()
        if not sample_name:
            raise ValueError("Each sample entry must include a non-empty 'name'")
        positions_value = sample.get("positions", "all")
        sample_position_ids = _parse_sample_positions(
            positions_value,
            available_position_ids=available_position_ids,
            available_index_set=available_index_set,
        )
        sample_position_ids = {pid for pid in sample_position_ids if pid in selected_files}
        if not sample_position_ids:
            continue

        sample_frames: list[pd.DataFrame] = []
        for position_id in sorted(sample_position_ids):
            if cancel_event and cancel_event.is_set():
                cancelled = True
                break
            position_idx = id_to_index.get(position_id, -1)
            position_progress_index = (
                global_position_lookup[position_idx]
                if global_position_lookup is not None and position_idx in global_position_lookup
                else selected_index_lookup.get(position_idx, 0)
            )
            position_progress_total = global_position_total if global_position_total is not None else len(selected_positions)

            csv_path = selected_files.get(position_id)
            if csv_path is None:
                skipped_positions += 1
                if progress_callback:
                    progress_callback(
                        {
                            "worker_id": worker_id,
                            "stage": "merge",
                            "channel_id": -1,
                            "position_id": position_idx,
                            "position_index": position_progress_index,
                            "position_total": position_progress_total,
                            "frame_index": 0,
                            "frame_total": 0,
                            "message": "skipped",
                        }
                    )
                continue
            if position_id not in cache:
                cache[position_id] = pd.read_csv(csv_path)
                if "inspected" in csv_path.parts:
                    inspected_count += 1
            sample_frames.append(cache[position_id])
            merged_positions += 1
            if progress_callback:
                progress_callback(
                    {
                        "worker_id": worker_id,
                        "stage": "merge",
                        "channel_id": -1,
                        "position_id": position_idx,
                        "position_index": position_progress_index,
                        "position_total": position_progress_total,
                        "frame_index": 1,
                        "frame_total": 1,
                        "message": "",
                    }
                )
        if cancelled:
            break
        if not sample_frames:
            continue

        sample_merged = pd.concat(sample_frames, ignore_index=True)
        sort_cols = [c for c in ["position", "roi", "frame"] if c in sample_merged.columns]
        if sort_cols:
            sample_merged.sort_values(sort_cols, inplace=True)
        feature_columns = sorted(column for column in sample_merged.columns if re.match(r"^.+_c\d+$", column))
        if not feature_columns:
            continue

        for feature_column in feature_columns:
            feature_df = sample_merged[["position", "roi", "frame", feature_column]].copy()
            feature_df.rename(columns={feature_column: "value"}, inplace=True)
            feature_df = feature_df[feature_df["value"].notna()]
            feature_df.sort_values(["position", "roi", "frame"], inplace=True)
            feature_out_dir = target_dir / feature_column
            feature_out_dir.mkdir(parents=True, exist_ok=True)
            out_path = feature_out_dir / f"{sample_name}.csv"
            feature_df.to_csv(out_path, index=False, float_format="%.6f")
            merged_rows += int(len(feature_df))
            merged_files += 1

    if merged_files == 0:
        raise ValueError("Merge produced 0 files from the provided samples configuration")

    return {
        "merge_method": method,
        "merged_dir": str(target_dir),
        "merged_positions": merged_positions,
        "merge_skipped_positions": skipped_positions,
        "merged_rows": merged_rows,
        "merged_files": merged_files,
        "inspected_positions": inspected_count,
        "merge_cancelled": cancelled,
    }


def run_merge_traces(
    input_dir: Path,
    sample_yaml: Path,
    output_dir: Path | None = None,
) -> dict[str, int | str]:
    selected_files = _collect_position_files(input_dir / "traces")
    position_ids = sorted(selected_files)
    metadata = MicroscopyMetadata(
        file_path=input_dir,
        base_name=input_dir.name,
        file_type="merged",
        height=0,
        width=0,
        n_frames=0,
        channel_names=[],
        dtype="",
        position_list=position_ids,
    )
    config = ProcessingConfig(channels=None, params={"positions": "all"})
    resolved_output = output_dir if output_dir is not None else (input_dir / "traces_merged")
    summary = run_merge_to_csv(
        metadata=metadata,
        config=config,
        output_dir=input_dir,
        sample_yaml=sample_yaml,
        merged_dir=resolved_output,
    )
    return {
        "output_dir": str(summary["merged_dir"]),
        "merged_positions": int(summary["merged_positions"]),
        "merged_rows": int(summary["merged_rows"]),
        "merged_files": int(summary["merged_files"]),
        "inspected_positions": int(summary["inspected_positions"]),
    }


__all__ = [
    "normalize_samples",
    "parse_fov_range",
    "parse_positions_field",
    "read_samples_yaml",
    "run_merge_to_csv",
    "run_merge_traces",
]
