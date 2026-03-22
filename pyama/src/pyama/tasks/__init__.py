"""Public task facade for pyama consumers."""

from pyama.tasks.manager import get_task_manager
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

__all__ = [
    "MergeTaskRequest",
    "ModelFitTaskRequest",
    "ProcessingTaskRequest",
    "StatisticsTaskRequest",
    "TaskKind",
    "TaskProgress",
    "TaskRecord",
    "TaskStatus",
    "VisualizationTaskRequest",
    "cancel_task",
    "get_task",
    "list_tasks",
    "submit_merge",
    "submit_model_fit",
    "submit_processing",
    "submit_statistics",
    "submit_visualization",
    "subscribe",
    "unsubscribe",
]
