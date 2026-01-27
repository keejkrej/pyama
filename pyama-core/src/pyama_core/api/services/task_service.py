"""Task management service."""

import asyncio
import logging
from pathlib import Path
from typing import Any

from pyama_core.api.database import TaskDB, get_db
from pyama_core.types.api import TaskResponse, TaskStatus, TaskListResponse
from pyama_core.types.processing import ProcessingConfig

logger = logging.getLogger(__name__)


class TaskServiceError(Exception):
    """Raised when a task operation fails."""

    pass


class TaskNotFoundError(TaskServiceError):
    """Raised when a task is not found."""

    pass


class TaskService:
    """Service for task CRUD operations and execution."""

    def __init__(self, db: TaskDB | None = None):
        """Initialize task service.

        Args:
            db: TaskDB instance. Uses global instance if None.
        """
        self.db = db or get_db()

    def create_task(
        self,
        file_path: str,
        config: ProcessingConfig,
        fake: bool = False,
        start_immediately: bool = True,
        output_dir: str | None = None,
    ) -> TaskResponse:
        """Create a new processing task.

        Args:
            file_path: Path to microscopy file to process
            config: Processing configuration
            fake: If True, run a 60-second simulated task
            start_immediately: If True, start task execution immediately
            output_dir: Directory for processing outputs (required for real tasks)

        Returns:
            TaskResponse with task ID and initial status
        """
        task = self.db.create_task(file_path=file_path, config=config.model_dump(), fake=fake)
        logger.info("Created task %s for file: %s (fake=%s)", task.id, file_path, fake)

        if start_immediately:
            if fake:
                asyncio.create_task(self._run_fake_task(task.id))
            else:
                asyncio.create_task(
                    self._run_real_task(task.id, file_path, config, output_dir=output_dir)
                )

        return task

    def list_tasks(self) -> TaskListResponse:
        """List all tasks.

        Returns:
            TaskListResponse with tasks list and total count
        """
        tasks = self.db.list_tasks()
        return TaskListResponse(tasks=tasks, total=len(tasks))

    def get_task(self, task_id: str) -> TaskResponse:
        """Get task by ID.

        Args:
            task_id: Task ID (UUID)

        Returns:
            TaskResponse with task details

        Raises:
            TaskNotFoundError: If task not found
        """
        task = self.db.get_task(task_id)
        if task is None:
            raise TaskNotFoundError(f"Task not found: {task_id}")
        return task

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task.

        Args:
            task_id: Task ID (UUID)

        Returns:
            True if successfully cancelled

        Raises:
            TaskNotFoundError: If task not found
            TaskServiceError: If task cannot be cancelled (wrong status)
        """
        task = self.get_task(task_id)  # Raises TaskNotFoundError if not found

        if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
            raise TaskServiceError(f"Cannot cancel task with status: {task.status}")

        success = self.db.cancel_task(task_id)
        if success:
            logger.info("Cancelled task: %s", task_id)
        return success

    async def _run_fake_task(self, task_id: str) -> None:
        """Run a fake 60-second task with progress updates."""
        try:
            # Transition to RUNNING
            self.db.update_task_status(
                task_id, TaskStatus.RUNNING, phase="fake", total_fovs=60
            )

            # Sleep with progress updates every second
            for i in range(60):
                await asyncio.sleep(1)
                self.db.update_task_status(
                    task_id,
                    TaskStatus.RUNNING,
                    current_fov=i + 1,
                    progress_percent=(i + 1) / 60 * 100,
                    progress_message=f"Fake processing... {i + 1}/60 seconds",
                )

            # Transition to COMPLETED
            self.db.update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                result={"output_dir": "/fake/output", "summary": {"fake": True}},
            )
        except Exception as e:
            logger.exception("Fake task %s failed: %s", task_id, e)
            self.db.update_task_status(
                task_id,
                TaskStatus.FAILED,
                error_message=str(e),
            )

    async def _run_real_task(
        self,
        task_id: str,
        file_path: str,
        config: ProcessingConfig,
        output_dir: str | None = None,
    ) -> None:
        """Run a real processing task."""
        try:
            # Import here to avoid circular imports
            from pyama_core.io import load_microscopy_file
            from pyama_core.processing.workflow.worker import WorkflowWorker

            # Transition to RUNNING
            self.db.update_task_status(
                task_id,
                TaskStatus.RUNNING,
                phase="loading",
                progress_message="Loading microscopy file...",
            )

            # Load microscopy file
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            _, metadata = load_microscopy_file(file_path_obj)

            # Create output directory
            if output_dir is None:
                raise ValueError("output_dir is required for real tasks")
            output_path = Path(output_dir) / task_id
            output_path.mkdir(parents=True, exist_ok=True)

            # Parse FOV selection from config
            from pyama_core.processing.merge.run import parse_fov_range

            fovs_param = config.params.fovs
            if fovs_param:
                fov_list = parse_fov_range(fovs_param)
                invalid = [f for f in fov_list if f < 0 or f >= metadata.n_fovs]
                if invalid:
                    raise ValueError(
                        f"Invalid FOV indices: {invalid} (valid: 0-{metadata.n_fovs - 1})"
                    )
            else:
                fov_list = list(range(metadata.n_fovs))
            self.db.update_task_status(
                task_id,
                TaskStatus.RUNNING,
                phase="processing",
                total_fovs=len(fov_list),
                current_fov=0,
                progress_percent=0,
                progress_message=f"Processing {len(fov_list)} FOVs...",
            )

            # Read processing parallelism from config params
            batch_size = config.params.batch_size or min(10, len(fov_list))
            n_workers = config.params.n_workers or 4

            # Create worker and run in thread
            worker = WorkflowWorker(
                metadata=metadata,
                config=config,
                output_dir=output_path,
                fov_list=fov_list,
                batch_size=batch_size,
                n_workers=n_workers,
            )

            # Run synchronous workflow in thread pool
            success, message = await asyncio.to_thread(worker.run)

            if success:
                self.db.update_task_status(
                    task_id,
                    TaskStatus.COMPLETED,
                    progress_percent=100,
                    result={
                        "output_dir": str(output_path),
                        "summary": {"message": message},
                    },
                )
            else:
                self.db.update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    error_message=message,
                )

        except Exception as e:
            logger.exception("Task %s failed: %s", task_id, e)
            self.db.update_task_status(
                task_id,
                TaskStatus.FAILED,
                error_message=str(e),
            )
