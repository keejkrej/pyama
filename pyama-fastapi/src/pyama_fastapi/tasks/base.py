"""Base task class for all background tasks."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from ..database import TaskDatabase
from ..models import TaskInfo

logger = logging.getLogger(__name__)


class BaseTask(ABC):
    """
    Abstract base class for all tasks.

    To create a new task type:
    1. Inherit from BaseTask
    2. Implement the execute() method
    3. Use update_progress() to report progress
    4. Register the task in TaskRegistry

    Example:
        class MyTask(BaseTask):
            async def execute(self) -> dict[str, Any]:
                await self.update_progress(0, "Starting...")

                # Do some work
                result = await self.do_work()

                await self.update_progress(50, "Halfway done")

                # Do more work
                final_result = await self.finish_work()

                await self.update_progress(100, "Completed")

                return {"result": final_result}
    """

    def __init__(
        self,
        task_info: TaskInfo,
        db: TaskDatabase,
        cancel_event: asyncio.Event,
    ):
        """
        Initialize the task.

        Args:
            task_info: TaskInfo object containing task metadata
            db: Database instance for persisting updates
            cancel_event: Event to signal task cancellation
        """
        self.task_info = task_info
        self.db = db
        self.cancel_event = cancel_event
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    @abstractmethod
    async def execute(self) -> dict[str, Any]:
        """
        Execute the task logic.

        This method must be implemented by all task subclasses.
        It should perform the actual work and return a result dictionary.

        Returns:
            Dictionary containing task results

        Raises:
            Exception: Any exception will be caught by TaskManager and
                      stored in task_info.error
        """
        pass

    async def update_progress(self, progress: float, message: str = "") -> None:
        """
        Update task progress and save to database.

        Args:
            progress: Progress percentage (0-100)
            message: Status message to display
        """
        self.task_info.progress = progress
        self.task_info.message = message
        await self.db.update_task(self.task_info)
        self.logger.debug(f"Task {self.task_info.task_id}: {progress:.1f}% - {message}")

    def is_cancelled(self) -> bool:
        """
        Check if the task has been cancelled.

        Returns:
            True if task should stop executing
        """
        return self.cancel_event.is_set()

    async def check_cancelled(self) -> None:
        """
        Check if task is cancelled and return early if so.

        Usage:
            await self.check_cancelled()  # Returns early if cancelled
        """
        if self.is_cancelled():
            self.logger.info(f"Task {self.task_info.task_id} was cancelled")
            raise asyncio.CancelledError("Task was cancelled")

    @property
    def parameters(self) -> dict[str, Any]:
        """Get task parameters."""
        return self.task_info.parameters

    @property
    def input_file_path(self) -> Optional[str]:
        """Get input file path."""
        return self.task_info.input_file_path

    @property
    def output_file_path(self) -> Optional[str]:
        """Get output file path."""
        return self.task_info.output_file_path
