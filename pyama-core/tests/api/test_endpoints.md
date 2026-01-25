# API Manual Testing Guide

HTTPie commands for testing PyAMA Core API endpoints.

## Prerequisites

```bash
# Start the backend server
cd pyama-core
uv run pyama-core serve
```

Server runs at `http://localhost:8000`

## Running Pytest

```bash
# Default test file: pyama-core/data/test.nd2
uv run pytest tests/api/test_endpoints.py -v

# Run only fake task tests (no real file needed)
uv run pytest tests/api/test_endpoints.py -v -k "fake"

# Use custom ND2 file via environment variable
PYAMA_TEST_ND2_FILE="/path/to/your/file.nd2" uv run pytest tests/api/test_endpoints.py -v
```

---

## General Endpoints

### Root - API Info
```bash
http GET :8000/
```

### Health Check
```bash
http GET :8000/health
```

---

## Microscopy Data Endpoints

### Load Microscopy Metadata
```bash
# With real file
http POST :8000/data/microscopy \
  file_path="/Users/jack/Documents/250129_HuH7_crop.nd2"

# File not found (404)
http POST :8000/data/microscopy \
  file_path="/nonexistent/file.nd2"

# Invalid request (422)
http POST :8000/data/microscopy
```

---

## Processing Config Endpoints

### Get Config Schema
```bash
http GET :8000/processing/config
```

---

## Task Endpoints

### Create Task (Real)
```bash
# Full config
http POST :8000/processing/tasks \
  file_path="/Users/jack/Documents/250129_HuH7_crop.nd2" \
  config:='{"channels": {"pc": {"channel": 0, "features": ["area"]}, "fl": []}}'

# Minimal config
http POST :8000/processing/tasks \
  file_path="/Users/jack/Documents/250129_HuH7_crop.nd2" \
  config:='{}'
```

### Create Task (Fake - 60 second simulation)
```bash
# Fake task with any path
http POST :8000/processing/tasks \
  file_path="/fake/file.nd2" \
  fake:=true \
  config:='{}'

# Fake task with real path
http POST :8000/processing/tasks \
  file_path="/Users/jack/Documents/250129_HuH7_crop.nd2" \
  fake:=true \
  config:='{}'
```

### List All Tasks
```bash
http GET :8000/processing/tasks
```

### Get Task Status
```bash
# Replace TASK_ID with actual task ID
http GET :8000/processing/tasks/TASK_ID

# Example with a real ID
http GET :8000/processing/tasks/a012b536-161e-472b-89fa-195f3a411d40
```

### Cancel Task
```bash
http DELETE :8000/processing/tasks/TASK_ID
```

---

## Testing Scenarios

### Test Fake Task Lifecycle
```bash
# 1. Create fake task
http POST :8000/processing/tasks \
  file_path="/fake/file.nd2" \
  fake:=true \
  config:='{}'

# 2. Poll status (run multiple times)
http GET :8000/processing/tasks/TASK_ID

# Expected progression:
# - pending (briefly)
# - running (with progress updates every second)
# - completed (after 60 seconds)
```

### Test Error Handling
```bash
# File not found (real task)
http POST :8000/processing/tasks \
  file_path="/does/not/exist.nd2" \
  config:='{}'
# Then poll - should show status: "failed"

# Invalid file format
touch /tmp/fake.nd2
http POST :8000/processing/tasks \
  file_path="/tmp/fake.nd2" \
  config:='{"channels": {"pc": {"channel": 0, "features": ["area"]}, "fl": []}}'
# Then poll - should show status: "failed" with error message

# Invalid config structure (422 immediately)
http POST :8000/processing/tasks \
  file_path="/some/file.nd2" \
  config:='{"channels": {"fl": []}}'
```

### Watch Progress (bash loop)
```bash
# Create task and save ID
TASK_ID=$(http POST :8000/processing/tasks \
  file_path="/fake/file.nd2" \
  fake:=true \
  config:='{}' | jq -r '.id')

# Poll every second
while true; do
  http GET :8000/processing/tasks/$TASK_ID | jq '{status, progress}'
  sleep 1
done
```

---

## Using curl Instead

If HTTPie is not available, use curl:

```bash
# GET request
curl -s http://localhost:8000/health | jq

# POST request
curl -s -X POST http://localhost:8000/processing/tasks \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/fake/file.nd2", "config": {}, "fake": true}' | jq

# DELETE request
curl -s -X DELETE http://localhost:8000/processing/tasks/TASK_ID | jq
```
