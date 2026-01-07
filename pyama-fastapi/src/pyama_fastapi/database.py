"""SQLite database module for task persistence."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite

from .models import TaskInfo, TaskStatus, TaskType

logger = logging.getLogger(__name__)

# Database schema
SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL,
    progress REAL DEFAULT 0.0,
    message TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    result TEXT,
    error TEXT,
    input_file_path TEXT,
    output_file_path TEXT,
    parameters TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_created_at ON tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_task_type ON tasks(task_type);
"""


class TaskDatabase:
    """Async SQLite database adapter for task persistence."""

    def __init__(self, db_path: str = "tasks.db"):
        """Initialize database connection."""
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Initialize the database schema."""
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()
        logger.info(f"Database initialized at {self.db_path}")

    async def close(self):
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            logger.info("Database connection closed")

    async def create_task(self, task_info: TaskInfo) -> None:
        """Create a new task in the database."""
        await self._conn.execute(
            """
            INSERT INTO tasks (
                task_id, task_type, status, progress, message,
                created_at, started_at, completed_at,
                result, error, input_file_path, output_file_path, parameters
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_info.task_id,
                task_info.task_type.value,
                task_info.status.value,
                task_info.progress,
                task_info.message,
                task_info.created_at.isoformat(),
                task_info.started_at.isoformat() if task_info.started_at else None,
                task_info.completed_at.isoformat() if task_info.completed_at else None,
                json.dumps(task_info.result) if task_info.result else None,
                task_info.error,
                task_info.input_file_path,
                task_info.output_file_path,
                json.dumps(task_info.parameters),
            ),
        )
        await self._conn.commit()
        logger.debug(f"Created task {task_info.task_id} in database")

    async def update_task(self, task_info: TaskInfo) -> None:
        """Update an existing task in the database."""
        await self._conn.execute(
            """
            UPDATE tasks SET
                status = ?,
                progress = ?,
                message = ?,
                started_at = ?,
                completed_at = ?,
                result = ?,
                error = ?,
                output_file_path = ?
            WHERE task_id = ?
            """,
            (
                task_info.status.value,
                task_info.progress,
                task_info.message,
                task_info.started_at.isoformat() if task_info.started_at else None,
                task_info.completed_at.isoformat() if task_info.completed_at else None,
                json.dumps(task_info.result) if task_info.result else None,
                task_info.error,
                task_info.output_file_path,
                task_info.task_id,
            ),
        )
        await self._conn.commit()
        logger.debug(f"Updated task {task_info.task_id} in database")

    async def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """Retrieve a task by ID."""
        async with self._conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_task_info(row)
            return None

    async def get_current_task(self) -> Optional[TaskInfo]:
        """Get the currently running task, if any."""
        async with self._conn.execute(
            """
            SELECT * FROM tasks
            WHERE status IN (?, ?)
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (TaskStatus.RUNNING.value, TaskStatus.PENDING.value),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_task_info(row)
            return None

    async def list_tasks(
        self, limit: Optional[int] = None, offset: int = 0
    ) -> list[TaskInfo]:
        """List all tasks ordered by creation time (newest first)."""
        query = "SELECT * FROM tasks ORDER BY created_at DESC"
        params = []

        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params = [limit, offset]

        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_task_info(row) for row in rows]

    async def list_tasks_by_status(self, status: TaskStatus) -> list[TaskInfo]:
        """List tasks filtered by status."""
        async with self._conn.execute(
            "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC",
            (status.value,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_task_info(row) for row in rows]

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task from the database."""
        cursor = await self._conn.execute(
            "DELETE FROM tasks WHERE task_id = ?", (task_id,)
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    async def count_tasks(self) -> int:
        """Count total number of tasks."""
        async with self._conn.execute("SELECT COUNT(*) FROM tasks") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    def _row_to_task_info(self, row: aiosqlite.Row) -> TaskInfo:
        """Convert a database row to TaskInfo model."""
        return TaskInfo(
            task_id=row["task_id"],
            task_type=TaskType(row["task_type"]),
            status=TaskStatus(row["status"]),
            progress=row["progress"],
            message=row["message"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=(
                datetime.fromisoformat(row["started_at"]) if row["started_at"] else None
            ),
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row["completed_at"]
                else None
            ),
            result=json.loads(row["result"]) if row["result"] else None,
            error=row["error"],
            input_file_path=row["input_file_path"],
            output_file_path=row["output_file_path"],
            parameters=json.loads(row["parameters"]) if row["parameters"] else {},
        )
