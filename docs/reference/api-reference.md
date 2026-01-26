# API Reference

This document provides complete API reference for the PyAMA Backend services, including the REST API, MCP (Model Context Protocol) integration, data models, and usage examples.

## Server Endpoints

PyAMA Core exposes two interfaces:

| Interface | Path | Description |
|-----------|------|-------------|
| REST API | `/api` | Traditional HTTP endpoints for frontend and scripts |
| MCP | `/mcp` | Model Context Protocol for AI assistant integration |

## Base URLs

**REST API:**
```
http://localhost:8000/api
```

**MCP SSE Endpoint:**
```
http://localhost:8000/mcp
```

## Authentication

Current version: No authentication (local development only)

Future support planned:
- API keys
- JWT tokens
- OAuth2

---

## MCP Integration

PyAMA Core supports the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), enabling AI assistants like Claude to interact with microscopy processing functionality directly.

### Connection

The MCP endpoint uses SSE (Server-Sent Events) transport at `/mcp`. Configure your MCP client to connect to:

```
http://localhost:8000/mcp
```

### Available MCP Tools

#### `load_microscopy`

Load a microscopy file and extract metadata.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `file_path` | string | Path to microscopy file (ND2, CZI, or TIFF format) |

**Returns:** Metadata including dimensions, channels, timepoints, and file info.

**Example Response:**
```json
{
  "n_fovs": 100,
  "n_frames": 180,
  "n_channels": 4,
  "channel_names": ["Phase", "GFP", "RFP", "DAPI"],
  "pixel_size_um": 0.65,
  "dtype": "uint16",
  "shape": [2048, 2048]
}
```

#### `get_processing_config_schema`

Get the JSON schema for processing configuration.

**Parameters:** None

**Returns:** JSON schema describing all available processing options including channels and parameters.

#### `create_processing_task`

Create and start a new image processing task.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `file_path` | string | Path to microscopy file to process |
| `config` | object | Processing configuration (channels and params) |
| `fake` | boolean | Run a 60-second simulated task for testing (default: false) |

**Config Structure:**
```json
{
  "channels": {
    "pc": {
      "channel": 0,
      "features": ["area", "aspect_ratio"]
    },
    "fl": [
      {
        "channel": 1,
        "features": ["intensity_total"]
      }
    ]
  },
  "params": {
    "fovs": "0-99",
    "batch_size": 2,
    "segmentation_method": "delta"
  }
}
```

**Returns:** Task object with ID and initial status.

#### `list_tasks`

List all processing tasks with their current status.

**Parameters:** None

**Returns:**
```json
{
  "tasks": [...],
  "total": 5
}
```

Task fields include: `id`, `status`, `progress`, `result`.

#### `get_task`

Get detailed status and progress of a specific task.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `task_id` | string | Task ID (UUID) to retrieve |

**Returns:** Complete task information including status, progress, result, error details, and timestamps.

#### `cancel_task`

Cancel a pending or running task.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `task_id` | string | Task ID (UUID) to cancel |

**Returns:** `{"success": true, "task_id": "..."}`

### MCP Client Configuration

**Claude Code (CLI):**
```bash
export PYAMA_MCP_URL="http://localhost:8000"  # adjust host/port as needed
claude mcp add pyama --transport sse "$PYAMA_MCP_URL/mcp"
```

**Claude Desktop** or other MCP-compatible clients — add this to your MCP configuration (adjust URL as needed):

```json
{
  "mcpServers": {
    "pyama": {
      "url": "http://localhost:8000/mcp",
      "transport": "sse"
    }
  }
}
```

### Example MCP Workflow

1. **Load file metadata:**
   ```
   load_microscopy(file_path="/data/experiment.nd2")
   ```

2. **Check available config options:**
   ```
   get_processing_config_schema()
   ```

3. **Create a processing task:**
   ```
   create_processing_task(
     file_path="/data/experiment.nd2",
     config={...}
   )
   ```

4. **Monitor progress:**
   ```
   get_task(task_id="abc-123-...")
   ```

---

## REST API

The REST API provides traditional HTTP endpoints for frontend applications and scripts.

## General Response Format

### Success Response
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation completed successfully"
}
```

### Error Response
```json
{
  "success": false,
  "error": "Error message description",
  "error_code": "ERROR_CODE",
  "details": { ... }
}
```

## Processing Endpoints

### Load Microscopy Metadata

Load metadata from an ND2/CZI microscopy file.

**Endpoint:** `POST /processing/load-metadata`

#### Request Body

```json
{
  "file_path": "/path/to/microscopy.nd2"
}
```

#### Response

```json
{
  "success": true,
  "data": {
    "n_fovs": 100,
    "n_frames": 180,
    "n_channels": 4,
    "channel_names": ["Phase", "GFP", "RFP", "DAPI"],
    "pixel_size_um": 0.65,
    "time_points": [0.0, 10.0, 20.0],
    "dtype": "uint16",
    "shape": [2048, 2048]
  }
}
```

#### Example

```javascript
const response = await fetch('/api/processing/load-metadata', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ file_path: '/data/experiment.nd2' })
});
const metadata = await response.json();
console.log(`${metadata.data.n_fovs} FOVs found`);
```

### Get Available Features

Retrieve list of available features for phase contrast and fluorescence channels.

**Endpoint:** `GET /processing/features`

#### Response

```json
{
  "success": true,
  "data": {
    "phase_features": [
      {
        "id": "area",
        "name": "Cell Area",
        "description": "Area of the cell in pixels",
        "units": "pixels^2"
      },
      {
        "id": "aspect_ratio",
        "name": "Aspect Ratio",
        "description": "Ratio of major to minor axis",
        "units": "ratio"
      }
    ],
    "fluorescence_features": [
      {
        "id": "intensity_total",
        "name": "Total Intensity",
        "description": "Sum of pixel intensities",
        "units": "arbitrary"
      }
    ]
  }
}
```

### Start Processing Workflow

Execute complete processing workflow with specified parameters.

**Endpoint:** `POST /processing/workflow/start`

#### Request Body

```json
{
  "microscopy_path": "/data/experiment.nd2",
  "output_dir": "/data/output",
  "channels": {
    "phase": {
      "channel": 0,
      "features": ["area", "aspect_ratio"]
    },
    "fluorescence": [
      {
        "channel": 1,
        "features": ["intensity_total"]
      },
      {
        "channel": 2,
        "features": ["intensity_mean"]
      }
    ]
  },
  "parameters": {
    "fov_start": 0,
    "fov_end": 99,
    "batch_size": 2,
    "n_workers": 4,
    "background_weight": 1.0
  }
}
```

#### Response

```json
{
  "success": true,
  "data": {
    "job_id": "job_1234567890",
    "message": "Workflow started successfully",
    "estimated_duration": 1800
  }
}
```

#### Data Models

**ChannelSelection:**
```json
{
  "channel": 0,        // Channel index (0-based)
  "features": [...]    // Array of feature IDs
}
```

**Channels:**
```json
{
  "phase": ChannelSelection,
  "fluorescence": [ChannelSelection]
}
```

**ProcessingParameters:**
```json
{
  "fov_start": 0,           // First FOV to process
  "fov_end": 99,            // Last FOV to process
  "batch_size": 2,          // FOVs per batch
  "n_workers": 4,           // Parallel workers
  "background_weight": 1.0  // Background correction [0-1]
}
```

### Get Workflow Status

Check status of a running workflow job.

**Endpoint:** `GET /processing/workflow/status/{job_id}`

#### Response

```json
{
  "success": true,
  "data": {
    "job_id": "job_1234567890",
    "status": "running",
    "progress": {
      "current_fov": 23,
      "total_fovs": 100,
      "percentage": 23.0,
      "current_step": "tracking",
      "steps_completed": ["copying", "segmentation", "correction"],
      "estimated_remaining": 900
    },
    "message": "Tracking FOV 23/100",
    "started_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:45:00Z"
  }
}
```

#### Status Values

- `pending`: Job queued but not started
- `running`: Job actively executing
- `completed`: Job finished successfully
- `failed`: Job failed with error
- `cancelled`: Job cancelled by user

### Cancel Workflow

Request cancellation of a running workflow.

**Endpoint:** `POST /processing/workflow/cancel/{job_id}`

#### Response

```json
{
  "success": true,
  "message": "Workflow cancellation requested",
  "data": {
    "job_id": "job_1234567890",
    "status": "cancelling"
  }
}
```

### Get Workflow Results

Retrieve results and output locations for completed workflow.

**Endpoint:** `GET /processing/workflow/results/{job_id}`

#### Response

```json
{
  "success": true,
  "data": {
    "job_id": "job_1234567890",
    "output_dir": "/data/output",
    "config_file": "/data/output/processing_config.yaml",
    "traces": [
      "/data/output/fov_000/experiment_fov_000_traces.csv",
      "/data/output/fov_001/experiment_fov_001_traces.csv"
    ],
    "stats": {
      "total_cells": 1500,
      "total_frames": 18000,
      "processing_time": 1200
    }
  }
}
```

### Merge Processing Results

Combine FOV results into sample-specific CSV files.

**Endpoint:** `POST /processing/merge`

#### Request Body

```json
{
  "sample_yaml": "/data/samples.yaml",
  "input_dir": "/data/output",
  "output_dir": "/data/merged"
}
```

#### Response

```json
{
  "success": true,
  "data": {
    "message": "Merge completed successfully",
    "output_dir": "/data/merged",
    "merged_files": [
      "/data/merged/control_merged.csv",
      "/data/merged/treatment_merged.csv"
    ],
    "stats": {
      "samples_processed": 2,
      "total_cells": 1500,
      "files_created": 2
    }
  }
}
```

## File Explorer Endpoints

### List Directory Contents

Browse directory with optional filtering.

**Endpoint:** `POST /processing/list-directory`

#### Request Body

```json
{
  "directory_path": "/data/experiments",
  "include_hidden": false,
  "filter_extensions": [".nd2", ".czi", ".txt"],
  "sort_by": "modified_time",
  "sort_order": "desc"
}
```

#### Response

```json
{
  "success": true,
  "data": {
    "directory_path": "/data/experiments",
    "items": [
      {
        "name": "experiment_20240115.nd2",
        "path": "/data/experiments/experiment_20240115.nd2",
        "is_directory": false,
        "is_file": true,
        "size_bytes": 1073741824,
        "modified_time": "2024-01-15T14:30:00Z",
        "extension": ".nd2",
        "is_microscopy_file": true
      },
      {
        "name": "subfolder",
        "path": "/data/experiments/subfolder",
        "is_directory": true,
        "is_file": false,
        "size_bytes": null,
        "modified_time": "2024-01-14T10:15:00Z",
        "extension": null,
        "is_microscopy_file": false
      }
    ],
    "total_items": 2,
    "filtered_items": 1
  }
}
```

### Search Files

Recursively search for files matching patterns.

**Endpoint:** `POST /processing/search-files`

#### Request Body

```json
{
  "search_path": "/data",
  "pattern": "**/*.nd2",
  "extensions": [".nd2", ".czi"],
  "max_depth": 5,
  "include_hidden": false,
  "case_sensitive": false
}
```

#### Response

```json
{
  "success": true,
  "data": {
    "search_path": "/data",
    "files": [
      {
        "name": "experiment.nd2",
        "path": "/data/experiments/experiment.nd2",
        "size_bytes": 1073741824,
        "modified_time": "2024-01-15T14:30:00Z"
      }
    ],
    "total_found": 1,
    "search_time": 0.15
  }
}
```

### Get File Information

Get detailed information and metadata for a specific file.

**Endpoint:** `POST /processing/file-info`

#### Request Body

```json
{
  "file_path": "/data/experiment.nd2"
}
```

#### Response

```json
{
  "success": true,
  "data": {
    "file_info": {
      "name": "experiment.nd2",
      "path": "/data/experiment.nd2",
      "is_directory": false,
      "is_file": true,
      "size_bytes": 1073741824,
      "modified_time": "2024-01-15T14:30:00Z",
      "extension": ".nd2"
    },
    "is_microscopy_file": true,
    "metadata_preview": {
      "n_fovs": 100,
      "n_frames": 180,
      "n_channels": 4,
      "channel_names": ["Phase", "GFP", "RFP", "DAPI"],
      "dtype": "uint16",
      "shape": [180, 100, 4, 2048, 2048]
    }
  }
}
```

### Get Recent Files

Retrieve recently accessed microscopy files.

**Endpoint:** `GET /processing/recent-files`

#### Query Parameters

- `limit` (optional): Maximum number of files (default: 10)
- `extensions` (optional): CSV of file extensions to filter

#### Response

```json
{
  "success": true,
  "data": {
    "recent_files": [
      {
        "path": "/data/experiment1.nd2",
        "accessed_at": "2024-01-15T15:30:00Z",
        "metadata": { ... }
      }
    ],
    "tracked": false  // Indicates if recent file tracking is enabled
  }
}
```

## Analysis Endpoints

### Get Available Models

List all available fitting models with parameters.

**Endpoint:** `GET /analysis/models`

#### Response

```json
{
  "success": true,
  "data": [
    {
      "name": "trivial",
      "description": "Constant model for testing",
      "equation": "f(t) = A + B",
      "parameters": [
        {
          "name": "amplitude",
          "symbol": "A",
          "default": 1.0,
          "bounds": [0.0, 10.0],
          "description": "Constant amplitude"
        },
        {
          "name": "offset",
          "symbol": "B",
          "default": 0.0,
          "bounds": [-5.0, 5.0],
          "description": "Vertical offset"
        }
      ]
    },
    {
      "name": "maturation",
      "description": "Exponential maturation model",
      "equation": "f(t) = A * (1 - e^(-kt)) + B",
      "parameters": [
        {
          "name": "amplitude",
          "symbol": "A",
          "default": 1.0,
          "bounds": [0.0, 10.0]
        },
        {
          "name": "rate",
          "symbol": "k",
          "default": 0.1,
          "bounds": [0.01, 1.0]
        },
        {
          "name": "offset",
          "symbol": "B",
          "default": 0.0,
          "bounds": [-1.0, 5.0]
        }
      ]
    }
  ]
}
```

### Load Trace Data

Load and validate trace CSV data.

**Endpoint:** `POST /analysis/load-traces`

#### Request Body

```json
{
  "csv_path": "/data/merged/traces.csv",
  "options": {
    "time_column": "time",
    "value_column": "value",
    "cell_column": "cell"
  }
}
```

#### Response

```json
{
  "success": true,
  "data": {
    "n_cells": 150,
    "n_timepoints": 180,
    "n_fovs": 100,
    "time_units": "hours",
    "columns": ["cell", "time", "value"],
    "time_range": {
      "min": 0.0,
      "max": 30.0
    },
    "value_range": {
      "min": 0.1,
      "max": 5.0
    },
    "summary": {
      "mean_trace_count_per_cell": 180,
      "cells_with_gaps": 12,
      "total_observations": 27000
    }
  }
}
```

### Start Fitting Analysis

Begin model fitting on loaded trace data.

**Endpoint:** `POST /analysis/fitting/start`

#### Request Body

```json
{
  "csv_path": "/data/merged/traces.csv",
  "model_type": "maturation",
  "model_params": {
    "amplitude": 1.5,
    "rate": 0.2,
    "offset": 0.1
  },
  "model_bounds": {
    "amplitude": [0.0, 10.0],
    "rate": [0.01, 1.0],
    "offset": [-1.0, 2.0]
  },
  "options": {
    "good_fits_only": false,
    "parallel": true,
    "n_workers": 4
  }
}
```

#### Response

```json
{
  "success": true,
  "data": {
    "job_id": "fit_1234567890",
    "message": "Fitting analysis started",
    "estimated_duration": 300
  }
}
```

### Get Fitting Status

Check progress of fitting job.

**Endpoint:** `GET /analysis/fitting/status/{job_id}`

#### Response

```json
{
  "success": true,
  "data": {
    "job_id": "fit_1234567890",
    "status": "running",
    "progress": {
      "current_cell": 75,
      "total_cells": 150,
      "percentage": 50.0,
      "successful_fits": 70,
      "failed_fits": 5,
      "average_r_squared": 0.92
    },
    "message": "Fitting cell 75/150",
    "current_params": {
      "model_type": "maturation",
      "convergence_rate": 0.95
    }
  }
}
```

### Cancel Fitting

Cancel running fitting analysis.

**Endpoint:** `POST /analysis/fitting/cancel/{job_id}`

#### Response

```json
{
  "success": true,
  "message": "Fitting cancellation requested"
}
```

### Get Fitting Results

Retrieve completed fitting results.

**Endpoint:** `GET /analysis/fitting/results/{job_id}`

#### Response

```json
{
  "success": true,
  "data": {
    "job_id": "fit_1234567890",
    "results_file": "/data/merged/traces_fitted_maturation.csv",
    "summary": {
      "total_cells": 150,
      "successful_fits": 145,
      "failed_fits": 5,
      "mean_r_squared": 0.92,
      "std_r_squared": 0.08
    },
    "model_type": "maturation",
    "parameters": [
      {
        "name": "amplitude",
        "mean": 1.23,
        "std": 0.45,
        "min": 0.12,
        "max": 5.67
      },
      {
        "name": "rate",
        "mean": 0.15,
        "std": 0.08,
        "min": 0.02,
        "max": 0.89
      },
      {
        "name": "offset",
        "mean": 0.23,
        "std": 0.12,
        "min": -0.45,
        "max": 1.23
      }
    ],
    "quality_distribution": {
      "good_r2": 130,
      "medium_r2": 15,
      "poor_r2": 5
    }
  }
}
```

## System Endpoints

### Health Check

Check API server health and status.

**Endpoint:** `GET /health`

#### Response

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": 3600,
  "active_jobs": 3,
  "system_info": {
    "python_version": "3.11.0",
    "platform": "Linux",
    "cpu_count": 8,
    "memory_gb": 32.0
  }
}
```

### System Metrics

Retrieve system performance metrics.

**Endpoint:** `GET /metrics`

#### Response

```json
{
  "timestamp": "2024-01-15T16:00:00Z",
  "cpu": {
    "usage_percent": 45.2,
    "load_average": [1.2, 1.5, 1.4]
  },
  "memory": {
    "total_gb": 32.0,
    "used_gb": 18.5,
    "available_gb": 13.5,
    "usage_percent": 57.8
  },
  "jobs": {
    "active": 3,
    "completed_today": 25,
    "failed_today": 1,
    "queue_length": 2
  }
}
```

### Active Jobs List

List all currently active jobs.

**Endpoint:** `GET /jobs`

#### Response

```json
{
  "success": true,
  "data": {
    "active_jobs": [
      {
        "job_id": "job_1234567890",
        "type": "workflow",
        "status": "running",
        "progress": 75.0,
        "started_at": "2024-01-15T15:30:00Z"
      },
      {
        "job_id": "fit_1234567891",
        "type": "fitting",
        "status": "queued",
        "progress": 0.0,
        "started_at": null
      }
    ],
    "total_active": 2
  }
}
```

## Error Codes

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| FILE_NOT_FOUND | 404 | Requested file does not exist |
| INVALID_PARAMETERS | 400 | Request parameters are invalid |
| PROCESSING_ERROR | 500 | Error during processing |
| JOB_NOT_FOUND | 404 | Job ID does not exist |
| JOB_ALREADY_COMPLETED | 400 | Job has already completed |
| INTERNAL_ERROR | 500 | Unexpected server error |
| UNAUTHORIZED | 401 | Authentication required (future) |
| FORBIDDEN | 403 | Access denied (future) |
| RATE_LIMITED | 429 | Too many requests (future) |

## Usage Examples

### Python Client Library

```python
import requests
from typing import Optional, Dict, Any

class PyAMAClient:
    def __init__(self, base_url: str = "http://localhost:8000/api"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def load_metadata(self, file_path: str) -> Dict[str, Any]:
        """Load microscopy metadata."""
        response = self.session.post(
            f"{self.base_url}/processing/load-metadata",
            json={"file_path": file_path}
        )
        response.raise_for_status()
        return response.json()['data']
    
    def start_workflow(self, config: Dict[str, Any]) -> str:
        """Start processing workflow."""
        response = self.session.post(
            f"{self.base_url}/processing/workflow/start",
            json=config
        )
        response.raise_for_status()
        return response.json()['data']['job_id']
    
    def wait_for_job(self, job_id: str, timeout: int = 3600) -> Dict[str, Any]:
        """Poll job until completion."""
        import time
        start_time = time.time()
        
        while True:
            response = self.session.get(
                f"{self.base_url}/processing/workflow/status/{job_id}"
            )
            response.raise_for_status()
            data = response.json()['data']
            
            if data['status'] in ['completed', 'failed', 'cancelled']:
                return data
            
            if time.time() - start_time > timeout:
                raise TimeoutError("Job timeout")
            
            time.sleep(5)
    
    def run_complete_workflow(self, file_path: str, output_dir: str) -> Dict[str, Any]:
        """Run complete workflow from file to results."""
        # Load metadata
        metadata = self.load_metadata(file_path)
        
        # Create configuration
        config = {
            "microscopy_path": file_path,
            "output_dir": output_dir,
            "channels": {
                "phase": {"channel": 0, "features": ["area", "aspect_ratio"]},
                "fluorescence": [
                    {"channel": 1, "features": ["intensity_total"]}
                ]
            },
            "parameters": {
                "fov_start": 0,
                "fov_end": metadata['n_fovs'] - 1,
                "batch_size": 2,
                "n_workers": 4
            }
        }
        
        # Start workflow
        job_id = self.start_workflow(config)
        
        # Wait for completion
        results = self.wait_for_job(job_id)
        
        # Get results
        response = self.session.get(
            f"{self.base_url}/processing/workflow/results/{job_id}"
        )
        response.raise_for_status()
        
        return response.json()['data']

# Usage
client = PyAMAClient()
results = client.run_complete_workflow(
    file_path="/data/experiment.nd2",
    output_dir="/data/output"
)
print(f"Results saved to: {results['output_dir']}")
```

### JavaScript/TypeScript Client

```typescript
interface WorkflowConfig {
  microscopy_path: string;
  output_dir: string;
  channels: Channels;
  parameters: ProcessingParameters;
}

class PyAMAClient {
  constructor(private baseUrl: string = 'http://localhost:8000/api') {}
  
  async loadMetadata(filePath: string): Promise<MicroscopyMetadata> {
    const response = await fetch(`${this.baseUrl}/processing/load-metadata`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_path: filePath })
    });
    
    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }
    
    const result = await response.json();
    return result.data;
  }
  
  async startWorkflow(config: WorkflowConfig): Promise<string> {
    const response = await fetch(`${this.baseUrl}/processing/workflow/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });
    
    const result = await response.json();
    return result.data.job_id;
  }
  
  async monitorJob(jobId: string, onUpdate: (status: JobStatus) => void): Promise<JobStatus> {
    return new Promise((resolve, reject) => {
      const poll = async () => {
        try {
          const response = await fetch(`${this.baseUrl}/processing/workflow/status/${jobId}`);
          const data = await response.json();
          const status = data.data;
          
          onUpdate(status);
          
          if (status.status === 'completed' || status.status === 'failed') {
            resolve(status);
          } else {
            setTimeout(poll, 2000);
          }
        } catch (error) {
          reject(error);
        }
      };
      
      poll();
    });
  }
}

// React Hook for Workflow Management
export function usePyamaWorkflow() {
  const [jobs, setJobs] = React.useState<Map<string, JobStatus>>(new Map());
  const client = React.useMemo(() => new PyAMAClient(), []);
  
  const startWorkflow = React.useCallback(async (config: WorkflowConfig) => {
    const jobId = await client.startWorkflow(config);
    setJobs(prev => new Map(prev).set(jobId, { job_id: jobId, status: 'pending' }));
    
    // Start monitoring
    client.monitorJob(jobId, (status) => {
      setJobs(prev => new Map(prev).set(jobId, status));
    });
    
    return jobId;
  }, [client]);
  
  return { jobs, startWorkflow };
}
```

This API reference provides complete documentation for all endpoints, data models, and usage patterns.
