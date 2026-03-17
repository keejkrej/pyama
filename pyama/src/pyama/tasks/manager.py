"""In-memory task manager and compatibility workflow wrapper."""

from collections.abc import Callable
from pathlib import Path
from queue import Queue
from threading import Event, Lock, Thread
from uuid import uuid4

from pyama.apps.modeling.fitting_service import FittingService as CoreFittingService
from pyama.apps.processing.merge import run_merge as run_merge_impl
from pyama.apps.processing.workflow.run import run_complete_workflow
from pyama.apps.statistics.service import (
    run_folder_statistics as run_folder_statistics_impl,
)
from pyama.apps.visualization.cache import VisualizationCache as CoreVisualizationCache
from pyama.tasks.broker import TaskBroker
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

TERMINAL_TASK_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
}


def _clone_progress(progress: TaskProgress | None) -> TaskProgress | None:
    if progress is None:
        return None
    return TaskProgress(
        task_id=progress.task_id,
        kind=progress.kind,
        step=progress.step,
        current=progress.current,
        total=progress.total,
        percent=progress.percent,
        message=progress.message,
        details=dict(progress.details),
    )


def _clone_record(record: TaskRecord) -> TaskRecord:
    return TaskRecord(
        id=record.id,
        kind=record.kind,
        status=record.status,
        request=record.request,
        progress=_clone_progress(record.progress),
        result=record.result,
        error_message=record.error_message,
    )


class TaskManager:
    """Run domain tasks in background threads and publish state snapshots."""

    def __init__(self) -> None:
        self._broker = TaskBroker()
        self._tasks: dict[str, TaskRecord] = {}
        self._cancel_events: dict[str, Event] = {}
        self._lock = Lock()

    def submit_processing(self, request: ProcessingTaskRequest) -> TaskRecord:
        return self._submit(TaskKind.PROCESSING, request, self._run_processing)

    def submit_merge(self, request: MergeTaskRequest) -> TaskRecord:
        return self._submit(TaskKind.MERGE, request, self._run_merge)

    def submit_model_fit(self, request: ModelFitTaskRequest) -> TaskRecord:
        return self._submit(TaskKind.MODEL_FIT, request, self._run_model_fit)

    def submit_statistics(self, request: StatisticsTaskRequest) -> TaskRecord:
        return self._submit(TaskKind.STATISTICS, request, self._run_statistics)

    def submit_visualization(self, request: VisualizationTaskRequest) -> TaskRecord:
        return self._submit(TaskKind.VISUALIZATION, request, self._run_visualization)

    def get_task(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            record = self._tasks.get(task_id)
            return None if record is None else _clone_record(record)

    def list_tasks(self) -> list[TaskRecord]:
        with self._lock:
            return [_clone_record(record) for record in self._tasks.values()]

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            record = self._tasks.get(task_id)
            cancel_event = self._cancel_events.get(task_id)
            if record is None or record.status in TERMINAL_TASK_STATUSES:
                return False
            record.status = TaskStatus.CANCELLED
            record.error_message = "Task cancelled"
            snapshot = _clone_record(record)
        if cancel_event is not None:
            cancel_event.set()
        self._broker.publish(snapshot)
        return True

    def subscribe(self, task_id: str) -> Queue:
        return self._broker.subscribe(task_id)

    def unsubscribe(self, task_id: str, queue: Queue) -> None:
        self._broker.unsubscribe(task_id, queue)

    def _submit(
        self,
        kind: TaskKind,
        request,
        runner: Callable[[str, object, Event], object],
    ) -> TaskRecord:
        task_id = uuid4().hex
        record = TaskRecord(
            id=task_id,
            kind=kind,
            status=TaskStatus.PENDING,
            request=request,
        )
        cancel_event = Event()
        with self._lock:
            self._tasks[task_id] = record
            self._cancel_events[task_id] = cancel_event
            snapshot = _clone_record(record)
        self._broker.publish(snapshot)
        Thread(
            target=self._run_task,
            args=(task_id, request, cancel_event, runner),
            daemon=True,
        ).start()
        return snapshot

    def _run_task(
        self,
        task_id: str,
        request,
        cancel_event: Event,
        runner: Callable[[str, object, Event], object],
    ) -> None:
        self._set_status(task_id, TaskStatus.RUNNING)
        try:
            result = runner(task_id, request, cancel_event)
        except Exception as exc:  # pragma: no cover - worker boundary
            if cancel_event.is_set():
                self._set_status(task_id, TaskStatus.CANCELLED, error_message=str(exc))
                return
            self._set_status(task_id, TaskStatus.FAILED, error_message=str(exc))
            return
        if cancel_event.is_set():
            self._set_status(task_id, TaskStatus.CANCELLED, error_message="Task cancelled")
            return
        self._set_status(task_id, TaskStatus.COMPLETED, result=result)

    def _set_status(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        result=None,
        error_message: str | None = None,
    ) -> None:
        with self._lock:
            record = self._tasks[task_id]
            if record.status == TaskStatus.CANCELLED and status != TaskStatus.CANCELLED:
                snapshot = _clone_record(record)
            else:
                record.status = status
                if result is not None:
                    record.result = result
                if error_message is not None:
                    record.error_message = error_message
                snapshot = _clone_record(record)
        self._broker.publish(snapshot)

    def _publish_progress(
        self,
        task_id: str,
        kind: TaskKind,
        step: str,
        *,
        current: int | None = None,
        total: int | None = None,
        percent: int | None = None,
        message: str = "",
        details: dict | None = None,
    ) -> None:
        progress = TaskProgress(
            task_id=task_id,
            kind=kind,
            step=step,
            current=current,
            total=total,
            percent=percent,
            message=message,
            details=dict(details or {}),
        )
        with self._lock:
            record = self._tasks[task_id]
            if record.status == TaskStatus.CANCELLED:
                snapshot = _clone_record(record)
            else:
                record.progress = progress
                snapshot = _clone_record(record)
        self._broker.publish(snapshot)

    def _run_processing(
        self,
        task_id: str,
        request: ProcessingTaskRequest,
        cancel_event: Event,
    ) -> dict:
        context = ensure_context(request.context)

        def progress_reporter(payload: dict) -> None:
            event_type = str(payload.get("event", "frame"))
            if event_type == "status":
                self._publish_progress(
                    task_id,
                    TaskKind.PROCESSING,
                    "workflow",
                    current=int(payload.get("completed_fovs", 0)),
                    total=int(payload.get("total_fovs", 0)),
                    percent=int(payload.get("progress_percent", 0)),
                    message=str(payload.get("message", "")),
                    details=payload,
                )
                return
            current = int(payload.get("t", 0))
            total = int(payload.get("T", 0))
            percent = int((current / total) * 100) if total > 0 else None
            self._publish_progress(
                task_id,
                TaskKind.PROCESSING,
                str(payload.get("step", "workflow")),
                current=current,
                total=total if total > 0 else None,
                percent=percent,
                message=str(payload.get("message", "")),
                details=payload,
            )

        success = run_complete_workflow(
            metadata=request.metadata,
            context=context,
            fov_start=request.fov_start,
            fov_end=request.fov_end,
            n_workers=request.n_workers,
            cancel_event=cancel_event,
            progress_reporter=progress_reporter,
        )
        if not success:
            raise RuntimeError("Processing workflow failed")
        return {"success": success, "output_dir": context.output_dir}

    def _run_merge(
        self,
        task_id: str,
        request: MergeTaskRequest,
        cancel_event: Event,
    ) -> dict:
        def progress_callback(current: int, total: int, message: str) -> None:
            percent = int((current / total) * 100) if total > 0 else None
            self._publish_progress(
                task_id,
                TaskKind.MERGE,
                "merge",
                current=current,
                total=total if total > 0 else None,
                percent=percent,
                message=message,
            )

        if cancel_event.is_set():
            raise RuntimeError("Task cancelled")
        message = run_merge_impl(
            request.samples,
            request.processing_results_dir,
            progress_callback=progress_callback,
        )
        return {"message": message}

    def _run_model_fit(
        self,
        task_id: str,
        request: ModelFitTaskRequest,
        cancel_event: Event,
    ):
        def progress_reporter(payload: dict) -> None:
            self._publish_progress(
                task_id,
                TaskKind.MODEL_FIT,
                str(payload.get("step", "model_fit")),
                current=payload.get("current"),
                total=payload.get("total"),
                percent=payload.get("progress"),
                message=str(payload.get("message", "")),
                details=payload,
            )

        if cancel_event.is_set():
            raise RuntimeError("Task cancelled")
        service = CoreFittingService(progress_reporter=progress_reporter)
        return service.fit_csv_file(
            request.csv_file,
            request.model_type,
            model_params=request.model_params,
            model_bounds=request.model_bounds,
            progress_reporter=progress_reporter,
        )

    def _run_statistics(
        self,
        task_id: str,
        request: StatisticsTaskRequest,
        cancel_event: Event,
    ):
        if cancel_event.is_set():
            raise RuntimeError("Task cancelled")
        self._publish_progress(
            task_id,
            TaskKind.STATISTICS,
            "statistics",
            message=f"Running {request.mode} statistics",
        )
        return run_folder_statistics_impl(
            request.folder_path,
            request.mode,
            normalize_by_area=request.normalize_by_area,
            fit_window_hours=request.fit_window_hours,
            area_filter_size=request.area_filter_size,
        )

    def _run_visualization(
        self,
        task_id: str,
        request: VisualizationTaskRequest,
        cancel_event: Event,
    ):
        if cancel_event.is_set():
            raise RuntimeError("Task cancelled")
        self._publish_progress(
            task_id,
            TaskKind.VISUALIZATION,
            "visualization_cache",
            message=f"Building cache for {request.channel_id}",
        )
        cache = CoreVisualizationCache(cache_root=request.cache_root)
        return cache.get_or_build_uint8(
            request.source_path,
            request.channel_id,
            force_rebuild=request.force_rebuild,
        )


_task_manager: TaskManager | None = None


def get_task_manager() -> TaskManager:
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager


class WorkflowTaskManager:
    """Compatibility wrapper around the generic task manager."""

    def __init__(self, task_manager: TaskManager | None = None) -> None:
        self._task_manager = task_manager or get_task_manager()
        self._cancel_event = Event()
        self._task_id: str | None = None

    def run(
        self,
        *,
        metadata,
        context,
        fov_start: int,
        fov_end: int,
        n_workers: int,
        progress_reporter: (
            Callable[[WorkflowProgressEvent | WorkflowStatusEvent], None] | None
        ) = None,
    ) -> bool:
        if self._cancel_event.is_set():
            return False

        record = self._task_manager.submit_processing(
            ProcessingTaskRequest(
                metadata=metadata,
                context=context,
                fov_start=fov_start,
                fov_end=fov_end,
                n_workers=n_workers,
            )
        )
        self._task_id = record.id
        queue = self._task_manager.subscribe(record.id)
        try:
            while True:
                snapshot = queue.get()
                if progress_reporter and snapshot.progress is not None:
                    details = snapshot.progress.details
                    if details.get("event") == "status":
                        progress_reporter(
                            WorkflowStatusEvent(
                                completed_fovs=int(details.get("completed_fovs", 0)),
                                total_fovs=int(details.get("total_fovs", 0)),
                                progress_percent=int(
                                    details.get("progress_percent", 0)
                                ),
                                message=str(details.get("message", "")),
                            )
                        )
                    elif snapshot.progress.kind == TaskKind.PROCESSING:
                        progress_reporter(
                            WorkflowProgressEvent(
                                worker_id=int(details.get("worker_id", -1)),
                                step=str(details.get("step", "workflow")),
                                fov=int(details.get("fov", -1)),
                                frame_index=int(details.get("t", 0)),
                                frame_total=int(details.get("T", 0)),
                                message=str(details.get("message", "")),
                            )
                        )
                if snapshot.status in TERMINAL_TASK_STATUSES:
                    return snapshot.status == TaskStatus.COMPLETED and bool(
                        (snapshot.result or {}).get("success", False)
                    )
        finally:
            self._task_manager.unsubscribe(record.id, queue)

    def cancel(self) -> None:
        self._cancel_event.set()
        if self._task_id is not None:
            self._task_manager.cancel_task(self._task_id)

    @property
    def cancel_event(self) -> Event:
        return self._cancel_event


__all__ = [
    "TERMINAL_TASK_STATUSES",
    "TaskManager",
    "WorkflowTaskManager",
    "get_task_manager",
]
