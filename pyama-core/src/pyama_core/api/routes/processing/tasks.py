"""Processing task routes - create, list, get, cancel tasks."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from pyama_core.api.database import TaskDB, get_db
from pyama_core.api.schemas.task import (
    TaskCreate,
    TaskListResponse,
    TaskResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["processing"])


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    request: TaskCreate,
    db: Annotated[TaskDB, Depends(get_db)],
) -> TaskResponse:
    """Create a new processing task.

    The task will be queued and processed by the background worker.
    Returns the task ID and initial status (pending).
    """
    task = db.create_task(
        file_path=request.file_path,
        config=request.config.model_dump(),
    )
    logger.info("Created task %s for file: %s", task.id, request.file_path)
    return task


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    db: Annotated[TaskDB, Depends(get_db)],
) -> TaskListResponse:
    """List all tasks."""
    tasks = db.list_tasks()
    return TaskListResponse(tasks=tasks, total=len(tasks))


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    db: Annotated[TaskDB, Depends(get_db)],
) -> TaskResponse:
    """Get task status, progress, and result."""
    task = db.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return task


@router.delete("/{task_id}", response_model=dict)
async def cancel_task(
    task_id: str,
    db: Annotated[TaskDB, Depends(get_db)],
) -> dict:
    """Cancel a pending or running task."""
    task = db.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    if task.status not in ("pending", "running"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel task with status: {task.status}",
        )

    success = db.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to cancel task")

    logger.info("Cancelled task: %s", task_id)
    return {"success": True, "task_id": task_id}
