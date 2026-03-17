"""Thread-safe in-process task subscriptions."""

from queue import Queue
from threading import Lock

from pyama.types.tasks import TaskRecord


class TaskBroker:
    """Fan-out broker for task state snapshots."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[Queue]] = {}
        self._lock = Lock()

    def subscribe(self, task_id: str) -> Queue:
        queue: Queue = Queue()
        with self._lock:
            self._subscribers.setdefault(task_id, set()).add(queue)
        return queue

    def unsubscribe(self, task_id: str, queue: Queue) -> None:
        with self._lock:
            subscribers = self._subscribers.get(task_id)
            if not subscribers:
                return
            subscribers.discard(queue)
            if not subscribers:
                self._subscribers.pop(task_id, None)

    def publish(self, record: TaskRecord) -> None:
        with self._lock:
            subscribers = list(self._subscribers.get(record.id, set()))
        for queue in subscribers:
            queue.put(record)


__all__ = ["TaskBroker"]
