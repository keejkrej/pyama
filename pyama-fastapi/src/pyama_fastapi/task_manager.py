"""Task manager for handling background tasks."""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import tiktoken

from .database import TaskDatabase
from .models import TaskInfo, TaskStatus, TaskType

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

            task_id = str(uuid.uuid4())
            task_info = TaskInfo(
                task_id=task_id,
                task_type=task_type,
                status=TaskStatus.PENDING,
                created_at=datetime.now(),
                parameters=parameters,
                input_file_path=input_file_path,
                output_file_path=output_file_path,
            )

            self.current_task = task_info
            await self.db.create_task(task_info)

            # Start the task in the background
            asyncio.create_task(self._run_task(task_id, task_type, parameters))

            return task_id, "Task submitted successfully"

    async def get_task_info(self, task_id: str) -> Optional[TaskInfo]:
        """Get information about a task."""
        return await self.db.get_task(task_id)

    async def get_current_task(self) -> Optional[TaskInfo]:
        """Get the currently running task."""
        return self.current_task

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

    async def _run_task(self, task_id: str, task_type: TaskType, parameters: dict):
        """Run a task in the background."""
        task = await self.db.get_task(task_id)
        self._cancel_event = asyncio.Event()

        try:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            task.message = "Task is running"
            await self.db.update_task(task)
            logger.info(f"Starting task {task_id} of type {task_type}")

            # Execute the appropriate task
            if task_type == TaskType.DUMMY_SHORT:
                await self._dummy_task(task, duration=5, steps=5)
            elif task_type == TaskType.DUMMY_LONG:
                await self._dummy_task(task, duration=30, steps=10)
            elif task_type == TaskType.DUMMY_VERY_LONG:
                await self._dummy_task(task, duration=120, steps=20)
            elif task_type == TaskType.TOKENIZE:
                await self._tokenize_task(task)
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
            await self.db.update_task(task)
            logger.info(f"Task {task_id} completed successfully")

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error = str(e)
            task.message = f"Task failed: {e}"
            await self.db.update_task(task)

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

            # Save progress to database
            await self.db.update_task(task)

            logger.debug(f"Task {task.task_id}: {progress:.1f}% complete")

            await asyncio.sleep(sleep_time)

        # Set final result
        task.result = {
            "message": "Dummy task completed",
            "steps_completed": steps,
            "duration": duration,
        }

    async def _tokenize_task(self, task: TaskInfo):
        """
        Tokenize a text file using tiktoken.

        Reads from input_file_path, sleeps for 1 minute, then writes tokenized
        output to output_file_path.

        Args:
            task: The task info object to update
        """
        try:
            # Validate paths
            if not task.input_file_path:
                raise ValueError("input_file_path is required for tokenize task")
            if not task.output_file_path:
                raise ValueError("output_file_path is required for tokenize task")

            input_path = Path(task.input_file_path)
            output_path = Path(task.output_file_path)

            # Step 1: Read input file (10%)
            task.progress = 10.0
            task.message = "Reading input file"
            await self.db.update_task(task)
            logger.info(f"Reading file: {input_path}")

            if not input_path.exists():
                raise FileNotFoundError(f"Input file not found: {input_path}")

            text_content = input_path.read_text(encoding="utf-8")
            logger.info(f"Read {len(text_content)} characters from {input_path}")

            # Step 2: Initialize tokenizer (20%)
            task.progress = 20.0
            task.message = "Initializing tokenizer"
            await self.db.update_task(task)

            encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding

            # Step 3: Sleep for 1 minute with progress updates (20% -> 80%)
            task.message = "Processing (sleeping for 1 minute)"
            sleep_duration = 60  # 1 minute
            sleep_steps = 12  # Update every 5 seconds

            for step in range(sleep_steps):
                if self._cancel_event and self._cancel_event.is_set():
                    return

                progress = 20.0 + ((step + 1) / sleep_steps) * 60.0
                task.progress = progress
                task.message = (
                    f"Processing ({step + 1}/{sleep_steps}, "
                    f"{(step + 1) * 5}s / {sleep_duration}s)"
                )
                await self.db.update_task(task)

                await asyncio.sleep(sleep_duration / sleep_steps)

            # Step 4: Tokenize (85%)
            task.progress = 85.0
            task.message = "Tokenizing text"
            await self.db.update_task(task)
            logger.info("Tokenizing text")

            tokens = encoding.encode(text_content)
            logger.info(f"Generated {len(tokens)} tokens")

            # Step 5: Write output (95%)
            task.progress = 95.0
            task.message = "Writing output file"
            await self.db.update_task(task)
            logger.info(f"Writing tokens to: {output_path}")

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Write tokens as JSON
            output_data = {
                "input_file": str(input_path),
                "char_count": len(text_content),
                "token_count": len(tokens),
                "tokens": tokens,
                "encoding": "cl100k_base",
            }

            output_path.write_text(json.dumps(output_data, indent=2), encoding="utf-8")
            logger.info(f"Wrote tokenized output to {output_path}")

            # Set final result
            task.result = {
                "message": "Tokenization completed",
                "input_file": str(input_path),
                "output_file": str(output_path),
                "char_count": len(text_content),
                "token_count": len(tokens),
                "encoding": "cl100k_base",
            }

        except Exception as e:
            logger.error(f"Tokenization failed: {e}", exc_info=True)
            raise
