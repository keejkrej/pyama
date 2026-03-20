"""Folder-level statistics orchestration services."""

from collections.abc import Callable
import logging
from pathlib import Path

import pandas as pd

from pyama.apps.statistics.discovery import discover_sample_pairs
from pyama.apps.statistics.metrics import (
    compute_auc_results,
    compute_onset_shifted_relu_results,
)
from pyama.apps.statistics.normalization import load_normalized_sample
from pyama.types.progress_payload import ProgressPayload
from pyama.utils.progress import emit_progress

logger = logging.getLogger(__name__)


def run_folder_statistics(
    folder_path: Path | str,
    mode: str,
    *,
    normalize_by_area: bool = True,
    frame_interval_minutes: float = 10.0,
    fit_window_min: float = 240.0,
    area_filter_size: int = 10,
    progress_reporter: Callable[[ProgressPayload], None] | None = None,
    cancel_event=None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Path]:
    """Run a statistics mode across all discovered samples in a folder."""
    folder = Path(folder_path)
    sample_pairs = discover_sample_pairs(folder)
    if not sample_pairs:
        raise ValueError(f"No valid intensity samples found in {folder}")

    if normalize_by_area:
        missing_area_samples = [
            pair.sample_name for pair in sample_pairs if pair.area_csv is None
        ]
        if missing_area_samples:
            sample_list = ", ".join(sorted(missing_area_samples))
            raise ValueError(
                "Area normalization requires an area CSV for every sample. "
                f"Missing area CSV for: {sample_list}"
            )

    traces_by_sample: dict[str, pd.DataFrame] = {}
    result_frames: list[pd.DataFrame] = []
    normalization_mode = "area_normalized" if normalize_by_area else "raw_intensity"

    logger.info(
        "Running statistics mode=%s normalization=%s on %d samples in %s",
        mode,
        normalization_mode,
        len(sample_pairs),
        folder,
    )

    total_samples = len(sample_pairs)
    for sample_index, pair in enumerate(sample_pairs, start=1):
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError("Task cancelled")
        trace_df = load_normalized_sample(
            pair,
            area_filter_size=area_filter_size,
            normalize_by_area=normalize_by_area,
            frame_interval_minutes=frame_interval_minutes,
        )
        traces_by_sample[pair.sample_name] = trace_df

        if mode == "auc":
            result_frames.append(
                compute_auc_results(
                    trace_df,
                    pair,
                    frame_interval_minutes=frame_interval_minutes,
                )
            )
        elif mode == "onset_shifted_relu":
            result_frames.append(
                compute_onset_shifted_relu_results(
                    trace_df,
                    pair,
                    fit_window_min=fit_window_min,
                    frame_interval_minutes=frame_interval_minutes,
                )
            )
        else:
            raise ValueError(f"Unsupported statistics mode: {mode}")

        emit_progress(
            progress_reporter,
            step="statistics",
            mode=mode,
            sample=pair.sample_name,
            current=sample_index,
            total=total_samples,
            message=f"Processed sample {pair.sample_name}",
        )

    results_df = pd.concat(result_frames, ignore_index=True)
    results_df["normalization_mode"] = normalization_mode
    if not normalize_by_area:
        results_df["source_area_file"] = ""

    output_suffix = "normalized" if normalize_by_area else "raw"
    output_name = (
        f"statistics_auc_{output_suffix}.csv"
        if mode == "auc"
        else f"statistics_onset_shifted_relu_{output_suffix}.csv"
    )
    output_path = folder / output_name
    results_df.to_csv(output_path, index=False)
    logger.info(
        "Saved statistics results to %s (%d rows)", output_path, len(results_df)
    )

    return results_df, traces_by_sample, output_path
