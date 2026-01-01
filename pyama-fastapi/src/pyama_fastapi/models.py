"""Data models for task management."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Available task types."""

    DUMMY_SHORT = "dummy_short"  # Completes in ~5 seconds
    DUMMY_LONG = "dummy_long"  # Completes in ~30 seconds
    DUMMY_VERY_LONG = "dummy_very_long"  # Completes in ~2 minutes
    TOKENIZE = "tokenize"  # Tokenize text file (~1 minute)
    # Future task types can be added here
    # ANALYSIS = "analysis"
    # TRAINING = "training"


class TaskSubmit(BaseModel):
    """Request model for submitting a task."""

    task_type: TaskType
    parameters: dict[str, Any] = Field(default_factory=dict)
    input_file_path: Optional[str] = None
    output_file_path: Optional[str] = None


class TaskInfo(BaseModel):
    """Information about a task."""

    task_id: str
    task_type: TaskType
    status: TaskStatus
    progress: float = Field(ge=0.0, le=100.0, default=0.0)
    message: str = ""
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    input_file_path: Optional[str] = None
    output_file_path: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    """Response when submitting or querying a task."""

    task_id: str
    status: TaskStatus
    message: str
