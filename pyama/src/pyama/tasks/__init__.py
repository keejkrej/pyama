"""Public task facade for pyama consumers."""

from pathlib import Path

from pyama.apps.modeling.fitting import analyze_fitting_quality
from pyama.apps.modeling.models import get_model, list_models
from pyama.apps.processing.extraction.features import (
    list_fluorescence_features,
    list_phase_features,
)
from pyama.apps.processing.merge import parse_fov_range, read_samples_yaml
from pyama.apps.statistics import discover_sample_pairs
from pyama.apps.statistics.metrics import evaluate_onset_trace
from pyama.apps.visualization.cache import CachedStack
from pyama.io import load_microscopy_file
from pyama.io.config.results import load_processing_results_yaml
from pyama.io.csv.analysis import load_analysis_csv
from pyama.io.csv.processing import (
    extract_all_cells_data,
    get_dataframe,
    update_cell_quality,
    write_dataframe,
)
from pyama.io.path.trace import resolve_trace_path
from pyama.tasks.manager import TaskManager, WorkflowTaskManager, get_task_manager
from pyama.types.processing import ensure_context
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
    WorkflowProgressEvent,
    WorkflowStatusEvent,
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


class FittingService:
    """Task-backed facade preserving the previous fitting-service API."""

    def __init__(self, progress_reporter=None) -> None:
        self._progress_reporter = progress_reporter

    def fit_csv_file(
        self,
        csv_file: Path,
        model_type: str,
        model_params: dict[str, float] | None = None,
        model_bounds: dict[str, tuple[float, float]] | None = None,
        *,
        progress_reporter=None,
    ):
        reporter = progress_reporter or self._progress_reporter
        record = submit_model_fit(
            ModelFitTaskRequest(
                csv_file=csv_file,
                model_type=model_type,
                model_params=model_params,
                model_bounds=model_bounds,
            )
        )
        snapshot = _wait_for_task(
            record.id,
            progress_handler=(
                (lambda progress: reporter(dict(progress.details)))
                if reporter is not None
                else None
            ),
        )
        if snapshot.status != TaskStatus.COMPLETED:
            raise RuntimeError(snapshot.error_message or "Fitting task failed")
        return snapshot.result


def run_merge(
    samples: list[dict],
    processing_results_dir: Path | str,
    progress_callback=None,
) -> str:
    record = submit_merge(
        MergeTaskRequest(
            samples=list(samples),
            processing_results_dir=Path(processing_results_dir),
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
    fit_window_hours: float = 4.0,
    area_filter_size: int = 10,
):
    record = submit_statistics(
        StatisticsTaskRequest(
            mode=mode,
            folder_path=Path(folder_path),
            normalize_by_area=normalize_by_area,
            fit_window_hours=fit_window_hours,
            area_filter_size=area_filter_size,
        )
    )
    snapshot = _wait_for_task(record.id)
    if snapshot.status != TaskStatus.COMPLETED:
        raise RuntimeError(snapshot.error_message or "Statistics task failed")
    return snapshot.result


class VisualizationCache:
    """Task-backed facade for visualization cache creation."""

    def __init__(self, cache_root: Path | None = None) -> None:
        self._cache_root = cache_root
        from pyama.apps.visualization.cache import VisualizationCache as CoreCache

        self._cache = CoreCache(cache_root=cache_root)

    def get_or_build_uint8(
        self,
        source_path: Path,
        channel_id: str,
        *,
        force_rebuild: bool = False,
    ) -> CachedStack:
        record = submit_visualization(
            VisualizationTaskRequest(
                source_path=source_path,
                channel_id=channel_id,
                cache_root=self._cache_root,
                force_rebuild=force_rebuild,
            )
        )
        snapshot = _wait_for_task(record.id)
        if snapshot.status != TaskStatus.COMPLETED:
            raise RuntimeError(snapshot.error_message or "Visualization task failed")
        return snapshot.result

    def load_frame(self, cached_path: Path, frame: int):
        return self._cache.load_frame(cached_path, frame)

    def load_slice(self, cached_path: Path, start: int, end: int):
        return self._cache.load_slice(cached_path, start, end)


__all__ = [
    "CachedStack",
    "FittingService",
    "MergeTaskRequest",
    "ModelFitTaskRequest",
    "ProcessingTaskRequest",
    "StatisticsTaskRequest",
    "TaskKind",
    "TaskManager",
    "TaskProgress",
    "TaskRecord",
    "TaskStatus",
    "VisualizationCache",
    "VisualizationTaskRequest",
    "WorkflowProgressEvent",
    "WorkflowStatusEvent",
    "WorkflowTaskManager",
    "analyze_fitting_quality",
    "cancel_task",
    "discover_sample_pairs",
    "ensure_context",
    "evaluate_onset_trace",
    "extract_all_cells_data",
    "get_dataframe",
    "get_model",
    "get_task",
    "get_task_manager",
    "list_fluorescence_features",
    "list_models",
    "list_phase_features",
    "list_tasks",
    "load_analysis_csv",
    "load_microscopy_file",
    "load_processing_results_yaml",
    "parse_fov_range",
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
    "write_dataframe",
]
