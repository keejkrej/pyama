"""Task manager for handling background tasks."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from .database import TaskDatabase
from .models import TaskInfo, TaskStatus, TaskType
from .tasks import TaskRegistry

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages task execution (single task at a time)."""

    def __init__(self, db: TaskDatabase):
        """Initialize the task manager."""
        self.db = db
        self.current_task: Optional[TaskInfo] = None
        self._task_lock = asyncio.Lock()
        self._cancel_event: Optional[asyncio.Event] = None

    async def submit_task(
        self,
        task_type: TaskType,
        parameters: dict,
        input_file_path: Optional[str] = None,
        output_file_path: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Submit a new task.

        Returns:
            Tuple of (task_id, message)

        Raises:
            ValueError: If a task is already running
        """
        async with self._task_lock:
            if self.current_task and self.current_task.status in [
                TaskStatus.RUNNING,
                TaskStatus.PENDING,
            ]:
                raise ValueError(
                    f"A task is already running: {self.current_task.task_id}"
                )

            # Merge user parameters with defaults
            merged_params = TaskRegistry.merge_parameters(task_type, parameters)

            task_id = str(uuid.uuid4())
            task_info = TaskInfo(
                task_id=task_id,
                task_type=task_type,
                status=TaskStatus.PENDING,
                created_at=datetime.now(),
                parameters=merged_params,
                input_file_path=input_file_path,
                output_file_path=output_file_path,
            )

            self.current_task = task_info
            await self.db.create_task(task_info)

            # Start the task in the background
            asyncio.create_task(self._run_task(task_id, task_type))

            return task_id, "Task submitted successfully"

    async def get_task_info(self, task_id: str) -> Optional[TaskInfo]:
        """Get information about a task."""
        return await self.db.get_task(task_id)

    async def get_current_task(self) -> Optional[TaskInfo]:
        """
        Get the currently running task with latest progress from database.

        Returns:
            TaskInfo with up-to-date progress, or None if no task is running
        """
        if not self.current_task:
            return None

        # Always read from database to get latest progress
        return await self.db.get_task(self.current_task.task_id)

    async def list_all_tasks(self) -> list[TaskInfo]:
        """List all tasks from the database."""
        return await self.db.list_tasks()

    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task.

        Returns:
            True if task was cancelled, False otherwise
        """
        async with self._task_lock:
            task = await self.db.get_task(task_id)
            if not task or task.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                return False

            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            task.message = "Task cancelled by user"

            await self.db.update_task(task)

            if self._cancel_event:
                self._cancel_event.set()

            return True

    async def _run_task(self, task_id: str, task_type: TaskType):
        """Run a task in the background."""
        task = await self.db.get_task(task_id)
        self._cancel_event = asyncio.Event()

        try:
            # Update status to running
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            task.message = "Task is running"
            await self.db.update_task(task)
            logger.info(f"Starting task {task_id} of type {task_type}")

            # Get task class from registry
            task_class = TaskRegistry.get_task_class(task_type)

            # Create task instance
            task_instance = task_class(
                task_info=task,
                db=self.db,
                cancel_event=self._cancel_event,
            )

            # Execute the task
            result = await task_instance.execute()

            # Check if task was cancelled during execution
            if task.status == TaskStatus.CANCELLED:
                logger.info(f"Task {task_id} was cancelled")
                return

            # Mark as completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.progress = 100.0
            task.message = "Task completed successfully"
            task.result = result
            await self.db.update_task(task)
            logger.info(f"Task {task_id} completed successfully")

        except asyncio.CancelledError:
            # Task was cancelled
            logger.info(f"Task {task_id} was cancelled")
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            task.message = "Task cancelled by user"
            await self.db.update_task(task)

        except Exception as e:
            # Task failed
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error = str(e)
            task.message = f"Task failed: {e}"
            await self.db.update_task(task)

        finally:
            self._cancel_event = None
