"""Main FastAPI application for PyAMA chat."""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .database import TaskDatabase
from .models import TaskInfo, TaskResponse, TaskSubmit
from .task_manager import TaskManager

logger = logging.getLogger(__name__)

# Global instances
db = TaskDatabase("tasks.db")
task_manager = TaskManager(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    logger.info("Starting pyama-fastapi server")
    await db.initialize()
    yield
    logger.info("Shutting down pyama-fastapi server")
    await db.close()


app = FastAPI(
    title="PyAMA FastAPI",
    description="Task processing backend for PyAMA microscopy analysis",
    version="0.1.0",
    lifespan=lifespan,
)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "pyama-fastapi"}


@app.post("/tasks", response_model=TaskResponse)
async def submit_task(task_submit: TaskSubmit) -> TaskResponse:
    """
    Submit a new task for processing.

    Only one task can run at a time. If a task is already running,
    this endpoint will return an error.
    """
    try:
        task_id, message = await task_manager.submit_task(
            task_submit.task_type,
            task_submit.parameters,
            task_submit.input_file_path,
            task_submit.output_file_path,
        )
        task_info = await task_manager.get_task_info(task_id)
        return TaskResponse(
            task_id=task_id, status=task_info.status, message=message
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/tasks/{task_id}", response_model=TaskInfo)
async def get_task(task_id: str) -> TaskInfo:
    """Get detailed information about a specific task."""
    task_info = await task_manager.get_task_info(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_info


@app.get("/tasks/current/info", response_model=TaskInfo | None)
async def get_current_task() -> TaskInfo | None:
    """Get information about the currently running task, if any."""
    return await task_manager.get_current_task()


@app.delete("/tasks/{task_id}", response_model=TaskResponse)
async def cancel_task(task_id: str) -> TaskResponse:
    """Cancel a running or pending task."""
    success = await task_manager.cancel_task(task_id)
    if not success:
        raise HTTPException(
            status_code=400, detail="Task cannot be cancelled (not found or already completed)"
        )
    return TaskResponse(
        task_id=task_id, status="cancelled", message="Task cancelled successfully"
    )


@app.get("/tasks", response_model=list[TaskInfo])
async def list_tasks() -> list[TaskInfo]:
    """List all tasks in history."""
    return await task_manager.list_all_tasks()


def run() -> None:
    """Run the FastAPI server."""
    uvicorn.run(
        "pyama_fastapi.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    run()
