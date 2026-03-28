"""In-memory task manager for asynchronous pyama jobs."""

from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
import tempfile
from queue import Queue
from threading import Event, Lock, Thread
from uuid import uuid4
import yaml

from pyama.apps.modeling.service import fit_csv_file as fit_csv_file_impl
from pyama.apps.processing.merge import run_merge_traces as run_merge_impl
from pyama.apps.processing.service import run_complete_workflow
from pyama.apps.statistics.service import (
    run_folder_statistics as run_folder_statistics_impl,
)
from pyama.tasks.broker import TaskBroker
from pyama.types.tasks import ProgressPayload
from pyama.types.tasks import (
    MergeTaskRequest,
    ModelFitTaskRequest,
    ProcessingTaskRequest,
    StatisticsTaskRequest,
    TaskKind,
    TaskProgress,
    TaskRecord,
    TaskStatus,
)
from pyama.utils.progress import build_progress_payload

TERMINAL_TASK_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
}


def _clone_progress(progress: TaskProgress | None) -> TaskProgress | None:
    if progress is None:
        return None
    return replace(progress, details=dict(progress.details))


def _clone_record(record: TaskRecord) -> TaskRecord:
    return replace(record, progress=_clone_progress(record.progress))


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
            updated_record = replace(
                record,
                status=TaskStatus.CANCELLED,
                error_message="Task cancelled",
            )
            self._tasks[task_id] = updated_record
            snapshot = _clone_record(updated_record)
        if cancel_event is not None:
            cancel_event.set()
        self._broker.publish(snapshot)
        return True

    def subscribe(self, task_id: str) -> Queue:
        queue = self._broker.subscribe(task_id)
        snapshot = self.get_task(task_id)
        if snapshot is not None:
            queue.put(snapshot)
        return queue

    def unsubscribe(self, task_id: str, queue: Queue) -> None:
        self._broker.unsubscribe(task_id, queue)

    def _submit(
        self,
        kind: TaskKind,
        request,
        runner: Callable[..., object],
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
        runner: Callable[..., object],
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
            self._set_status(
                task_id, TaskStatus.CANCELLED, error_message="Task cancelled"
            )
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
                updated_record = replace(
                    record,
                    status=status,
                    result=record.result if result is None else result,
                    error_message=(
                        record.error_message if error_message is None else error_message
                    ),
                )
                self._tasks[task_id] = updated_record
                snapshot = _clone_record(updated_record)
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
        details: Mapping[str, object] | None = None,
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
                updated_record = replace(record, progress=progress)
                self._tasks[task_id] = updated_record
                snapshot = _clone_record(updated_record)
        self._broker.publish(snapshot)

    def _publish_payload_progress(
        self,
        task_id: str,
        kind: TaskKind,
        payload: ProgressPayload,
    ) -> None:
        self._publish_progress(
            task_id,
            kind,
            str(payload.get("step", kind.value)),
            current=payload.get("current"),
            total=payload.get("total"),
            percent=payload.get("progress"),
            message=str(payload.get("message", "")),
            details=payload,
        )

    def _run_processing(
        self,
        task_id: str,
        request: ProcessingTaskRequest,
        cancel_event: Event,
    ) -> dict:
        config = request.config
        output_dir = request.output_dir

        if config.params.positions.strip().lower() == "all":
            selected_positions = list(range(request.metadata.n_positions))
        else:
            from pyama.utils.position import parse_position_range

            selected_positions = parse_position_range(
                config.params.positions, length=request.metadata.n_positions
            )

        channels = config.channels
        fl_count = 0 if channels is None else len(channels.fl)
        total_channels = 0 if channels is None else 1 + fl_count
        stage_units = {
            "roi": len(selected_positions)
            * max(1, total_channels)
            * max(1, int(request.metadata.n_frames)),
            "background_estimation": len(selected_positions)
            * fl_count
            * max(1, int(request.metadata.n_frames)),
            "extraction": len(selected_positions)
            * max(1, int(request.metadata.n_frames)),
        }
        workflow_total = max(1, sum(stage_units.values()))
        stage_progress: dict[tuple[str, int, int | None], int] = {}

        def progress_reporter(payload: ProgressPayload) -> None:
            step = str(payload.get("step", "workflow"))
            position = int(payload.get("position", -1))
            channel = payload.get("channel")
            channel_id = int(channel) if isinstance(channel, (int, str)) else None
            current = int(payload.get("t", 0)) + 1
            total = int(payload.get("T", 0))
            current = min(current, total) if total > 0 else current

            progress_key = (
                step,
                position,
                channel_id
                if step in {"roi", "background_estimation", "extraction"}
                else None,
            )
            previous = stage_progress.get(progress_key, 0)
            if current > previous:
                stage_progress[progress_key] = current

            workflow_current = sum(stage_progress.values())
            workflow_percent = (
                int((workflow_current / workflow_total) * 100)
                if workflow_total > 0
                else None
            )
            self._publish_progress(
                task_id,
                TaskKind.PROCESSING,
                step,
                current=workflow_current,
                total=workflow_total,
                percent=workflow_percent,
                message=str(payload.get("message", "")),
                details={
                    **payload,
                    "overall_current": workflow_current,
                    "overall_total": workflow_total,
                    "overall_percent": workflow_percent,
                    "step_current": current,
                    "step_total": total,
                },
            )

        success = run_complete_workflow(
            metadata=request.metadata,
            config=config,
            output_dir=output_dir,
            cancel_event=cancel_event,
            progress_reporter=progress_reporter,
        )
        if not success:
            raise RuntimeError("Processing workflow failed")
        return {"success": success, "output_dir": output_dir}

    def _run_merge(
        self,
        task_id: str,
        request: MergeTaskRequest,
        cancel_event: Event,
    ) -> dict:
        if cancel_event.is_set():
            raise RuntimeError("Task cancelled")

        input_dir = request.input_dir or request.processing_results_dir
        if input_dir is None:
            raise RuntimeError("Merge input_dir is required")
        output_dir = request.output_dir or (input_dir / "traces_merged")

        samples = [
            {"name": sample.name, "positions": list(sample.positions)}
            for sample in request.samples
        ]
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", encoding="utf-8", delete=False
            ) as handle:
                yaml.safe_dump({"samples": samples}, handle, sort_keys=False)
                temp_path = Path(handle.name)

            summary = run_merge_impl(
                input_dir=input_dir,
                sample_yaml=temp_path,
                output_dir=output_dir,
            )
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink(missing_ok=True)

        self._publish_payload_progress(
            task_id,
            TaskKind.MERGE,
            build_progress_payload(
                step="merge",
                current=int(summary["merged_positions"]),
                total=int(summary["merged_positions"]),
                message=(
                    f"Merged {summary['merged_positions']} positions into "
                    f"{summary['merged_files']} file(s)"
                ),
            ),
        )
        return {
            "message": (
                f"Merged {summary['merged_positions']} positions into "
                f"{summary['merged_files']} file(s)"
            ),
            "output_dir": summary["output_dir"],
            "merged_positions": summary["merged_positions"],
            "merged_files": summary["merged_files"],
            "merged_rows": summary["merged_rows"],
        }

    def _run_model_fit(
        self,
        task_id: str,
        request: ModelFitTaskRequest,
        cancel_event: Event,
    ):
        def progress_reporter(payload: ProgressPayload) -> None:
            self._publish_payload_progress(task_id, TaskKind.MODEL_FIT, payload)

        if cancel_event.is_set():
            raise RuntimeError("Task cancelled")
        return fit_csv_file_impl(
            request.csv_file,
            request.model_type,
            frame_interval_minutes=request.frame_interval_minutes,
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
        def progress_reporter(payload: ProgressPayload) -> None:
            self._publish_payload_progress(task_id, TaskKind.STATISTICS, payload)

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
            frame_interval_minutes=request.frame_interval_minutes,
            fit_window_min=request.fit_window_min,
            area_filter_size=request.area_filter_size,
            progress_reporter=progress_reporter,
            cancel_event=cancel_event,
        )

_task_manager: TaskManager | None = None


def get_task_manager() -> TaskManager:
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager


__all__ = ["TERMINAL_TASK_STATUSES", "TaskManager", "get_task_manager"]
