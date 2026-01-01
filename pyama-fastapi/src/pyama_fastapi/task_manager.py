"""Task manager for handling background tasks."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from .models import TaskInfo, TaskStatus, TaskType

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages task execution (single task at a time)."""

    def __init__(self):
        """Initialize the task manager."""
        self.current_task: Optional[TaskInfo] = None
        self.task_history: dict[str, TaskInfo] = {}
        self._task_lock = asyncio.Lock()
        self._cancel_event: Optional[asyncio.Event] = None

    async def submit_task(
        self, task_type: TaskType, parameters: dict
    ) -> tuple[str, str]:
        """
        Submit a new task.

        Returns:
            Tuple of (task_id, message)

        Raises:
            ValueError: If a task is already running
        """
        async with self._task_lock:
            if self.current_task and self.current_task.status == TaskStatus.RUNNING:
                raise ValueError(
                    f"A task is already running: {self.current_task.task_id}"
                )

            task_id = str(uuid.uuid4())
            task_info = TaskInfo(
                task_id=task_id,
                task_type=task_type,
                status=TaskStatus.PENDING,
                created_at=datetime.now(),
            )

            self.current_task = task_info
            self.task_history[task_id] = task_info

            # Start the task in the background
            asyncio.create_task(self._run_task(task_id, task_type, parameters))

            return task_id, "Task submitted successfully"

    async def get_task_info(self, task_id: str) -> Optional[TaskInfo]:
        """Get information about a task."""
        return self.task_history.get(task_id)

    async def get_current_task(self) -> Optional[TaskInfo]:
        """Get the currently running task."""
        return self.current_task

    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task.

        Returns:
            True if task was cancelled, False otherwise
        """
        async with self._task_lock:
            task = self.task_history.get(task_id)
            if not task or task.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                return False

            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            task.message = "Task cancelled by user"

            if self._cancel_event:
                self._cancel_event.set()

            return True

    async def _run_task(self, task_id: str, task_type: TaskType, parameters: dict):
        """Run a task in the background."""
        task = self.task_history[task_id]
        self._cancel_event = asyncio.Event()

        try:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            task.message = "Task is running"
            logger.info(f"Starting task {task_id} of type {task_type}")

            # Execute the appropriate task
            if task_type == TaskType.DUMMY_SHORT:
                await self._dummy_task(task, duration=5, steps=5)
            elif task_type == TaskType.DUMMY_LONG:
                await self._dummy_task(task, duration=30, steps=10)
            elif task_type == TaskType.DUMMY_VERY_LONG:
                await self._dummy_task(task, duration=120, steps=20)
            else:
                raise ValueError(f"Unknown task type: {task_type}")

            # Check if task was cancelled
            if task.status == TaskStatus.CANCELLED:
                logger.info(f"Task {task_id} was cancelled")
                return

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.progress = 100.0
            task.message = "Task completed successfully"
            logger.info(f"Task {task_id} completed successfully")

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error = str(e)
            task.message = f"Task failed: {e}"

        finally:
            self._cancel_event = None

    async def _dummy_task(self, task: TaskInfo, duration: int, steps: int):
        """
        Simulate a long-running task.

        Args:
            task: The task info object to update
            duration: Total duration in seconds
            steps: Number of progress steps
        """
        sleep_time = duration / steps

        for step in range(steps):
            # Check for cancellation
            if self._cancel_event and self._cancel_event.is_set():
                return

            progress = ((step + 1) / steps) * 100
            task.progress = progress
            task.message = f"Processing step {step + 1}/{steps}"

            logger.debug(f"Task {task.task_id}: {progress:.1f}% complete")

            await asyncio.sleep(sleep_time)

        # Set final result
        task.result = {
            "message": "Dummy task completed",
            "steps_completed": steps,
            "duration": duration,
        }
