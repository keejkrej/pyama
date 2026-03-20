"""Function-based service entrypoints for processing."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Empty, Queue
import logging
import threading
import tempfile
from typing import Any, Callable
import yaml

import pandas as pd

from pyama.apps.processing.background import run_background_to_raw_zarr
from pyama.apps.processing.copy import run_copy_to_raw_zarr
from pyama.apps.processing.extract import (
    list_fluorescence_features,
    list_phase_features,
    run_extract_to_csv,
)
from pyama.apps.processing.merge import (
    normalize_samples,
    parse_fov_range,
    parse_positions_field,
    read_samples_yaml,
    run_merge_to_csv,
    run_merge_traces,
)
from pyama.apps.processing.roi import run_roi_to_rois_zarr
from pyama.apps.processing.segment import run_segment_to_raw_zarr
from pyama.apps.processing.track import run_track_to_raw_zarr
from pyama.io import load_microscopy_file
from pyama.io.config import ensure_config
from pyama.types.microscopy import MicroscopyMetadata
from pyama.types.pipeline import Channels, ProcessingConfig
from pyama.utils.progress import emit_progress
from pyama.utils.position import parse_position_range

logger = logging.getLogger(__name__)

_STAGE_TO_PROGRESS_STEP = {
    "copy": "copy",
    "segment": "segmentation",
    "track": "tracking",
    "background": "background_estimation",
    "roi": "roi",
    "extract": "extraction",
    "merge": "merge",
}


def _legacy_context_to_config(
    *,
    metadata: MicroscopyMetadata,
    context,
    fov_start: int | None,
    fov_end: int | None,
    n_workers: int | None,
) -> ProcessingConfig:
    if context is None:
        raise ValueError("Processing configuration is required")

    channels_obj = getattr(context, "channels", None)
    params_obj = getattr(context, "params", None)
    pc_selection = getattr(channels_obj, "pc", None)
    fl_selections = list(getattr(channels_obj, "fl", [])) if channels_obj is not None else []

    if pc_selection is None:
        channels = None
    else:
        fl_map = {
            int(selection.channel): sorted(list(getattr(selection, "features", [])))
            for selection in fl_selections
        }
        channels = Channels(
            pc={int(pc_selection.channel): sorted(list(getattr(pc_selection, "features", [])))},
            fl=fl_map,
        )

    if fov_start is None or fov_start < 0:
        fov_start = 0
    if fov_end is None or fov_end < 0:
        fov_end = metadata.n_positions - 1
    positions = f"{fov_start}:{fov_end + 1}"

    payload = {
        "positions": positions,
        "n_workers": max(1, int(n_workers or 1)),
        "background_weight": float(getattr(params_obj, "background_weight", 1.0)),
        "copy_only": bool(getattr(params_obj, "copy_only", False)),
    }
    return ProcessingConfig(channels=channels, params=payload)


def _run_orchestrator(
    *,
    reader,
    metadata: MicroscopyMetadata,
    config: ProcessingConfig,
    output_dir: Path,
    cancel_event: threading.Event | None = None,
    progress_callback: Callable[[dict[str, int | str]], None] | None = None,
) -> dict[str, int | str | bool]:
    if cancel_event and cancel_event.is_set():
        return {"message": "Workflow cancelled before copy", "cancelled": True}

    config = ensure_config(config)
    if config.params.positions.strip().lower() == "all":
        resolved_positions = list(range(metadata.n_positions))
    else:
        resolved_positions = parse_position_range(config.params.positions, length=metadata.n_positions)

    if not resolved_positions:
        return {
            "raw_zarr_path": str(output_dir / "raw.zarr"),
            "rois_zarr_path": str(output_dir / "rois.zarr"),
            "selected_positions": 0,
            "selected_channels": 0,
            "copied_datasets": 0,
            "skipped_datasets": 0,
            "copied_frames": 0,
            "cancelled": False,
            "segmentation_method": config.params.segmentation_method.value,
            "segmented_datasets": 0,
            "segmentation_skipped_datasets": 0,
            "segmented_frames": 0,
            "segmentation_cancelled": False,
            "tracking_method": config.params.tracking_method.value,
            "tracked_datasets": 0,
            "tracking_skipped_datasets": 0,
            "tracked_frames": 0,
            "tracking_cancelled": False,
            "background_method": "mvp",
            "background_datasets": 0,
            "background_skipped_datasets": 0,
            "background_frames": 0,
            "background_cancelled": False,
            "roi_method": "mvp",
            "roi_positions": 0,
            "roi_skipped_positions": 0,
            "roi_count": 0,
            "roi_frames": 0,
            "roi_cancelled": False,
            "extract_method": "mvp",
            "extracted_positions": 0,
            "extract_skipped_positions": 0,
            "extracted_rows": 0,
            "extract_cancelled": False,
        }

    worker_count = max(1, min(config.params.n_workers, len(resolved_positions)))
    position_lookup = {position_idx: idx + 1 for idx, position_idx in enumerate(resolved_positions)}
    position_queue: Queue[int] = Queue()
    for position_idx in resolved_positions:
        position_queue.put(position_idx)

    def run_worker(worker_id: int) -> dict[str, int | str | bool]:
        summary: dict[str, int | str | bool] = {
            "raw_zarr_path": str(output_dir / "raw.zarr"),
            "rois_zarr_path": str(output_dir / "rois.zarr"),
            "selected_positions": 0,
            "selected_channels": 0,
            "copied_datasets": 0,
            "skipped_datasets": 0,
            "copied_frames": 0,
            "cancelled": False,
            "segmentation_method": config.params.segmentation_method.value,
            "segmented_datasets": 0,
            "segmentation_skipped_datasets": 0,
            "segmented_frames": 0,
            "segmentation_cancelled": False,
            "tracking_method": config.params.tracking_method.value,
            "tracked_datasets": 0,
            "tracking_skipped_datasets": 0,
            "tracked_frames": 0,
            "tracking_cancelled": False,
            "background_method": "mvp",
            "background_datasets": 0,
            "background_skipped_datasets": 0,
            "background_frames": 0,
            "background_cancelled": False,
            "roi_method": "mvp",
            "roi_positions": 0,
            "roi_skipped_positions": 0,
            "roi_count": 0,
            "roi_frames": 0,
            "roi_cancelled": False,
            "extract_method": "mvp",
            "extracted_positions": 0,
            "extract_skipped_positions": 0,
            "extracted_rows": 0,
            "extract_cancelled": False,
        }
        while True:
            if cancel_event and cancel_event.is_set():
                summary["cancelled"] = True
                break
            try:
                position_idx = position_queue.get_nowait()
            except Empty:
                break

            copy_summary = run_copy_to_raw_zarr(
                reader=reader,
                metadata=metadata,
                config=config,
                output_dir=output_dir,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
                positions_subset=[position_idx],
                worker_id=worker_id,
                global_position_lookup=position_lookup,
                global_position_total=len(resolved_positions),
            )
            summary["selected_positions"] = int(summary["selected_positions"]) + int(copy_summary.get("selected_positions", 0))
            summary["selected_channels"] = int(copy_summary.get("selected_channels", 0))
            summary["copied_datasets"] = int(summary["copied_datasets"]) + int(copy_summary.get("copied_datasets", 0))
            summary["skipped_datasets"] = int(summary["skipped_datasets"]) + int(copy_summary.get("skipped_datasets", 0))
            summary["copied_frames"] = int(summary["copied_frames"]) + int(copy_summary.get("copied_frames", 0))
            if bool(copy_summary.get("cancelled", False)):
                summary["cancelled"] = True
                break
            if config.params.copy_only:
                continue

            segment_summary = run_segment_to_raw_zarr(
                reader=reader,
                metadata=metadata,
                config=config,
                output_dir=output_dir,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
                positions_subset=[position_idx],
                worker_id=worker_id,
                global_position_lookup=position_lookup,
                global_position_total=len(resolved_positions),
            )
            summary["segmented_datasets"] = int(summary["segmented_datasets"]) + int(segment_summary.get("segmented_datasets", 0))
            summary["segmentation_skipped_datasets"] = int(summary["segmentation_skipped_datasets"]) + int(segment_summary.get("segmentation_skipped_datasets", 0))
            summary["segmented_frames"] = int(summary["segmented_frames"]) + int(segment_summary.get("segmented_frames", 0))
            if bool(segment_summary.get("segmentation_cancelled", False)):
                summary["segmentation_cancelled"] = True
                break

            track_summary = run_track_to_raw_zarr(
                reader=reader,
                metadata=metadata,
                config=config,
                output_dir=output_dir,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
                positions_subset=[position_idx],
                worker_id=worker_id,
                global_position_lookup=position_lookup,
                global_position_total=len(resolved_positions),
            )
            summary["tracked_datasets"] = int(summary["tracked_datasets"]) + int(track_summary.get("tracked_datasets", 0))
            summary["tracking_skipped_datasets"] = int(summary["tracking_skipped_datasets"]) + int(track_summary.get("tracking_skipped_datasets", 0))
            summary["tracked_frames"] = int(summary["tracked_frames"]) + int(track_summary.get("tracked_frames", 0))
            if bool(track_summary.get("tracking_cancelled", False)):
                summary["tracking_cancelled"] = True
                break

            background_summary = run_background_to_raw_zarr(
                reader=reader,
                metadata=metadata,
                config=config,
                output_dir=output_dir,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
                positions_subset=[position_idx],
                worker_id=worker_id,
                global_position_lookup=position_lookup,
                global_position_total=len(resolved_positions),
            )
            summary["background_datasets"] = int(summary["background_datasets"]) + int(background_summary.get("background_datasets", 0))
            summary["background_skipped_datasets"] = int(summary["background_skipped_datasets"]) + int(background_summary.get("background_skipped_datasets", 0))
            summary["background_frames"] = int(summary["background_frames"]) + int(background_summary.get("background_frames", 0))
            if bool(background_summary.get("background_cancelled", False)):
                summary["background_cancelled"] = True
                break

            roi_summary = run_roi_to_rois_zarr(
                reader=reader,
                metadata=metadata,
                config=config,
                output_dir=output_dir,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
                positions_subset=[position_idx],
                worker_id=worker_id,
                global_position_lookup=position_lookup,
                global_position_total=len(resolved_positions),
            )
            summary["roi_positions"] = int(summary["roi_positions"]) + int(roi_summary.get("roi_positions", 0))
            summary["roi_skipped_positions"] = int(summary["roi_skipped_positions"]) + int(roi_summary.get("roi_skipped_positions", 0))
            summary["roi_count"] = int(summary["roi_count"]) + int(roi_summary.get("roi_count", 0))
            summary["roi_frames"] = int(summary["roi_frames"]) + int(roi_summary.get("roi_frames", 0))
            if bool(roi_summary.get("roi_cancelled", False)):
                summary["roi_cancelled"] = True
                break

            extract_summary = run_extract_to_csv(
                metadata=metadata,
                config=config,
                output_dir=output_dir,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
                positions_subset=[position_idx],
                worker_id=worker_id,
                global_position_lookup=position_lookup,
                global_position_total=len(resolved_positions),
            )
            summary["extracted_positions"] = int(summary["extracted_positions"]) + int(extract_summary.get("extracted_positions", 0))
            summary["extract_skipped_positions"] = int(summary["extract_skipped_positions"]) + int(extract_summary.get("extract_skipped_positions", 0))
            summary["extracted_rows"] = int(summary["extracted_rows"]) + int(extract_summary.get("extracted_rows", 0))
            if bool(extract_summary.get("extract_cancelled", False)):
                summary["extract_cancelled"] = True
                break
        return summary

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        worker_summaries = list(executor.map(run_worker, range(worker_count)))

    return {
        "raw_zarr_path": str(output_dir / "raw.zarr"),
        "rois_zarr_path": str(output_dir / "rois.zarr"),
        "selected_positions": sum(int(summary.get("selected_positions", 0)) for summary in worker_summaries),
        "selected_channels": max((int(summary.get("selected_channels", 0)) for summary in worker_summaries), default=0),
        "copied_datasets": sum(int(summary.get("copied_datasets", 0)) for summary in worker_summaries),
        "skipped_datasets": sum(int(summary.get("skipped_datasets", 0)) for summary in worker_summaries),
        "copied_frames": sum(int(summary.get("copied_frames", 0)) for summary in worker_summaries),
        "cancelled": any(bool(summary.get("cancelled", False)) for summary in worker_summaries),
        "segmentation_method": config.params.segmentation_method.value,
        "segmented_datasets": sum(int(summary.get("segmented_datasets", 0)) for summary in worker_summaries),
        "segmentation_skipped_datasets": sum(int(summary.get("segmentation_skipped_datasets", 0)) for summary in worker_summaries),
        "segmented_frames": sum(int(summary.get("segmented_frames", 0)) for summary in worker_summaries),
        "segmentation_cancelled": any(bool(summary.get("segmentation_cancelled", False)) for summary in worker_summaries),
        "tracking_method": config.params.tracking_method.value,
        "tracked_datasets": sum(int(summary.get("tracked_datasets", 0)) for summary in worker_summaries),
        "tracking_skipped_datasets": sum(int(summary.get("tracking_skipped_datasets", 0)) for summary in worker_summaries),
        "tracked_frames": sum(int(summary.get("tracked_frames", 0)) for summary in worker_summaries),
        "tracking_cancelled": any(bool(summary.get("tracking_cancelled", False)) for summary in worker_summaries),
        "background_method": "mvp",
        "background_datasets": sum(int(summary.get("background_datasets", 0)) for summary in worker_summaries),
        "background_skipped_datasets": sum(int(summary.get("background_skipped_datasets", 0)) for summary in worker_summaries),
        "background_frames": sum(int(summary.get("background_frames", 0)) for summary in worker_summaries),
        "background_cancelled": any(bool(summary.get("background_cancelled", False)) for summary in worker_summaries),
        "roi_method": "mvp",
        "roi_positions": sum(int(summary.get("roi_positions", 0)) for summary in worker_summaries),
        "roi_skipped_positions": sum(int(summary.get("roi_skipped_positions", 0)) for summary in worker_summaries),
        "roi_count": sum(int(summary.get("roi_count", 0)) for summary in worker_summaries),
        "roi_frames": sum(int(summary.get("roi_frames", 0)) for summary in worker_summaries),
        "roi_cancelled": any(bool(summary.get("roi_cancelled", False)) for summary in worker_summaries),
        "extract_method": "mvp",
        "extracted_positions": sum(int(summary.get("extracted_positions", 0)) for summary in worker_summaries),
        "extract_skipped_positions": sum(int(summary.get("extract_skipped_positions", 0)) for summary in worker_summaries),
        "extracted_rows": sum(int(summary.get("extracted_rows", 0)) for summary in worker_summaries),
        "extract_cancelled": any(bool(summary.get("extract_cancelled", False)) for summary in worker_summaries),
    }


def run_complete_workflow(
    *,
    metadata: MicroscopyMetadata,
    config: ProcessingConfig | None = None,
    output_dir: Path | None = None,
    context=None,
    fov_start: int | None = None,
    fov_end: int | None = None,
    n_workers: int | None = None,
    cancel_event: threading.Event | None = None,
    progress_callback: Callable[[dict[str, int | str]], None] | None = None,
    progress_reporter: Callable[[dict[str, int | str]], None] | None = None,
) -> bool:
    resolved_output_dir = output_dir
    if resolved_output_dir is None and context is not None:
        resolved_output_dir = getattr(context, "output_dir", None)
    if resolved_output_dir is None:
        raise ValueError("output_dir is required")

    resolved_config = config
    if resolved_config is None:
        resolved_config = _legacy_context_to_config(
            metadata=metadata,
            context=context,
            fov_start=fov_start,
            fov_end=fov_end,
            n_workers=n_workers,
        )
    elif n_workers is not None and n_workers > 0 and resolved_config.params.n_workers != n_workers:
        payload = resolved_config.model_dump(mode="python")
        payload.setdefault("params", {})
        payload["params"]["n_workers"] = n_workers
        resolved_config = ProcessingConfig.model_validate(payload)

    def _event_to_progress_payload(event: dict[str, int | str]) -> None:
        stage = str(event.get("stage", "processing"))
        step = _STAGE_TO_PROGRESS_STEP.get(stage, stage)
        position_index = int(event.get("position_id", -1))
        channel_id = int(event.get("channel_id", -1))
        frame_index = int(event.get("frame_index", 0))
        frame_total = int(event.get("frame_total", 0))
        worker_id = int(event.get("worker_id", -1))
        message = str(event.get("message", ""))
        emit_progress(
            progress_reporter,
            step=step,
            event="frame",
            fov=position_index,
            channel=channel_id if channel_id >= 0 else None,
            current=max(frame_index - 1, 0),
            total=frame_total if frame_total > 0 else None,
            current_key="t",
            total_key="T",
            message=message,
            worker_id=worker_id,
            position_id=position_index,
            stage=stage,
            position_index=event.get("position_index"),
            position_total=event.get("position_total"),
            frame_index=frame_index,
            frame_total=frame_total,
        )

    progress_sink = progress_callback
    if progress_reporter is not None:
        if progress_sink is None:
            progress_sink = _event_to_progress_payload
        else:
            original_sink = progress_sink

            def _combined_progress_sink(event: dict[str, int | str]) -> None:
                original_sink(event)
                _event_to_progress_payload(event)

            progress_sink = _combined_progress_sink

    reader, _loaded_metadata = load_microscopy_file(Path(metadata.file_path))
    try:
        _run_orchestrator(
            reader=reader,
            metadata=metadata,
            config=resolved_config,
            output_dir=resolved_output_dir,
            cancel_event=cancel_event,
            progress_callback=progress_sink,
        )
    finally:
        try:
            reader.close()
        except Exception:
            logger.debug("Failed to close microscopy reader for %s", metadata.file_path, exc_info=True)
    return not bool(cancel_event and cancel_event.is_set())


def get_channel_feature_config(proc_results: Any) -> list[tuple[int, list[str]]]:
    config: dict[int, set[str]] = {}
    position_data = proc_results.get("position_data", {})
    for traces_info in position_data.values():
        traces_path = traces_info.get("traces")
        if traces_path is None:
            continue
        columns = list(pd.read_csv(traces_path, nrows=0).columns)
        for column in columns:
            match = pd.Series([column]).str.extract(r"^(.+)_c(\d+)$").iloc[0]
            if match.isna().any():
                continue
            feature = str(match[0])
            channel = int(match[1])
            config.setdefault(channel, set()).add(feature)
    return [
        (channel, sorted(features))
        for channel, features in sorted(config.items(), key=lambda item: item[0])
        if features
    ]


def run_merge(
    samples,
    processing_results_dir: Path | str,
    progress_callback=None,
    cancel_event=None,
) -> str:
    del progress_callback, cancel_event
    input_dir = Path(processing_results_dir)
    payload = {
        "samples": [
            {"name": sample.name, "positions": list(sample.positions)}
            for sample in samples
        ]
    }
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", encoding="utf-8", delete=False
        ) as handle:
            yaml.safe_dump(payload, handle, sort_keys=False)
            temp_path = Path(handle.name)
        summary = run_merge_traces(
            input_dir=input_dir,
            sample_yaml=temp_path,
            output_dir=input_dir / "traces_merged",
        )
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)
    return (
        f"Merged {summary['merged_positions']} positions into "
        f"{summary['merged_files']} file(s)"
    )


__all__ = [
    "get_channel_feature_config",
    "list_fluorescence_features",
    "list_phase_features",
    "normalize_samples",
    "parse_fov_range",
    "parse_positions_field",
    "read_samples_yaml",
    "run_complete_workflow",
    "run_merge",
    "run_merge_to_csv",
    "run_merge_traces",
]
