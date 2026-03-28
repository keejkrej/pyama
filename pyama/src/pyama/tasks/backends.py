"""Task backends for async pyama jobs."""

from collections import defaultdict
from queue import Queue
from threading import Lock
from typing import TYPE_CHECKING, cast

from pyama.tasks.manager import TaskManager, get_task_manager
from pyama.types import (
    ModelFitTaskResultHandle,
    StatisticsTaskResultHandle,
    TaskKind,
    TaskRecord,
)

if TYPE_CHECKING:
    from pyama.rpc.client import PyamaRpcClient
    from pyama.types.tasks import (
        MergeTaskRequest,
        ModelFitTaskRequest,
        ProcessingTaskRequest,
        StatisticsTaskRequest,
    )


class TaskBackend:
    """Small protocol-style base class for local and RPC backends."""

    def submit_processing(self, request: "ProcessingTaskRequest") -> TaskRecord:
        raise NotImplementedError

    def submit_merge(self, request: "MergeTaskRequest") -> TaskRecord:
        raise NotImplementedError

    def submit_model_fit(self, request: "ModelFitTaskRequest") -> TaskRecord:
        raise NotImplementedError

    def submit_statistics(self, request: "StatisticsTaskRequest") -> TaskRecord:
        raise NotImplementedError

    def get_task(self, task_id: str) -> TaskRecord | None:
        raise NotImplementedError

    def list_tasks(self) -> list[TaskRecord]:
        raise NotImplementedError

    def cancel_task(self, task_id: str) -> bool:
        raise NotImplementedError

    def subscribe(self, task_id: str) -> Queue:
        raise NotImplementedError

    def unsubscribe(self, task_id: str, queue: Queue) -> None:
        raise NotImplementedError

    def close(self) -> None:
        """Optional backend cleanup hook."""


class LocalTaskBackend(TaskBackend):
    """Direct in-process backend used by tests and library code."""

    def __init__(self, manager: TaskManager | None = None) -> None:
        self._manager = get_task_manager() if manager is None else manager

    def submit_processing(self, request: "ProcessingTaskRequest") -> TaskRecord:
        return self._manager.submit_processing(request)

    def submit_merge(self, request: "MergeTaskRequest") -> TaskRecord:
        return self._manager.submit_merge(request)

    def submit_model_fit(self, request: "ModelFitTaskRequest") -> TaskRecord:
        return self._manager.submit_model_fit(request)

    def submit_statistics(self, request: "StatisticsTaskRequest") -> TaskRecord:
        return self._manager.submit_statistics(request)

    def get_task(self, task_id: str) -> TaskRecord | None:
        return self._manager.get_task(task_id)

    def list_tasks(self) -> list[TaskRecord]:
        return self._manager.list_tasks()

    def cancel_task(self, task_id: str) -> bool:
        return self._manager.cancel_task(task_id)

    def subscribe(self, task_id: str) -> Queue:
        return self._manager.subscribe(task_id)

    def unsubscribe(self, task_id: str, queue: Queue) -> None:
        self._manager.unsubscribe(task_id, queue)


class RpcTaskBackend(TaskBackend):
    """RPC-backed backend used by GUI and other interactive entrypoints."""

    def __init__(self, client: "PyamaRpcClient") -> None:
        from pyama.rpc.artifacts import load_table_handle

        self._client = client
        self._load_table_handle = load_table_handle
        self._snapshots: dict[str, TaskRecord] = {}
        self._subscribers: dict[str, list[Queue]] = defaultdict(list)
        self._lock = Lock()
        self._client.set_notification_handler(self._handle_notification)

    def _handle_notification(self, method: str, params: object) -> None:
        if method != "events.task_snapshot" or not isinstance(params, dict):
            return
        params_dict = cast(dict[object, object], params)
        snapshot = params_dict.get("snapshot")
        if not isinstance(snapshot, TaskRecord):
            return
        materialized = self._materialize_task_record(snapshot)
        with self._lock:
            self._snapshots[materialized.id] = materialized
            subscribers = list(self._subscribers.get(materialized.id, []))
        for queue in subscribers:
            queue.put(materialized)

    def _materialize_task_record(self, record: TaskRecord) -> TaskRecord:
        result = record.result
        if result is None:
            return record
        if record.kind == TaskKind.MODEL_FIT and isinstance(
            result, ModelFitTaskResultHandle
        ):
            table = (
                None
                if result.results_table is None
                else self._load_table_handle(result.results_table)
            )
            return TaskRecord(
                id=record.id,
                kind=record.kind,
                status=record.status,
                request=record.request,
                progress=record.progress,
                result=(table, result.saved_csv_path),
                error_message=record.error_message,
            )
        if record.kind == TaskKind.STATISTICS and isinstance(
            result, StatisticsTaskResultHandle
        ):
            results_df = self._load_table_handle(result.results_table)
            traces = {
                sample_name: self._load_table_handle(table_handle)
                for sample_name, table_handle in result.trace_tables.items()
            }
            return TaskRecord(
                id=record.id,
                kind=record.kind,
                status=record.status,
                request=record.request,
                progress=record.progress,
                result=(results_df, traces, result.output_path),
                error_message=record.error_message,
            )
        return record

    def close(self) -> None:
        self._client.close()

    def _request_record(self, method: str, request: object) -> TaskRecord:
        record = cast(TaskRecord, self._client.request(method, {"request": request}))
        with self._lock:
            self._snapshots[record.id] = record
        return record

    def submit_processing(self, request: "ProcessingTaskRequest") -> TaskRecord:
        return self._request_record("tasks.submit_processing", request)

    def submit_merge(self, request: "MergeTaskRequest") -> TaskRecord:
        return self._request_record("tasks.submit_merge", request)

    def submit_model_fit(self, request: "ModelFitTaskRequest") -> TaskRecord:
        return self._request_record("tasks.submit_model_fit", request)

    def submit_statistics(self, request: "StatisticsTaskRequest") -> TaskRecord:
        return self._request_record("tasks.submit_statistics", request)

    def get_task(self, task_id: str) -> TaskRecord | None:
        result = self._client.request("tasks.get_task", {"task_id": task_id})
        if result is None:
            return None
        record = self._materialize_task_record(cast(TaskRecord, result))
        with self._lock:
            self._snapshots[task_id] = record
        return record

    def list_tasks(self) -> list[TaskRecord]:
        records = cast(list[TaskRecord], self._client.request("tasks.list_tasks", {}))
        materialized = [self._materialize_task_record(record) for record in records]
        with self._lock:
            for record in materialized:
                self._snapshots[record.id] = record
        return materialized

    def cancel_task(self, task_id: str) -> bool:
        return bool(self._client.request("tasks.cancel_task", {"task_id": task_id}))

    def subscribe(self, task_id: str) -> Queue:
        queue: Queue = Queue()
        with self._lock:
            self._subscribers[task_id].append(queue)
            snapshot = self._snapshots.get(task_id)
        if snapshot is not None:
            queue.put(snapshot)
        return queue

    def unsubscribe(self, task_id: str, queue: Queue) -> None:
        with self._lock:
            subscribers = self._subscribers.get(task_id)
            if not subscribers:
                return
            self._subscribers[task_id] = [
                existing for existing in subscribers if existing is not queue
            ]
            if not self._subscribers[task_id]:
                self._subscribers.pop(task_id, None)


__all__ = [
    "LocalTaskBackend",
    "RpcTaskBackend",
    "TaskBackend",
]
