import re
from pathlib import Path
from threading import Event
from typing import Any, Callable

import pandas as pd

from pyama.io.config import ensure_config
from pyama.io.samples import read_samples_yaml
from pyama.io.traces import collect_position_trace_files
from pyama.types.io import MicroscopyMetadata
from pyama.types.processing import MergeSample, MergeSamplePayload
from pyama.types.processing import ProcessingConfig
from pyama.utils.processing import resolve_processing_positions
from pyama.utils.position import parse_position_range


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
        positions_value = sample.get("positions")
        normalized.append(
            MergeSample(
                name=name,
                positions=tuple(parse_positions_field(positions_value)),
            )
        )
    return normalized


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

    indices = parse_position_range(text, length=len(available_position_ids))
    return {
        int(available_position_ids[index])
        for index in indices
        if int(index) in available_index_set
    }


def _resolve_merge_context(
    *,
    metadata: MicroscopyMetadata,
    config: ProcessingConfig,
    output_dir: Path,
    positions_subset: list[int] | None,
    merged_dir: Path | None,
) -> tuple[list[int], dict[int, Path], Path, list[int], set[int]]:
    traces_dir = output_dir / "traces"
    if not traces_dir.exists():
        raise FileNotFoundError(f"Traces directory not found: {traces_dir}")

    selected_positions = (
        positions_subset
        if positions_subset is not None
        else resolve_processing_positions(metadata, config)
    )
    selected_position_ids = {int(metadata.position_list[position_idx]) for position_idx in selected_positions}
    selected_files = collect_position_trace_files(traces_dir, position_ids=selected_position_ids)
    if not selected_files:
        raise FileNotFoundError(f"No position CSV files found in {traces_dir} for selected positions")

    target_dir = merged_dir if merged_dir is not None else (output_dir / "traces_merged")
    target_dir.mkdir(parents=True, exist_ok=True)
    available_position_ids = sorted(selected_position_ids)
    available_index_set = set(range(len(available_position_ids)))
    return selected_positions, selected_files, target_dir, available_position_ids, available_index_set


def _emit_merge_progress(
    *,
    progress_callback: Callable[[dict[str, int | str]], None] | None,
    worker_id: int,
    position_idx: int,
    position_progress_index: int,
    position_progress_total: int,
    message: str,
    frame_index: int,
    frame_total: int,
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        {
            "worker_id": worker_id,
            "stage": "merge",
            "channel_id": -1,
            "position_id": position_idx,
            "position_index": position_progress_index,
            "position_total": position_progress_total,
            "frame_index": frame_index,
            "frame_total": frame_total,
            "message": message,
        }
    )


def _collect_sample_frames(
    *,
    sample_position_ids: set[int],
    selected_files: dict[int, Path],
    cache: dict[int, pd.DataFrame],
    cancel_event: Event | None,
    progress_callback: Callable[[dict[str, int | str]], None] | None,
    worker_id: int,
    id_to_index: dict[int, int],
    selected_index_lookup: dict[int, int],
    global_position_lookup: dict[int, int] | None,
    global_position_total: int | None,
    selected_positions: list[int],
) -> tuple[list[pd.DataFrame], int, int, int, bool]:
    sample_frames: list[pd.DataFrame] = []
    skipped_positions = 0
    inspected_count = 0
    merged_positions = 0

    for position_id in sorted(sample_position_ids):
        if cancel_event and cancel_event.is_set():
            return sample_frames, skipped_positions, inspected_count, merged_positions, True

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
            _emit_merge_progress(
                progress_callback=progress_callback,
                worker_id=worker_id,
                position_idx=position_idx,
                position_progress_index=position_progress_index,
                position_progress_total=position_progress_total,
                message="skipped",
                frame_index=0,
                frame_total=0,
            )
            continue

        if position_id not in cache:
            cache[position_id] = pd.read_csv(csv_path)
            if "inspected" in csv_path.parts:
                inspected_count += 1
        sample_frames.append(cache[position_id])
        merged_positions += 1
        _emit_merge_progress(
            progress_callback=progress_callback,
            worker_id=worker_id,
            position_idx=position_idx,
            position_progress_index=position_progress_index,
            position_progress_total=position_progress_total,
            message="",
            frame_index=1,
            frame_total=1,
        )

    return sample_frames, skipped_positions, inspected_count, merged_positions, False


def _write_sample_feature_files(
    *,
    sample_name: str,
    sample_frames: list[pd.DataFrame],
    target_dir: Path,
) -> tuple[int, int]:
    sample_merged = pd.concat(sample_frames, ignore_index=True)
    sort_cols = [c for c in ["position", "roi", "frame"] if c in sample_merged.columns]
    if sort_cols:
        sample_merged.sort_values(sort_cols, inplace=True)
    feature_columns = sorted(column for column in sample_merged.columns if re.match(r"^.+_c\d+$", column))
    if not feature_columns:
        return 0, 0

    merged_rows = 0
    merged_files = 0
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
    return merged_rows, merged_files


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
    selected_positions, selected_files, target_dir, available_position_ids, available_index_set = _resolve_merge_context(
        metadata=metadata,
        config=config,
        output_dir=output_dir,
        positions_subset=positions_subset,
        merged_dir=merged_dir,
    )
    samples = read_samples_yaml(sample_yaml)["samples"]

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

        sample_frames, sample_skipped, sample_inspected, sample_merged_positions, cancelled = _collect_sample_frames(
            sample_position_ids=sample_position_ids,
            selected_files=selected_files,
            cache=cache,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
            worker_id=worker_id,
            id_to_index=id_to_index,
            selected_index_lookup=selected_index_lookup,
            global_position_lookup=global_position_lookup,
            global_position_total=global_position_total,
            selected_positions=selected_positions,
        )
        skipped_positions += sample_skipped
        inspected_count += sample_inspected
        merged_positions += sample_merged_positions
        if cancelled:
            break
        if not sample_frames:
            continue

        sample_rows, sample_files = _write_sample_feature_files(
            sample_name=sample_name,
            sample_frames=sample_frames,
            target_dir=target_dir,
        )
        merged_rows += sample_rows
        merged_files += sample_files

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
    selected_files = collect_position_trace_files(input_dir / "traces")
    position_ids = sorted(selected_files)
    metadata = MicroscopyMetadata(
        file_path=input_dir,
        base_name=input_dir.name,
        file_type="merged",
        height=0,
        width=0,
        n_frames=0,
        channel_names=(),
        dtype="",
        position_list=tuple(position_ids),
    )
    config = ProcessingConfig(params=ProcessingConfig().params)
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
    "parse_positions_field",
    "run_merge_to_csv",
    "run_merge_traces",
]
