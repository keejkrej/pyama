# Task Development Guide

This guide shows how to create custom tasks using the `BaseTask` class.

## Architecture Overview

The task system uses an object-oriented design with these components:

1. **BaseTask** - Abstract base class that all tasks inherit from
2. **Task Classes** - Concrete implementations (DummyTask, TokenizeTask, etc.)
3. **TaskRegistry** - Maps TaskType enum to task classes
4. **TaskManager** - Orchestrates task execution (doesn't contain task logic)

## Creating a New Task

### Step 1: Create Your Task Class

Create a new file in `src/pyama_fastapi/tasks/`:

```python
# src/pyama_fastapi/tasks/my_task.py
"""My custom task implementation."""

import asyncio
from typing import Any
from pathlib import Path

from .base import BaseTask


class MyCustomTask(BaseTask):
    """
    Description of what your task does.

    Required fields:
        input_file_path: Path to input file
        output_file_path: Path to output file (optional)

    Parameters:
        param1: Description (default: value)
        param2: Description (default: value)
    """

    async def execute(self) -> dict[str, Any]:
        """Execute the task logic."""

        # Access task properties
        input_path = Path(self.input_file_path)
        output_path = Path(self.output_file_path) if self.output_file_path else None
        param1 = self.parameters.get("param1", "default_value")

        # Step 1: Initial work (0-25%)
        await self.update_progress(10, "Starting task")

        # Check for cancellation
        await self.check_cancelled()

        # Do some work...
        result = await self.do_something()

        await self.update_progress(25, "First step complete")

        # Step 2: Main processing (25-75%)
        await self.update_progress(50, "Processing data")

        # Check for cancellation periodically
        if self.is_cancelled():
            return {"cancelled": True}

        # More work...
        processed = await self.process_data(result)

        await self.update_progress(75, "Almost done")

        # Step 3: Finalize (75-100%)
        await self.update_progress(90, "Writing output")

        final_result = await self.save_output(processed, output_path)

        # Return result dictionary
        return {
            "message": "Task completed successfully",
            "input_file": str(input_path),
            "output_file": str(output_path) if output_path else None,
            "items_processed": len(processed),
            "custom_metric": final_result,
        }

    async def do_something(self):
        """Helper method."""
        # Your logic here
        await asyncio.sleep(1)
        return "result"

    async def process_data(self, data):
        """Helper method."""
        # Your logic here
        return [data] * 10

    async def save_output(self, data, path):
        """Helper method."""
        # Your logic here
        return len(data)
```

### Step 2: Add to Task Type Enum

Edit `src/pyama_fastapi/models.py`:

```python
class TaskType(str, Enum):
    """Available task types."""

    DUMMY_SHORT = "dummy_short"
    DUMMY_LONG = "dummy_long"
    DUMMY_VERY_LONG = "dummy_very_long"
    TOKENIZE = "tokenize"
    MY_CUSTOM_TASK = "my_custom_task"  # Add your task type
```

### Step 3: Register the Task

Edit `src/pyama_fastapi/tasks/registry.py`:

```python
from .my_task import MyCustomTask

class TaskRegistry:
    _registry: dict[TaskType, Type[BaseTask]] = {
        TaskType.DUMMY_SHORT: DummyTask,
        TaskType.DUMMY_LONG: DummyTask,
        TaskType.DUMMY_VERY_LONG: DummyTask,
        TaskType.TOKENIZE: TokenizeTask,
        TaskType.MY_CUSTOM_TASK: MyCustomTask,  # Register your task
    }

    _default_parameters: dict[TaskType, dict] = {
        TaskType.DUMMY_SHORT: {"duration": 5, "steps": 5},
        TaskType.DUMMY_LONG: {"duration": 30, "steps": 10},
        TaskType.DUMMY_VERY_LONG: {"duration": 120, "steps": 20},
        TaskType.TOKENIZE: {"encoding": "cl100k_base", "sleep_duration": 60},
        TaskType.MY_CUSTOM_TASK: {"param1": "default", "param2": 42},
    }
```

### Step 4: Export the Task

Edit `src/pyama_fastapi/tasks/__init__.py`:

```python
from .my_task import MyCustomTask

__all__ = ["BaseTask", "DummyTask", "TokenizeTask", "MyCustomTask", "TaskRegistry"]
```

### Step 5: Test Your Task

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "my_custom_task",
    "parameters": {"param1": "custom_value"},
    "input_file_path": "/path/to/input.txt",
    "output_file_path": "/path/to/output.json"
  }'
```

## BaseTask API Reference

### Properties

- `self.task_info: TaskInfo` - Full task metadata
- `self.db: TaskDatabase` - Database instance for persistence
- `self.cancel_event: asyncio.Event` - Event for cancellation signaling
- `self.parameters: dict` - Task parameters (with defaults merged)
- `self.input_file_path: Optional[str]` - Input file path
- `self.output_file_path: Optional[str]` - Output file path
- `self.logger: Logger` - Task-specific logger

### Methods

#### `async def execute() -> dict[str, Any]` ✨ REQUIRED

The main task logic. Must be implemented by all tasks.

**Returns:** Dictionary containing task results

**Example:**
```python
async def execute(self) -> dict[str, Any]:
    # Your logic here
    return {"result": "success"}
```

#### `async def update_progress(progress: float, message: str = "")`

Update task progress and save to database.

**Args:**
- `progress` (float): Progress percentage (0-100)
- `message` (str): Status message to display

**Example:**
```python
await self.update_progress(50, "Halfway done")
```

#### `def is_cancelled() -> bool`

Check if the task has been cancelled.

**Returns:** True if task should stop executing

**Example:**
```python
if self.is_cancelled():
    return {"cancelled": True}
```

#### `async def check_cancelled()`

Check if task is cancelled and raise CancelledError if so.

**Example:**
```python
await self.check_cancelled()  # Returns early if cancelled
```

## Best Practices

### 1. Progress Updates

Update progress regularly so users can track the task:

```python
async def execute(self):
    await self.update_progress(0, "Starting")

    for i, item in enumerate(items):
        await self.check_cancelled()

        # Process item...

        progress = ((i + 1) / len(items)) * 100
        await self.update_progress(progress, f"Processed {i+1}/{len(items)}")

    return {"items": len(items)}
```

### 2. Cancellation Handling

Check for cancellation in loops:

```python
async def execute(self):
    for step in range(100):
        await self.check_cancelled()  # Raises CancelledError if cancelled

        # Do work...

    return {"steps": 100}
```

### 3. Error Handling

Let exceptions propagate - TaskManager will catch them:

```python
async def execute(self):
    # No need to wrap in try/except
    # TaskManager will catch exceptions and mark task as FAILED

    if not self.input_file_path:
        raise ValueError("input_file_path is required")

    path = Path(self.input_file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Continue with task...
```

### 4. File I/O

Use pathlib for file operations:

```python
async def execute(self):
    input_path = Path(self.input_file_path)
    output_path = Path(self.output_file_path)

    # Read input
    content = input_path.read_text()

    # Process...
    result = self.process(content)

    # Write output (create directories if needed)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result)

    return {"output_file": str(output_path)}
```

### 5. Async Operations

Use asyncio for long-running operations:

```python
async def execute(self):
    # Good: Non-blocking sleep
    await asyncio.sleep(1)

    # Bad: Blocking sleep (blocks event loop)
    # time.sleep(1)  # DON'T DO THIS

    # For CPU-intensive work, consider using run_in_executor
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, self.cpu_intensive_function)

    return {"result": result}
```

## Example: Full Custom Task

Here's a complete example of an image processing task:

```python
"""Image processing task."""

import asyncio
from pathlib import Path
from typing import Any

from PIL import Image

from .base import BaseTask


class ImageProcessTask(BaseTask):
    """
    Process an image (resize, convert format, etc.).

    Required:
        input_file_path: Path to input image
        output_file_path: Path to output image

    Parameters:
        width: Target width in pixels (default: 800)
        height: Target height in pixels (default: 600)
        format: Output format - JPEG, PNG, etc. (default: "JPEG")
        quality: JPEG quality 1-100 (default: 85)
    """

    async def execute(self) -> dict[str, Any]:
        """Execute image processing."""

        # Validate
        if not self.input_file_path or not self.output_file_path:
            raise ValueError("Both input_file_path and output_file_path required")

        input_path = Path(self.input_file_path)
        output_path = Path(self.output_file_path)

        # Get parameters
        width = self.parameters.get("width", 800)
        height = self.parameters.get("height", 600)
        fmt = self.parameters.get("format", "JPEG")
        quality = self.parameters.get("quality", 85)

        # Step 1: Load image (10%)
        await self.update_progress(10, "Loading image")

        if not input_path.exists():
            raise FileNotFoundError(f"Image not found: {input_path}")

        # Use executor for CPU-bound PIL operations
        loop = asyncio.get_event_loop()
        image = await loop.run_in_executor(None, Image.open, str(input_path))

        original_size = image.size
        self.logger.info(f"Loaded image: {original_size[0]}x{original_size[1]}")

        # Step 2: Resize (50%)
        await self.update_progress(50, f"Resizing to {width}x{height}")
        await self.check_cancelled()

        resized = await loop.run_in_executor(
            None, image.resize, (width, height), Image.Resampling.LANCZOS
        )

        # Step 3: Convert format if needed (75%)
        await self.update_progress(75, f"Converting to {fmt}")
        await self.check_cancelled()

        if fmt == "JPEG" and resized.mode in ("RGBA", "LA", "P"):
            rgb_image = Image.new("RGB", resized.size, (255, 255, 255))
            rgb_image.paste(resized, mask=resized.split()[-1] if resized.mode == "RGBA" else None)
            resized = rgb_image

        # Step 4: Save (90%)
        await self.update_progress(90, "Saving output")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        save_kwargs = {"format": fmt}
        if fmt == "JPEG":
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True

        await loop.run_in_executor(None, resized.save, str(output_path), **save_kwargs)

        self.logger.info(f"Saved image to: {output_path}")

        # Return result
        return {
            "message": "Image processed successfully",
            "input_file": str(input_path),
            "output_file": str(output_path),
            "original_size": original_size,
            "new_size": (width, height),
            "format": fmt,
            "file_size_bytes": output_path.stat().st_size,
        }
```

## Summary

1. ✅ Create a class that inherits from `BaseTask`
2. ✅ Implement the `execute()` method
3. ✅ Use `update_progress()` to report progress
4. ✅ Use `check_cancelled()` in loops
5. ✅ Add to TaskType enum
6. ✅ Register in TaskRegistry
7. ✅ Export from `tasks/__init__.py`

That's it! Your task will automatically work with the full task management system including progress tracking, cancellation, database persistence, and the REST API.
