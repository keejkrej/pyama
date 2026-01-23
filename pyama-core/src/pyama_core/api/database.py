"""SQLite database for task storage."""

import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

from pyama_core.api.schemas.task import (
    TaskProgress,
    TaskResponse,
    TaskResult,
    TaskStatus,
)
from pyama_core.api.schemas.processing import ProcessingConfigSchema

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = Path.home() / ".pyama" / "tasks.db"

# SQL schema for tasks table
CREATE_TASKS_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    file_path TEXT NOT NULL,
    config JSON NOT NULL,
    phase TEXT,
    current_fov INTEGER,
    total_fovs INTEGER,
    progress_percent REAL,
    progress_message TEXT,
    result JSON,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
"""


class TaskDB:
    """SQLite-based task database."""

    def __init__(self, db_path: Path | None = None):
        """Initialize the task database.

        Args:
            db_path: Path to SQLite database file. Defaults to ~/.pyama/tasks.db
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.execute(CREATE_TASKS_TABLE)
            conn.commit()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _row_to_task(self, row: sqlite3.Row) -> TaskResponse:
        """Convert a database row to a TaskResponse."""
        # Parse config JSON
        config_data = json.loads(row["config"]) if row["config"] else None
        config = ProcessingConfigSchema(**config_data) if config_data else None

        # Build progress if running
        progress = None
        if row["status"] == TaskStatus.RUNNING:
            progress = TaskProgress(
                phase=row["phase"],
                current_fov=row["current_fov"],
                total_fovs=row["total_fovs"],
                percent=row["progress_percent"],
                message=row["progress_message"],
            )

        # Build result if completed
        result = None
        if row["status"] == TaskStatus.COMPLETED and row["result"]:
            result_data = json.loads(row["result"])
            result = TaskResult(**result_data)

        # Parse timestamps
        created_at = datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now()
        started_at = datetime.fromisoformat(row["started_at"]) if row["started_at"] else None
        completed_at = datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None

        return TaskResponse(
            id=row["id"],
            status=TaskStatus(row["status"]),
            file_path=row["file_path"],
            config=config,
            progress=progress,
            result=result,
            error_message=row["error_message"],
            created_at=created_at,
            started_at=started_at,
            completed_at=completed_at,
        )

    def create_task(self, file_path: str, config: dict[str, Any]) -> TaskResponse:
        """Create a new task in pending status."""
        task_id = str(uuid.uuid4())
        created_at = datetime.now()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO tasks (id, status, file_path, config, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (task_id, TaskStatus.PENDING, file_path, json.dumps(config), created_at.isoformat()),
            )
            conn.commit()

        return TaskResponse(
            id=task_id,
            status=TaskStatus.PENDING,
            file_path=file_path,
            config=ProcessingConfigSchema(**config),
            created_at=created_at,
        )

    def get_task(self, task_id: str) -> TaskResponse | None:
        """Get a task by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_task(row)

    def list_tasks(self) -> list[TaskResponse]:
        """List all tasks, ordered by creation time (newest first)."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC")
            return [self._row_to_task(row) for row in cursor.fetchall()]

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        phase: str | None = None,
        current_fov: int | None = None,
        total_fovs: int | None = None,
        progress_percent: float | None = None,
        progress_message: str | None = None,
        result: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> bool:
        """Update task status and optionally progress/result."""
        updates = ["status = ?"]
        values: list[Any] = [status.value]

        if phase is not None:
            updates.append("phase = ?")
            values.append(phase)

        if current_fov is not None:
            updates.append("current_fov = ?")
            values.append(current_fov)

        if total_fovs is not None:
            updates.append("total_fovs = ?")
            values.append(total_fovs)

        if progress_percent is not None:
            updates.append("progress_percent = ?")
            values.append(progress_percent)

        if progress_message is not None:
            updates.append("progress_message = ?")
            values.append(progress_message)

        if result is not None:
            updates.append("result = ?")
            values.append(json.dumps(result))

        if error_message is not None:
            updates.append("error_message = ?")
            values.append(error_message)

        # Set timestamps based on status
        if status == TaskStatus.RUNNING:
            updates.append("started_at = ?")
            values.append(datetime.now().isoformat())
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            updates.append("completed_at = ?")
            values.append(datetime.now().isoformat())

        values.append(task_id)

        with self._get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
                values,
            )
            conn.commit()
            return cursor.rowcount > 0

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        return self.update_task_status(task_id, TaskStatus.CANCELLED)

    def get_next_pending_task(self) -> TaskResponse | None:
        """Get the next pending task (oldest first)."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at ASC LIMIT 1",
                (TaskStatus.PENDING,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_task(row)

    def has_running_task(self) -> bool:
        """Check if there's a currently running task."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = ?",
                (TaskStatus.RUNNING,),
            )
            return cursor.fetchone()[0] > 0


# Global database instance (lazy initialization)
_db_instance: TaskDB | None = None


def get_db() -> TaskDB:
    """Get the global database instance (FastAPI dependency)."""
    global _db_instance
    if _db_instance is None:
        _db_instance = TaskDB()
    return _db_instance


def init_db(db_path: Path | None = None) -> TaskDB:
    """Initialize the global database instance with a specific path."""
    global _db_instance
    _db_instance = TaskDB(db_path)
    return _db_instance
