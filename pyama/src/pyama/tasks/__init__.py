"""Public task facade for pyama consumers."""

from collections.abc import Callable
from pathlib import Path
from typing import cast

from pyama.apps.modeling.fitting import analyze_fitting_quality
from pyama.apps.modeling.models import get_model, list_models
from pyama.apps.processing.extract import (
    list_fluorescence_features,
    list_phase_features,
)
from pyama.apps.processing.merge import normalize_samples
from pyama.apps.processing.service import (
    parse_fov_range,
    parse_positions_field,
    read_samples_yaml,
)
from pyama.apps.statistics import discover_sample_pairs
from pyama.apps.statistics.metrics import evaluate_onset_trace
from pyama.apps.visualization.service import (
    CachedStack,
    load_frame as core_load_frame,
    load_slice as core_load_slice,
)
from pyama.io import load_microscopy_file
from pyama.io.config import scan_processing_results
from pyama.io.csv import load_analysis_csv
from pyama.io.csv import (
    extract_all_rois_data,
    get_dataframe,
    update_roi_quality,
    write_dataframe,
)
from pyama.io.path import resolve_trace_path
from pyama.tasks.manager import TaskManager, get_task_manager
from pyama.types.processing import MergeSample
from pyama.types.progress_payload import ProgressPayload
from pyama.types.tasks import (
    MergeTaskRequest,
    ModelFitTaskRequest,
    ProcessingTaskRequest,
    StatisticsTaskRequest,
    TaskKind,
    TaskProgress,
    TaskRecord,
    TaskStatus,
    VisualizationTaskRequest,
)


def _wait_for_task(task_id: str, progress_handler=None) -> TaskRecord:
    manager = get_task_manager()
    queue = manager.subscribe(task_id)
    try:
        while True:
            snapshot = queue.get()
            if progress_handler and snapshot.progress is not None:
                progress_handler(snapshot.progress)
            if snapshot.status in {
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            }:
                return snapshot
    finally:
        manager.unsubscribe(task_id, queue)


def submit_processing(request: ProcessingTaskRequest) -> TaskRecord:
    return get_task_manager().submit_processing(request)


def submit_merge(request: MergeTaskRequest) -> TaskRecord:
    return get_task_manager().submit_merge(request)


def submit_model_fit(request: ModelFitTaskRequest) -> TaskRecord:
    return get_task_manager().submit_model_fit(request)


def submit_statistics(request: StatisticsTaskRequest) -> TaskRecord:
    return get_task_manager().submit_statistics(request)


def submit_visualization(request: VisualizationTaskRequest) -> TaskRecord:
    return get_task_manager().submit_visualization(request)


def get_task(task_id: str) -> TaskRecord | None:
    return get_task_manager().get_task(task_id)


def list_tasks() -> list[TaskRecord]:
    return get_task_manager().list_tasks()


def cancel_task(task_id: str) -> bool:
    return get_task_manager().cancel_task(task_id)


def subscribe(task_id: str):
    return get_task_manager().subscribe(task_id)


def unsubscribe(task_id: str, queue) -> None:
    get_task_manager().unsubscribe(task_id, queue)


def fit_csv_file(
    csv_file: Path,
    model_type: str,
    model_params: dict[str, float] | None = None,
    model_bounds: dict[str, tuple[float, float]] | None = None,
    *,
    frame_interval_minutes: float = 10.0,
    progress_reporter: Callable[[ProgressPayload], None] | None = None,
):
    record = submit_model_fit(
        ModelFitTaskRequest(
            csv_file=csv_file,
            model_type=model_type,
            frame_interval_minutes=frame_interval_minutes,
            model_params=model_params,
            model_bounds=model_bounds,
        )
    )
    snapshot = _wait_for_task(
        record.id,
        progress_handler=(
            (
                lambda progress: progress_reporter(
                    cast(ProgressPayload, dict(progress.details))
                )
            )
            if progress_reporter is not None
            else None
        ),
    )
    if snapshot.status != TaskStatus.COMPLETED:
        raise RuntimeError(snapshot.error_message or "Fitting task failed")
    return snapshot.result


def run_merge(
    samples: list[MergeSample],
    input_dir: Path | str,
    progress_callback=None,
    output_dir: Path | str | None = None,
) -> str:
    record = submit_merge(
        MergeTaskRequest(
            samples=list(samples),
            input_dir=Path(input_dir),
            output_dir=None if output_dir is None else Path(output_dir),
        )
    )
    snapshot = _wait_for_task(
        record.id,
        progress_handler=(
            (
                lambda progress: progress_callback(
                    progress.current or 0,
                    progress.total or 0,
                    progress.message,
                )
            )
            if progress_callback is not None
            else None
        ),
    )
    if snapshot.status != TaskStatus.COMPLETED:
        raise RuntimeError(snapshot.error_message or "Merge task failed")
    return str((snapshot.result or {}).get("message", ""))


def run_folder_statistics(
    folder_path,
    mode: str,
    *,
    normalize_by_area: bool = True,
    frame_interval_minutes: float = 10.0,
    fit_window_min: float = 240.0,
    area_filter_size: int = 10,
):
    record = submit_statistics(
        StatisticsTaskRequest(
            mode=mode,
            folder_path=Path(folder_path),
            normalize_by_area=normalize_by_area,
            frame_interval_minutes=frame_interval_minutes,
            fit_window_min=fit_window_min,
            area_filter_size=area_filter_size,
        )
    )
    snapshot = _wait_for_task(record.id)
    if snapshot.status != TaskStatus.COMPLETED:
        raise RuntimeError(snapshot.error_message or "Statistics task failed")
    return snapshot.result


def get_or_build_uint8(
    source_path: Path,
    channel_id: str,
    *,
    cache_root: Path | None = None,
    force_rebuild: bool = False,
) -> CachedStack:
    record = submit_visualization(
        VisualizationTaskRequest(
            source_path=source_path,
            channel_id=channel_id,
            cache_root=cache_root,
            force_rebuild=force_rebuild,
        )
    )
    snapshot = _wait_for_task(record.id)
    if snapshot.status != TaskStatus.COMPLETED:
        raise RuntimeError(snapshot.error_message or "Visualization task failed")
    return snapshot.result


def load_cached_frame(cached_path: Path, frame: int):
    return core_load_frame(cached_path, frame)


def load_cached_slice(cached_path: Path, start: int, end: int):
    return core_load_slice(cached_path, start, end)


# Legacy aliases kept so the existing shells compile while they migrate to ROI terminology.
extract_all_cells_data = extract_all_rois_data
update_cell_quality = update_roi_quality


__all__ = [
    "CachedStack",
    "MergeTaskRequest",
    "ModelFitTaskRequest",
    "ProcessingTaskRequest",
    "StatisticsTaskRequest",
    "TaskKind",
    "TaskManager",
    "TaskProgress",
    "TaskRecord",
    "TaskStatus",
    "VisualizationTaskRequest",
    "analyze_fitting_quality",
    "cancel_task",
    "discover_sample_pairs",
    "evaluate_onset_trace",
    "extract_all_cells_data",
    "extract_all_rois_data",
    "fit_csv_file",
    "get_dataframe",
    "get_model",
    "get_or_build_uint8",
    "get_task",
    "get_task_manager",
    "list_fluorescence_features",
    "list_models",
    "list_phase_features",
    "list_tasks",
    "load_analysis_csv",
    "load_cached_frame",
    "load_cached_slice",
    "load_microscopy_file",
    "normalize_samples",
    "scan_processing_results",
    "parse_fov_range",
    "parse_positions_field",
    "read_samples_yaml",
    "resolve_trace_path",
    "run_folder_statistics",
    "run_merge",
    "submit_merge",
    "submit_model_fit",
    "submit_processing",
    "submit_statistics",
    "submit_visualization",
    "subscribe",
    "unsubscribe",
    "update_cell_quality",
    "update_roi_quality",
    "write_dataframe",
]
