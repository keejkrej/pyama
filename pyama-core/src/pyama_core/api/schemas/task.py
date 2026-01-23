"""Pydantic schemas for task management."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from pyama_core.api.schemas.processing import ProcessingConfigSchema


class TaskStatus(str, Enum):
    """Task status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskCreate(BaseModel):
    """Request to create a new processing task."""

    file_path: str = Field(..., description="Path to the microscopy file to process")
    config: ProcessingConfigSchema = Field(..., description="Processing configuration")

    model_config = {
        "json_schema_extra": {
            "example": {
                "file_path": "/path/to/experiment.nd2",
                "config": {
                    "channels": {
                        "pc": {"channel": 0, "features": ["area"]},
                        "fl": [{"channel": 1, "features": ["intensity_total"]}],
                    },
                    "params": {
                        "segmentation_method": "cellpose",
                        "tracking_method": "iou",
                    },
                },
            }
        }
    }


class TaskProgress(BaseModel):
    """Progress information for a running task."""

    phase: str | None = Field(None, description="Current processing phase")
    current_fov: int | None = Field(None, description="Current FOV being processed")
    total_fovs: int | None = Field(None, description="Total number of FOVs")
    percent: float | None = Field(None, description="Progress percentage (0-100)")
    message: str | None = Field(None, description="Progress message")


class TaskResult(BaseModel):
    """Result of a completed task."""

    output_dir: str | None = Field(None, description="Path to output directory")
    summary: dict[str, Any] | None = Field(None, description="Processing summary")


class TaskResponse(BaseModel):
    """Response containing task information."""

    id: str = Field(..., description="Task ID (UUID)")
    status: TaskStatus = Field(..., description="Current task status")
    file_path: str = Field(..., description="Path to the microscopy file")
    config: ProcessingConfigSchema | None = Field(None, description="Processing configuration")

    # Progress (only present when status is RUNNING)
    progress: TaskProgress | None = Field(None, description="Progress information")

    # Result (only present when status is COMPLETED)
    result: TaskResult | None = Field(None, description="Task result")

    # Error (only present when status is FAILED)
    error_message: str | None = Field(None, description="Error message if task failed")

    # Timestamps
    created_at: datetime = Field(..., description="Task creation timestamp")
    started_at: datetime | None = Field(None, description="Task start timestamp")
    completed_at: datetime | None = Field(None, description="Task completion timestamp")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "abc123-def456-ghi789",
                "status": "running",
                "file_path": "/path/to/experiment.nd2",
                "progress": {
                    "phase": "segmentation",
                    "current_fov": 3,
                    "total_fovs": 10,
                    "percent": 30.0,
                    "message": "Segmenting FOV 3/10...",
                },
                "created_at": "2024-01-15T10:30:00Z",
                "started_at": "2024-01-15T10:30:01Z",
            }
        }
    }


class TaskListResponse(BaseModel):
    """Response containing a list of tasks."""

    tasks: list[TaskResponse] = Field(..., description="List of tasks")
    total: int = Field(..., description="Total number of tasks")
