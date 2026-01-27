"""Pydantic schemas for the PyAMA API (tasks, microscopy, etc.)."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from pyama_core.types.microscopy import MicroscopyMetadata
from pyama_core.types.processing import ProcessingConfig


# =============================================================================
# MICROSCOPY SCHEMAS
# =============================================================================


class MicroscopyLoadRequest(BaseModel):
    """Request to load a microscopy file."""

    file_path: str = Field(..., description="Path to the microscopy file (ND2, CZI, TIFF)")

    model_config = {
        "json_schema_extra": {
            "example": {"file_path": "/path/to/experiment.nd2"}
        }
    }


class MicroscopyMetadataSchema(BaseModel):
    """Metadata extracted from a microscopy file."""

    file_path: str = Field(..., description="Path to the microscopy file")
    base_name: str = Field(..., description="Base name of the file (without extension)")
    file_type: str = Field(..., description="File type (nd2, czi, tiff, etc.)")
    height: int = Field(..., description="Image height in pixels")
    width: int = Field(..., description="Image width in pixels")
    n_frames: int = Field(..., description="Number of time frames")
    n_fovs: int = Field(..., description="Number of fields of view")
    n_channels: int = Field(..., description="Number of channels")
    timepoints: list[float] = Field(..., description="Timepoint values")
    channel_names: list[str] = Field(..., description="Channel names")
    dtype: str = Field(..., description="Data type of the image array")

    model_config = {
        "json_schema_extra": {
            "example": {
                "file_path": "/path/to/experiment.nd2",
                "base_name": "experiment",
                "file_type": "nd2",
                "height": 2048,
                "width": 2048,
                "n_frames": 100,
                "n_fovs": 10,
                "n_channels": 3,
                "timepoints": [0.0, 60.0, 120.0],
                "channel_names": ["Phase", "GFP", "RFP"],
                "dtype": "uint16",
            }
        }
    }


def metadata_to_schema(meta: MicroscopyMetadata) -> MicroscopyMetadataSchema:
    """Convert a MicroscopyMetadata model to the API schema."""
    return MicroscopyMetadataSchema(
        file_path=str(meta.file_path),
        base_name=meta.base_name,
        file_type=meta.file_type,
        height=meta.height,
        width=meta.width,
        n_frames=meta.n_frames,
        n_fovs=meta.n_fovs,
        n_channels=meta.n_channels,
        timepoints=meta.timepoints,
        channel_names=meta.channel_names,
        dtype=meta.dtype,
    )


# =============================================================================
# TASK SCHEMAS
# =============================================================================


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
    output_dir: str | None = Field(
        None,
        description="Output directory for processed files. Required when fake is False.",
    )
    config: ProcessingConfig = Field(..., description="Processing configuration")
    fake: bool = Field(False, description="If true, run a fake 60-second task instead of real processing")

    @model_validator(mode="after")
    def validate_output_dir(self) -> "TaskCreate":
        if not self.fake and self.output_dir is None:
            raise ValueError("output_dir is required for real (non-fake) tasks")
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "file_path": "/path/to/experiment.nd2",
                "output_dir": "/path/to/outputs",
                "config": {
                    "channels": {
                        "pc": {"channel": 0, "features": ["area"]},
                        "fl": [{"channel": 1, "features": ["intensity_total"]}],
                    },
                    "params": {
                        "fovs": "0-4,6",
                        "batch_size": 2,
                        "n_workers": 2,
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
    config: ProcessingConfig | None = Field(None, description="Processing configuration")

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
