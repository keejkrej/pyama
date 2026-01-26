# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentation Synchronization

**IMPORTANT**: This file contains all repository guidelines for AI agents working with this codebase.

## Project Overview

PyAMA is a modular Python application for microscopy image analysis consisting of the following packages in a UV workspace:

- **pyama-core**: Core processing library with analysis, processing workflows, I/O utilities, REST API server, and MCP integration
- **pyama-qt**: Qt-based GUI with tabs for Processing, Analysis, and Visualization
- **pyama-preact**: Modern web frontend built with Preact + Tailwind CSS, packaged as a Tauri desktop app (lives outside the UV workspace)
- **pyama-acdc**: Cell-ACDC integration plugin

## Development Commands

### Environment Setup

```bash
# Install all dependencies including dev tools
uv sync --all-extras

# Install in development mode
uv pip install -e pyama-core/
uv pip install -e pyama-qt/
```

### Testing

```bash
# Run pytest (test discovery from workspace root)
uv run pytest

# Run specific test module
uv run pytest pyama-core/tests/processing/test_merge.py

# Run tests for a specific package
uv run pytest pyama-core/tests/
```

#### Testing rules (agents must follow)

- Only implement essential tests that demonstrate correctness visually for core algorithms.
  - Event detection: include noisy step-up and step-down only; each test saves a plot with a vertical event line.
  - Particle counting: include a single scenario with many Gaussian particles on a noisy background; assert all particles are detected and draw bounding boxes.
- Plots must always be saved under `{package}/tests/_plots/` (e.g., `pyama-core/tests/_plots/` for core tests). Allow override via `PYAMA_PLOT_DIR` env var.
- Use deterministic RNG (`np.random.seed(...)` or `RandomState`) inside tests to avoid flakiness.
- Keep assertions robust and minimal (e.g., count matches expected, event index near the step), avoid tight numerical tolerances on noisy data.
- Do not depend on OS-specific temp directories; never write to `/tmp` in tests.
- Keep tests top-level functions (no classes/fixtures unless necessary) to reduce boilerplate and speed up runs.
- Ensure tests can run headless; use Matplotlib without interactive backends and always close figures (`plt.close(fig)`).
- Add `**/tests/_plots/` to `.gitignore` so generated images aren’t committed.

### Code Quality

```bash
# Lint code with ruff (from pyama-qt dev dependencies)
uv run ruff check

# Format code
uv run ruff format

# Type checking (use ty from dev dependencies)
uv run ty check
```

### Running the Application

```bash
# Launch Qt GUI application
uv run pyama-qt

# Alternative: run directly
uv run python pyama-qt/src/pyama_qt/main.py

# Start API server (for pyama-preact frontend)
uv run pyama-core serve --port 8000 --reload
```

### CLI Commands

```bash
# All commands available via pyama-core CLI
uv run pyama-core workflow             # Interactive processing workflow
uv run pyama-core workflow -c cfg.yaml -n data.nd2  # Config-based workflow
uv run pyama-core merge                # Interactive CSV merge wizard
uv run pyama-core trajectory traces.csv  # Plot cell trajectories
uv run pyama-core plot data.npy        # Plot numpy array files
uv run pyama-core serve                # Start FastAPI server
```

### Web Frontend (pyama-preact)

```bash
cd pyama-preact

# Install dependencies
bun install  # or npm install

# Development
bun run dev           # Vite dev server (localhost:5173)
bun run tauri:dev     # Tauri desktop app with hot reload

# Production
bun run build         # Build web assets
bun run tauri:build   # Build native desktop app
```

## Architecture

### Core Processing Pipeline

The application centers around a workflow pipeline (`pyama_core.processing.workflow.pipeline.run_complete_workflow`) that orchestrates microscopy image processing through these services:

1. **CopyingService**: Handles data loading and copying from ND2 files (runs sequentially per batch)
2. **SegmentationService**: Cell segmentation using LOG-STD approach
3. **CorrectionService**: Background correction for fluorescence channels
4. **TrackingService**: Cell tracking across time points using IoU
5. **ExtractionService**: Feature extraction and trace generation to CSV

The pipeline processes FOVs in batches using multithreading (`ThreadPoolExecutor`). Each batch is copied sequentially, then split across threads for parallel processing through steps 2-5. Worker contexts are merged back into the parent context after completion.

**FOV Selection**: FOVs can be specified using flexible range syntax (e.g., `"0-5, 7, 10-15"`) via `parse_fov_range()` in `pyama_core.processing.merge`. The workflow uses `fov_list` parameter; legacy configs with `fov_start`/`fov_end` are auto-migrated.

**Particle Detection**: Fluorescence particle counting uses the Spotiflow deep learning model (`spotiflow` package) with the pretrained "general" model for subpixel-accurate spot detection (see `pyama_core.processing.extraction.features.fluorescence.particle_num`).

### Processing Context

The `ProcessingContext` dataclass (in `pyama_core.types.processing`) is the central data structure that flows through the pipeline, containing:

- Output directory paths
- Channel configurations (`Channels` dataclass with `pc` and `fl` fields)
- Processing parameters
- Config is saved to `processing_config.yaml` for reference
- FOV outputs are discovered by file naming conventions (e.g., `fov_000/`, `fov_001/`)

**Output schema highlights**

- `channels.pc` serializes as `[phase_channel, [feature1, ...]]` and `channels.fl` as `[[channel, [feature1, ...]], ...]`, capturing both channel IDs and the enabled feature sets.
- Per-FOV trace CSVs are at `fov_{id}/{basename}_fov_{id}_traces.csv`. Feature columns are suffixed with `_ch_{channel_id}` (e.g., `intensity_total_ch_1`, `area_ch_0`) so downstream tools can isolate per-channel data.

### REST API & MCP Server

The `pyama_core.api` module provides a FastAPI server (`pyama_core.api.server.create_app`) with both REST and MCP endpoints:

**API Routes** (under `/api`):
- `POST /api/data/microscopy` - Load microscopy file metadata
- `POST /api/processing/tasks` - Create a processing task
- `GET /api/processing/tasks` - List all tasks
- `GET /api/processing/tasks/{task_id}` - Get task status and progress
- `DELETE /api/processing/tasks/{task_id}` - Cancel a task
- `GET /api/processing/config` - Schema discovery for processing configuration

**MCP Endpoint**: Streamable HTTP transport mounted at `/mcp` with tools mirroring the REST API (`load_microscopy`, `get_processing_config_schema`, `create_task`, etc.)

**Connect Claude Code as MCP client** (requires server running):
```bash
export PYAMA_MCP_URL="http://localhost:8000"  # adjust host/port as needed
claude mcp add pyama --transport http "$PYAMA_MCP_URL/mcp"
```

**Architecture**:
- **Routes** (`api/routes/`): FastAPI routers for data and processing endpoints
- **Schemas** (`api/schemas/`): Pydantic models for request/response validation (`TaskCreate`, `TaskResponse`, `ProcessingConfigSchema`, `MicroscopyMetadataSchema`)
- **Services** (`api/services/`): Business logic layer (`TaskService` for task CRUD/execution, `MicroscopyService` for file handling)
- **Database** (`api/database.py`): SQLite-based task persistence at `~/.pyama/tasks.db` with columns for status, progress, config, and timing
- **MCP** (`api/mcp/`): Model Context Protocol server with tool definitions

**CORS**: Configured for Tauri (`tauri://localhost`, `localhost:1420`) and Vite (`localhost:5173`) dev servers.

**Task execution**: Supports both real processing workflows and a `fake` mode (60-second simulation) for frontend development. Tasks track `phase`, `current_fov`, `total_fovs`, `progress_percent`, and `progress_message`.

### Preact Web Frontend (pyama-preact)

A modern desktop application using Preact + Tauri, separate from the UV workspace.

**Stack**: Preact, TypeScript, Tailwind CSS 4, Vite, Tauri 2.x

**Structure**:
- Custom component library (`components/ui/`): card, button, badge, modal, file-picker, checkbox, select, input, table, theme-toggle
- Processing page with task creation, configuration, and progress polling
- Communicates with pyama-core via REST API (`localhost:8000`)

### Qt Application Structure

The Qt GUI uses a simplified tab-based architecture without strict MVC separation:

**Main Components:**

- **ProcessingTab** (`pyama_qt.processing.main_tab`): Data processing workflows and parameter tuning
- **AnalysisTab** (`pyama_qt.analysis.main_tab`): Analysis models and fitting (maturation, maturation-blocked, trivial models)
- **VisualizationTab** (`pyama_qt.visualization.main_tab`): Data visualization and plotting

**Component Classes:**

- **ParameterTable** (`pyama_qt.components.parameter_table`): Table-based parameter editing widget (renamed from ParameterPanel)
- **ParameterPanel** (`pyama_qt.analysis.parameter`): Parameter visualization and analysis widget
- **QualityPanel** (`pyama_qt.analysis.quality`): Fitting quality inspection with FOV-based trace pagination and quality statistics

**Background Workers:** Long-running tasks (fitting, ND2 loading) use QObject workers in separate threads via `pyama_qt.utils.threading`

### Qt Signal/Slot Guidelines

- All signal receiver methods must use `@Slot()` decorator for performance and type safety
- Use `_build_ui()` and `_connect_signals()` methods for Qt widget initialization
- Signal naming follows snake_case convention
- **Semantic signals only**: Child panels should emit semantic signals like `workflow_finished(success, message)` instead of generic `status_message(text)`
- **No redundant status messages**: Don't emit generic status messages when semantic signals already convey the same information
- **Event-specific signals**: Each major operation should have its own started/finished signal pair with rich data payload
- Main tab handles status updates centrally through semantic signal handlers

#### Unified Signal Pattern

**IMPORTANT**: All operations across tabs must follow a consistent signal pattern for status updates:

**Panel-Level Signal Pattern (for UI status updates):**

- `operation_started()` - Emitted when operation begins
- `operation_finished(bool, str)` - Emitted when operation completes (success, detailed_message)

**Worker-Level Signal Pattern (for data transfer):**

- Background workers (`QObject` workers in separate threads) emit:
  - `finished(bool, str)` - For operations that return status messages (e.g., `AnalysisWorker`, `WorkflowRunner`)
  - `finished(bool, object)` - For operations that return data payloads (e.g., `MicroscopyLoaderWorker` emits `MicroscopyMetadata | None`, `VisualizationWorker` emits `dict | None` with `{"fov_id": int, "image_map": dict, "payload": dict}`)
- Panel handlers convert worker signals to panel-level semantic signals for UI coordination

**Status Message Guidelines:**

- **Success**: Show the detailed message from the operation (e.g., "Results saved to /path/to/output", "Samples loaded from /path/to/file")
- **Failure**: Show "Failed to [operation]: [error message]"
- **Started**: Show generic progress message (e.g., "Processing workflow started...", "Loading samples...")

**Examples:**

```python
# Processing Tab - Panel-level signals
workflow_started = Signal()
workflow_finished = Signal(bool, str)
microscopy_loading_started = Signal()
microscopy_loading_finished = Signal(bool, str)

# Merge Panel - Panel-level signals
merge_started = Signal()
merge_finished = Signal(bool, str)
samples_loading_started = Signal()
samples_loading_finished = Signal(bool, str)
samples_saving_started = Signal()
samples_saving_finished = Signal(bool, str)

# Worker-level signals (internal)
class MicroscopyLoaderWorker(QObject):
    finished = Signal(bool, object)  # (success, MicroscopyMetadata | None)

class VisualizationWorker(QObject):
    finished = Signal(bool, object)  # (success, dict | None with fov_id, image_map, payload)

class AnalysisWorker(QObject):
    finished = Signal(bool, str)  # (success, message)
```

**Handler Pattern:**

```python
@Slot(bool, str)
def _on_operation_finished(self, success: bool, message: str) -> None:
    """Handle operation finished event."""
    logger.info("Operation finished (success=%s): %s", success, message)
    if self._status_manager:
        if success:
            self._status_manager.show_message(message)  # Show detailed message
        else:
            self._status_manager.show_message(f"Failed to [operation]: {message}")

# Worker signal handler (converts to panel signal)
@Slot(bool, object)
def _on_worker_finished(self, success: bool, data: object) -> None:
    """Handle worker completion and convert to panel signal."""
    if success and data:
        # Process data payload (e.g., metadata, image_map)
        # ...
        self.microscopy_loading_finished.emit(True, "File loaded successfully")
    else:
        self.microscopy_loading_finished.emit(False, "Failed to load file")
```

### One-Way UI→Model Binding Architecture

**IMPORTANT**: PyAMA-Qt uses strict one-way binding from UI to model only. This prevents circular dependencies and makes data flow predictable.

#### Requirements

- **UI→Model only**: User input updates model state, but models don't automatically update UI
- **No model→UI synchronization**: UI refreshes must be explicit, not automatic
- **Signal-based communication**: Cross-panel updates via explicit Qt signals
- **Manual mode pattern**: Parameter panels only update model when user enables manual editing
- **Direct assignment**: UI event handlers directly update model attributes

#### Implementation Pattern

```python
@Slot()
def _on_ui_widget_changed(self) -> None:
    """Handle UI widget change (UI→Model only)."""
    # Get value from UI widget
    ui_value = self._ui_widget.current_value()

    # Update model directly (one-way binding)
    self._model_attribute = ui_value

    # Optionally emit signal for other panels
    self.model_changed.emit()
```

#### Forbidden Patterns

- Automatic UI updates when model changes
- Bidirectional data binding
- Signal loops where UI changes trigger model changes which trigger UI changes
- Model→UI automatic synchronization

#### Allowed Patterns

- Initial UI population from model defaults
- Manual UI refresh methods called explicitly
- Cross-panel communication via signals
- Background workers loading data into model

#### Reference Documentation

For detailed UI architecture information, refer to the component documentation in `pyama_qt/components/` and tab implementations in `pyama_qt/processing/`, `pyama_qt/analysis/`, and `pyama_qt/visualization/`.

### Key Data Types

- ND2 and CZI files are the primary input formats for microscopy data (via bioio-nd2 and bioio-czi)
- Processing operates on FOVs (fields of view) with configurable batch sizes and worker counts
- Channel indexing distinguishes phase contrast (pc) from fluorescence (fl) channels
- Outputs include segmentation masks, corrected fluorescence, and extracted traces (CSV format)

### CSV Data Structures

PyAMA uses consistent CSV formats for data exchange between components.

#### Analysis/Merged CSV (Tidy Format)

Input format for analysis. Contains trace data in tidy/long format with one observation per row.

**Columns:**
- `frame` - Frame index (0-based integer)
- `fov` - Field of view index (integer)
- `cell` - Cell ID within the FOV (integer)
- `value` - Measurement value (e.g., intensity)

**Example:**
```csv
frame,fov,cell,value
0,0,0,1.234
0,0,1,2.345
1,0,0,1.456
1,0,1,2.567
0,1,0,3.456
```

**Loading behavior:** `load_analysis_csv()` returns a DataFrame with MultiIndex `(fov, cell)` and columns `frame`, `time`, `value`. The `time` column is computed from `frame` using either a `frame_interval` parameter (default: 1.0 hours) or a `time_mapping` dict for non-equidistant time points:
```python
# Using frame interval (equidistant time points)
df = load_analysis_csv(path, frame_interval=1/6)  # 10 min per frame

# Using time mapping (non-equidistant time points)
time_mapping = {0: 0.0, 1: 0.167, 2: 0.5, ...}  # frame -> time in hours
df = load_analysis_csv(path, time_mapping=time_mapping)

# Access cell (fov=0, cell=1) data:
cell_data = df.loc[(0, 1)]  # Returns DataFrame with frame, time, value columns
```

#### Fitted Results CSV

Output format from fitting operations. Contains one row per cell with fitting results.

**Columns:**
- `fov` - Field of view index (integer)
- `cell` - Cell ID within the FOV (integer)
- `model_type` - Name of the fitted model (e.g., "maturation")
- `success` - Whether fitting succeeded (boolean)
- `r_squared` - R² goodness of fit (float, 0-1)
- `{param_name}` - One column per fitted parameter value

**Example:**
```csv
fov,cell,model_type,success,r_squared,amplitude,rate,offset
0,0,maturation,True,0.95,1.234,0.567,0.123
0,1,maturation,True,0.88,2.345,0.678,0.234
1,0,maturation,False,0.45,0.000,0.000,0.000
```

#### Processing Traces CSV

Output from extraction step. Contains per-cell, per-frame features with channel suffixes.

**Columns:**
- `fov` - Field of view index
- `cell` - Cell ID
- `frame` - Frame index (0-based)
- `good` - Quality flag (boolean)
- `position_x`, `position_y` - Cell centroid
- `bbox_x0`, `bbox_y0`, `bbox_x1`, `bbox_y1` - Bounding box
- `{feature}_ch_{channel_id}` - Feature columns with channel suffix

**Example:**
```csv
fov,cell,frame,good,position_x,position_y,intensity_total_ch_1,area_ch_0
0,0,0,True,100.5,200.3,1234.5,450
0,0,1,True,101.2,199.8,1356.2,455
```

**Note:** Processing CSVs only contain `frame`, not `time`. Time is computed at analysis load time using `frame_interval` or `time_mapping`.

## Workflow Execution Philosophy

### No Artificial Timeouts

**IMPORTANT**: The workflow execution does not use artificial timeouts. Processing continues until completion or manual user cancellation.

**Rationale**:

- Timeouts don't scale with dataset complexity (number of FOVs, frames, features)
- Users can manually cancel if processing takes too long
- Prevents premature failures on large datasets
- Simplifies debugging by removing timeout-related failures

**Implementation**:

- No timeout parameter in `as_completed(futures)` calls
- No `TimeoutError` handling in workflow execution
- Cleanup operations are commented out to preserve partial results for debugging
- Users control workflow termination through GUI cancellation

### Visualization Preprocessing

- Normalize 3D time stacks using a single percentile-based scale computed over the entire stack (not per frame) so all frames share the same vmin/vmax; downstream rendering should assume the resulting uint8 range (0-255).

## Development Notes

- Uses UV for dependency management with workspace configuration (`pyama-core`, `pyama-qt`, `pyama-acdc`; `pyama-preact` is a separate Node.js project)
- Built on Python 3.11+ with scientific computing stack (numpy, scipy, scikit-image, xarray)
- Qt GUI built with PySide6
- REST API built with FastAPI + uvicorn; MCP integration via `mcp` package
- Deep learning features via Spotiflow (particle detection) and Cellpose (segmentation)
- Processing pipeline supports multiprocessing with configurable worker counts
- Tests are located in `{package}/tests/` directories (e.g., `pyama-core/tests/` for core) organized by component (analysis, features, processing, utils)
- Typing style: prefer built-in generics (dict, list, tuple) and union types using '|' over typing.Dict, typing.List, typing.Tuple, typing.Union
- **Import organization**: All import statements must be at the top of the file - no scattered imports within functions
- **Logging in pyama-qt**: `logger.info` messages must communicate user-facing progress with actionable context (paths, counts, selected options), while `logger.debug` should capture developer diagnostics (IDs, parameter values, ranges) rather than generic text.
