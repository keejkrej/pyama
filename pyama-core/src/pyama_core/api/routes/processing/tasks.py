"""Processing task routes - create, list, get, cancel tasks."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from pyama_core.api.database import TaskDB, get_db
from pyama_core.types.api import (
    TaskCreate,
    TaskListResponse,
    TaskResponse,
)
from pyama_core.api.services import TaskService, TaskServiceError, TaskNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["processing"])


def get_task_service(db: Annotated[TaskDB, Depends(get_db)]) -> TaskService:
    """Get TaskService instance with injected database."""
    return TaskService(db=db)


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    request: TaskCreate,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    """Create a new processing task.

    The task will be queued and processed by the background worker.
    Returns the task ID and initial status (pending).

    If fake=true, runs a 60-second simulated task with progress updates.
    """
    task = service.create_task(
        file_path=request.file_path,
        config=request.config,
        fake=request.fake,
        output_dir=request.output_dir,
    )
    return task


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskListResponse:
    """List all tasks."""
    return service.list_tasks()


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    """Get task status, progress, and result."""
    try:
        return service.get_task(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")


@router.delete("/{task_id}", response_model=dict)
async def cancel_task(
    task_id: str,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> dict:
    """Cancel a pending or running task."""
    try:
        success = service.cancel_task(task_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to cancel task")
        return {"success": True, "task_id": task_id}
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    except TaskServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
