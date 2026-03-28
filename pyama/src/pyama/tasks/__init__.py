"""Public async-job facade for pyama consumers."""

from pathlib import Path
from queue import Queue
from threading import Lock

from pyama.rpc.client import PyamaRpcClient
from pyama.tasks.backends import LocalTaskBackend, RpcTaskBackend, TaskBackend
from pyama.types import (
    MergeTaskRequest,
    ModelFitTaskRequest,
    ProcessingTaskRequest,
    StatisticsTaskRequest,
    TaskKind,
    TaskProgress,
    TaskRecord,
    TaskStatus,
)

_backend_lock = Lock()
_backend: TaskBackend | None = None


def _get_backend() -> TaskBackend:
    global _backend
    with _backend_lock:
        if _backend is None:
            _backend = LocalTaskBackend()
        return _backend


def set_backend(backend: TaskBackend) -> None:
    global _backend
    with _backend_lock:
        current = _backend
        _backend = backend
    if current is not None and current is not backend:
        current.close()


def use_local_backend() -> None:
    set_backend(LocalTaskBackend())


def start_rpc_backend(*, cwd: Path | None = None) -> RpcTaskBackend:
    backend = RpcTaskBackend(PyamaRpcClient(cwd=cwd))
    set_backend(backend)
    return backend


def shutdown_backend() -> None:
    global _backend
    with _backend_lock:
        current = _backend
        _backend = None
    if current is not None:
        current.close()


def submit_processing(request: ProcessingTaskRequest) -> TaskRecord:
    return _get_backend().submit_processing(request)


def submit_merge(request: MergeTaskRequest) -> TaskRecord:
    return _get_backend().submit_merge(request)


def submit_model_fit(request: ModelFitTaskRequest) -> TaskRecord:
    return _get_backend().submit_model_fit(request)


def submit_statistics(request: StatisticsTaskRequest) -> TaskRecord:
    return _get_backend().submit_statistics(request)


def get_task(task_id: str) -> TaskRecord | None:
    return _get_backend().get_task(task_id)


def list_tasks() -> list[TaskRecord]:
    return _get_backend().list_tasks()


def cancel_task(task_id: str) -> bool:
    return _get_backend().cancel_task(task_id)


def subscribe(task_id: str) -> Queue:
    return _get_backend().subscribe(task_id)


def unsubscribe(task_id: str, queue: Queue) -> None:
    _get_backend().unsubscribe(task_id, queue)


__all__ = [
    "MergeTaskRequest",
    "ModelFitTaskRequest",
    "ProcessingTaskRequest",
    "StatisticsTaskRequest",
    "TaskKind",
    "TaskProgress",
    "TaskRecord",
    "TaskStatus",
    "cancel_task",
    "get_task",
    "list_tasks",
    "set_backend",
    "shutdown_backend",
    "start_rpc_backend",
    "submit_merge",
    "submit_model_fit",
    "submit_processing",
    "submit_statistics",
    "subscribe",
    "unsubscribe",
    "use_local_backend",
]
