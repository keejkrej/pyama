# PyAMA Backend

PyAMA Backend is a FastAPI-based REST API server that provides programmatic access to PyAMA's functionality. It enables integration with web applications, automated pipelines, and remote analysis workflows.

## Installation

```bash
# Install as part of the workspace
uv pip install -e pyama-backend/
```

## Running the Server

### Development Mode
```bash
# Using uv
uv run python -m pyama_backend

# Using uvicorn directly
uvicorn pyama_backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode
```bash
uvicorn pyama_backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Base URL
```
http://localhost:8000/api/v1
```

## API Documentation

Once running, access interactive documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Key Features

### Asynchronous Job Processing
- Long-running operations use background jobs
- Poll job status during execution
- Cancel jobs if needed
- Retain results after completion

### File System Access
- Direct file path handling (no upload required initially)
- Absolute paths for security
- File browser capabilities

### Comprehensive Endpoints
- **Processing**: Load metadata, run workflows, merge results
- **Analysis**: Fit models, analyze traces
- **File Explorer**: Browse directories, search files

## API Endpoints

### Processing Endpoints

#### Load Metadata
```http
POST /processing/load-metadata
{
  "file_path": "/path/to/file.nd2"
}
```

#### Start Workflow
```http
POST /processing/workflow/start
{
  "microscopy_path": "/path/to/file.nd2",
  "output_dir": "/path/to/output",
  "channels": {
    "phase": {"channel": 0, "features": ["area", "aspect_ratio"]},
    "fluorescence": [
      {"channel": 1, "features": ["intensity_total"]}
    ]
  },
  "parameters": {
    "fov_start": 0,
    "fov_end": 99,
    "batch_size": 2,
    "n_workers": 2
  }
}
```

#### Get Workflow Status
```http
GET /processing/workflow/status/{job_id}
```

#### Cancel Workflow
```http
POST /processing/workflow/cancel/{job_id}
```

#### Merge Results
```http
POST /processing/merge
{
  "sample_yaml": "/path/to/samples.yaml",
  "input_dir": "/path/to/processed_fovs",
  "output_dir": "/path/to/output"
}
```

### Analysis Endpoints

#### Get Available Models
```http
GET /analysis/models
```

#### Load Trace Data
```http
POST /analysis/load-traces
{
  "csv_path": "/path/to/traces.csv"
}
```

#### Start Fitting
```http
POST /analysis/fitting/start
{
  "csv_path": "/path/to/traces.csv",
  "model_type": "maturation",
  "model_params": {
    "amplitude": 1.0,
    "rate": 0.1,
    "offset": 0.0
  },
  "model_bounds": {
    "amplitude": [0.0, 10.0],
    "rate": [0.01, 1.0],
    "offset": [-1.0, 5.0]
  }
}
```

#### Get Fitting Status
```http
GET /analysis/fitting/status/{job_id}
```

#### Get Fitting Results
```http
GET /analysis/fitting/results/{job_id}
```

### File Explorer Endpoints

#### List Directory
```http
POST /processing/list-directory
{
  "directory_path": "/path/to/directory",
  "include_hidden": false,
  "filter_extensions": [".nd2", ".czi", ".txt"]
}
```

#### Search Files
```http
POST /processing/search-files
{
  "search_path": "/path/to/search",
  "pattern": "**/*.{nd2,czi}",
  "extensions": [".nd2", ".czi"],
  "max_depth": 5,
  "include_hidden": false
}
```

#### Get File Information
```http
POST /processing/file-info
{
  "file_path": "/path/to/file.nd2"
}
```

#### Get Recent Files
```http
GET /processing/recent-files?limit=10&extensions=.nd2,.czi
```

## Data Models

### Job Status
```json
{
  "job_id": "job_123456",
  "status": "running",
  "progress": {
    "current_fov": 45,
    "total_fovs": 100,
    "percentage": 45.0
  },
  "message": "Processing FOV 45/100"
}
```

### Channel Configuration
```json
{
  "phase": {
    "channel": 0,
    "features": ["area", "aspect_ratio"]
  },
  "fluorescence": [
    {
      "channel": 1,
      "features": ["intensity_total", "intensity_mean"]
    }
  ]
}
```

### Workflow Parameters
```json
{
  "fov_start": 0,
  "fov_end": 99,
  "batch_size": 2,
  "n_workers": 2,
  "background_weight": 1.0
}
```

## Usage Examples

### Python Client
```python
import requests

# Load metadata
response = requests.post(
    "http://localhost:8000/api/v1/processing/load-metadata",
    json={"file_path": "/data/experiment.nd2"}
)
metadata = response.json()

# Start workflow
response = requests.post(
    "http://localhost:8000/api/v1/processing/workflow/start",
    json={
        "microscopy_path": "/data/experiment.nd2",
        "output_dir": "/data/output",
        "channels": metadata["suggested_channels"],
        "parameters": {"fov_start": 0, "fov_end": 9}
    }
)
job_id = response.json()["job_id"]

# Monitor progress
while True:
    response = requests.get(
        f"http://localhost:8000/api/v1/processing/workflow/status/{job_id}"
    )
    status = response.json()
    print(f"Progress: {status['progress']['percentage']}%")
    
    if status["status"] in ["completed", "failed"]:
        break
    
    time.sleep(5)

# Get results
response = requests.get(
    f"http://localhost:8000/api/v1/processing/workflow/results/{job_id}"
)
results = response.json()
```

### JavaScript/Fetch
```javascript
// Workflow configuration
const config = {
  microscopy_path: "/data/experiment.nd2",
  output_dir: "/data/output",
  channels: {
    phase: {channel: 0, features: ["area"]},
    fluorescence: [{channel: 1, features: ["intensity_total"]}]
  },
  parameters: {batch_size: 2, n_workers: 4}
};

// Start workflow
const response = await fetch('/api/v1/processing/workflow/start', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(config)
});
const {job_id} = await response.json();

// Monitor with setInterval
const monitor = setInterval(async () => {
  const status = await fetch(`/api/v1/processing/workflow/status/${job_id}`);
  const data = await status.json();
  
  console.log(`${data.progress.percentage}% complete`);
  
  if (data.status === 'completed') {
    clearInterval(monitor);
    console.log('Job finished!');
  }
}, 2000);
```

### cURL Examples
```bash
# Load file metadata
curl -X POST "http://localhost:8000/api/v1/processing/load-metadata" \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/data/sample.nd2"}'

# List directory
curl -X POST "http://localhost:8000/api/v1/processing/list-directory" \
  -H "Content-Type: application/json" \
  -d '{"directory_path": "/data", "filter_extensions": [".nd2"]}'

# Get available models
curl -X GET "http://localhost:8000/api/v1/analysis/models"
```

## Authentication

Current version: No authentication (suitable for local development)

Future versions will support:
- API key authentication
- JWT tokens
- User management

## Error Handling

Standard error response format:
```json
{
  "success": false,
  "error": "Error message",
  "error_code": "ERROR_CODE"
}
```

Common error codes:
- `FILE_NOT_FOUND`: Requested file doesn't exist
- `INVALID_PARAMETERS`: Invalid request parameters
- `PROCESSING_ERROR`: Error during processing
- `JOB_NOT_FOUND`: Invalid job ID
- `INTERNAL_ERROR`: Unexpected server error

## Configuration

### Environment Variables
```bash
# Server settings
export PYAMA_HOST=0.0.0.0
export PYAMA_PORT=8000
export PYAMA_DEBUG=false

# Processing limits
export PYAMA_MAX_JOBS=10
export PYAMA_JOB_TIMEOUT=3600  # seconds

# File system
export PYAMA_ALLOWED_PATHS="/data,/experiment"
```

### Docker Deployment
```dockerfile
FROM python:3.11

WORKDIR /app
COPY . .

RUN pip install -e .
RUN pip install uvicorn

EXPOSE 8000
CMD ["uvicorn", "pyama_backend.main:app", "--host", "0.0.0.0"]
```

## Deployment Options

### Local Development
- Use `--reload` flag for auto-reloading
- Logs to console
- Single worker process

### Production
- Multiple worker processes
- Gunicorn/uvicorn workers
- Log files
- Process monitoring (systemd/supervisor)

### Cloud Deployment
- Docker containers
- Kubernetes deployment
- Load balancer for multiple instances
- Redis for job queue (future)

## Monitoring

### Health Check
```http
GET /health
```

### Metrics
```http
GET /metrics
```

### Active Jobs
```http
GET /jobs
```

## Extending the API

### Adding Endpoints
1. Define Pydantic models for request/response
2. Implement endpoint function with type hints
3. Add to router in main.py
4. Update OpenAPI documentation

### Custom Workers
1. Create worker class inheriting from BaseWorker
2. Implement execute() method
3. Register in job manager
4. Add client endpoints

### Middleware
- Request logging
- CORS handling
- Rate limiting
- Authentication (future)

## Best Practices

### Client Implementation
- Use exponential backoff for status polling
- Validate file paths before submission
- Handle network errors gracefully
- Implement timeout logic

### Server Usage
- Monitor job queue length
- Clean up completed jobs periodically
- Log all processing errors
- Use proper HTTP status codes

### Security
- Validate all input paths
- Restrict file system access
- Sanitize error messages
- Plan for authentication

## Integration Examples

### With React/Frontend
- Use fetch API or axios
- Implement real-time updates with polling
- Handle file uploads (future feature)
- Display progress bars

### With Python Scripts
- Use requests library
- Batch process multiple files
- Automate pipeline steps
- Export results to databases

### With Other Services
- Webhook notifications on completion
- Integration with cloud storage
- Email alerts for failures
- Dashboard visualization

## Next Steps

- See [API Reference](../reference/api-reference.md) for detailed endpoint documentation
- Check [Workflow Pipeline](../reference/workflow-pipeline.md) for processing details
- Visit [User Guide](../user-guide/) for workflow concepts

PyAMA Backend enables programmatic access to all PyAMA capabilities, making it suitable for web applications, automated pipelines, and integrations with other bioinformatics tools.
