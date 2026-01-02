# PyAMA FastAPI Backend

A FastAPI-based backend for processing long-running tasks for PyAMA microscopy analysis.

## Features

- **Single-task execution**: Only one task runs at a time to prevent resource conflicts
- **Background processing**: Tasks run asynchronously in the background
- **Progress tracking**: Real-time progress updates via polling
- **Task history**: All tasks are stored in history for later retrieval
- **Task cancellation**: Running tasks can be cancelled
- **No authentication**: Designed to work with pyama-nextjs which handles user management

## Installation

```bash
cd pyama-fastapi
uv sync
```

## Running the Server

```bash
# Using the CLI command
uv run pyama-fastapi

# Or using uvicorn directly
uv run uvicorn pyama_fastapi.main:app --host 0.0.0.0 --port 8000 --reload
```

The server will start on `http://localhost:8000`.

## API Endpoints

### Health Check

```http
GET /
```

Returns server status.

**Response:**
```json
{
  "status": "ok",
  "service": "pyama-fastapi"
}
```

### Submit a Task

```http
POST /tasks
```

Submit a new task for processing. Only one task can run at a time.

**Request Body:**
```json
{
  "task_type": "dummy_short",
  "parameters": {}
}
```

**Available Task Types:**
- `dummy_short`: Runs for ~5 seconds (5 steps)
- `dummy_long`: Runs for ~30 seconds (10 steps)
- `dummy_very_long`: Runs for ~2 minutes (20 steps)

**Response (200 OK):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Task submitted successfully"
}
```

**Response (409 Conflict):**
```json
{
  "detail": "A task is already running: <task_id>"
}
```

### Get Task Status

```http
GET /tasks/{task_id}
```

Get detailed information about a specific task.

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_type": "dummy_short",
  "status": "running",
  "progress": 60.0,
  "message": "Processing step 3/5",
  "created_at": "2026-01-01T15:30:00.000000",
  "started_at": "2026-01-01T15:30:00.500000",
  "completed_at": null,
  "result": null,
  "error": null
}
```

**Status Values:**
- `pending`: Task is queued but not yet started
- `running`: Task is currently executing
- `completed`: Task finished successfully
- `failed`: Task encountered an error
- `cancelled`: Task was cancelled by user

### Get Current Task

```http
GET /tasks/current/info
```

Get information about the currently running task, if any.

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_type": "dummy_short",
  "status": "running",
  "progress": 60.0,
  ...
}
```

Returns `null` if no task is currently running.

### Cancel a Task

```http
DELETE /tasks/{task_id}
```

Cancel a running or pending task.

**Response (200 OK):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "cancelled",
  "message": "Task cancelled successfully"
}
```

**Response (400 Bad Request):**
```json
{
  "detail": "Task cannot be cancelled (not found or already completed)"
}
```

### List All Tasks

```http
GET /tasks
```

Get a list of all tasks in history.

**Response:**
```json
[
  {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "task_type": "dummy_short",
    "status": "completed",
    ...
  },
  ...
]
```

## Usage Example with Next.js

### Submitting a Task

```typescript
// Submit a task
const response = await fetch('http://localhost:8000/tasks', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    task_type: 'dummy_long',
    parameters: {}
  })
});

const { task_id } = await response.json();
```

### Polling for Progress

```typescript
// Poll for progress every 2 seconds
const pollInterval = setInterval(async () => {
  const response = await fetch(`http://localhost:8000/tasks/${task_id}`);
  const taskInfo = await response.json();

  console.log(`Progress: ${taskInfo.progress}%`);
  console.log(`Status: ${taskInfo.status}`);
  console.log(`Message: ${taskInfo.message}`);

  if (['completed', 'failed', 'cancelled'].includes(taskInfo.status)) {
    clearInterval(pollInterval);

    if (taskInfo.status === 'completed') {
      console.log('Result:', taskInfo.result);
    } else if (taskInfo.status === 'failed') {
      console.error('Error:', taskInfo.error);
    }
  }
}, 2000);
```

### Using React Hook

```typescript
import { useState, useEffect } from 'react';

function useTask(taskId: string | null) {
  const [taskInfo, setTaskInfo] = useState(null);

  useEffect(() => {
    if (!taskId) return;

    const interval = setInterval(async () => {
      const response = await fetch(`http://localhost:8000/tasks/${taskId}`);
      const data = await response.json();
      setTaskInfo(data);

      if (['completed', 'failed', 'cancelled'].includes(data.status)) {
        clearInterval(interval);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [taskId]);

  return taskInfo;
}
```

## Testing

Run the test script to verify the API is working:

```bash
# Make sure the server is running first
uv run python test_api.py
```

## Architecture

- **Single Task Queue**: Only one task runs at a time to prevent resource conflicts
- **Background Execution**: Tasks run asynchronously using Python's asyncio
- **In-Memory Storage**: Task history is stored in memory (will reset on server restart)
- **No Authentication**: User management is handled by pyama-nextjs frontend

## Future Enhancements

- Persistent task storage (database)
- Task priority queue
- Multiple concurrent tasks with resource limits
- WebSocket support for real-time progress updates
- Integration with pyama-core for actual analysis tasks
