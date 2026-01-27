"""MCP tool definitions for PyAMA Core.

This module defines the MCP tools that expose pyama-core functionality
to Claude and other MCP clients.
"""

from typing import Any

from pydantic import Field

from pyama_core.api.mcp.server import mcp
from pyama_core.types.api import metadata_to_schema
from pyama_core.types.processing import ProcessingConfig
from pyama_core.api.services import (
    MicroscopyService,
    MicroscopyServiceError,
    TaskService,
    TaskServiceError,
    TaskNotFoundError,
)


@mcp.tool()
def load_microscopy(
    file_path: str = Field(description="Path to microscopy file (ND2, CZI, or TIFF format)")
) -> dict[str, Any]:
    """Load a microscopy file and extract metadata.

    Returns metadata including dimensions, channels, timepoints, and file info.
    Supports ND2 (Nikon), CZI (Zeiss), and TIFF formats.
    """
    try:
        service = MicroscopyService()
        metadata = service.load_metadata(file_path)
        schema = metadata_to_schema(metadata)
        return schema.model_dump()
    except MicroscopyServiceError as e:
        return {"error": str(e)}


@mcp.tool()
def get_processing_config_schema() -> dict[str, Any]:
    """Get the JSON schema for processing configuration.

    Returns the schema that describes all available processing options including:
    - channels: Phase contrast and fluorescence channel configuration
    - params: Processing parameters (FOVs, batch size, segmentation method, etc.)

    Use this to understand what configuration options are available before
    creating a processing task.
    """
    return ProcessingConfig.model_json_schema()


@mcp.tool()
def create_processing_task(
    file_path: str = Field(description="Path to microscopy file to process"),
    output_dir: str = Field(
        description="Directory where processing outputs will be saved. A task-specific subdirectory will be created inside."
    ),
    config: dict[str, Any] = Field(description="Processing configuration (channels and params)"),
    fake: bool = Field(
        description="Run a 60-second simulated task for testing",
        default=False,
    ),
) -> dict[str, Any]:
    """Create and start a new image processing task.

    The task runs asynchronously in the background. Use get_task() to check
    progress and results.

    Config should follow the ProcessingConfig structure:
    - channels.pc: Phase contrast channel (channel index + features list)
    - channels.fl: Fluorescence channels — only include channels that need
      feature extraction. Omit channels with no features entirely.
    - params.fovs: FOV selection string (e.g., '0-4,6'). REQUIRED — specify
      which FOVs to process. Empty string means all FOVs.
    - params.batch_size, params.n_workers: Processing parallelism
    """
    try:
        service = TaskService()
        # Validate config against schema
        validated_config = ProcessingConfig(**config)
        task = service.create_task(
            file_path=file_path,
            config=validated_config.model_dump(),
            fake=fake,
            output_dir=output_dir,
        )
        return task.model_dump(mode="json")
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def list_tasks() -> dict[str, Any]:
    """List all processing tasks with their current status.

    Returns tasks ordered by creation time (newest first) with:
    - id: Task UUID
    - status: pending, running, completed, failed, or cancelled
    - progress: Current progress for running tasks
    - result: Output directory and summary for completed tasks
    """
    service = TaskService()
    response = service.list_tasks()
    return {
        "tasks": [t.model_dump(mode="json") for t in response.tasks],
        "total": response.total,
    }


@mcp.tool()
def get_task(
    task_id: str = Field(description="Task ID (UUID) to retrieve")
) -> dict[str, Any]:
    """Get detailed status and progress of a specific task.

    Returns complete task information including:
    - status: Current task state
    - progress: Phase, current FOV, total FOVs, percent complete
    - result: Output directory and summary (if completed)
    - error_message: Error details (if failed)
    - timestamps: created_at, started_at, completed_at
    """
    try:
        service = TaskService()
        task = service.get_task(task_id)
        return task.model_dump(mode="json")
    except TaskNotFoundError as e:
        return {"error": str(e)}


@mcp.tool()
def cancel_task(
    task_id: str = Field(description="Task ID (UUID) to cancel")
) -> dict[str, Any]:
    """Cancel a pending or running task.

    Only tasks with status 'pending' or 'running' can be cancelled.
    Returns success status.
    """
    try:
        service = TaskService()
        success = service.cancel_task(task_id)
        return {"success": success, "task_id": task_id}
    except (TaskNotFoundError, TaskServiceError) as e:
        return {"error": str(e)}
