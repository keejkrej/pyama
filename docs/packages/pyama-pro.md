# PyAMA-Pro

PyAMA-Pro is the Qt-based graphical user interface for PyAMA, providing comprehensive tools for microscopy image analysis through a tabbed interface featuring Processing, Visualization, and Analysis capabilities.

## Installation

```bash
# Install as part of the workspace
uv pip install -e pyama-pro/
```

## Running the Application

```bash
# Launch the Qt GUI
uv run pyama-pro

# Or run directly
uv run python pyama-pro/src/pyama_pro/main.py
```

## Architecture

PyAMA-Pro uses a simplified tab-based architecture without strict MVC separation:

### Main Components

- **ProcessingTab**: Data processing workflows and parameter tuning
- **AnalysisTab**: Analysis models and fitting (maturation, maturation-blocked, trivial models)
- **VisualizationTab**: Data visualization and plotting

### Component Classes

- **ParameterTable**: Table-based parameter editing widget
- **ParameterPanel**: Parameter visualization and analysis widget
- **QualityPanel**: Fitting quality inspection with FOV-based trace pagination

## Features Overview

### Processing Tab
- Load ND2/CZI microscopy files
- Configure phase contrast and fluorescence channels
- Select features for extraction
- Run complete processing workflow (segmentation, tracking, extraction)
- Assign FOVs to samples for batch processing
- Merge results into sample-specific CSV files

### Visualization Tab
- Load and inspect processed results
- Navigate through time points and FOVs
- Display multiple channels simultaneously
- Trace inspection and quality control
- Mark traces as good/bad for analysis
- Export inspected CSV files

### Analysis Tab
- Load merged trace data
- Fit mathematical models to traces
- Review fitting quality metrics
- Analyze parameter distributions
- Export fitted results and plots

## Data Flow

```
ND2/CZI Files → Processing → Traces (CSV) → Visualization → QC → Analysis → Fitted Results
```

## Quick Start Guide

### 1. Process Your Data

1. Launch PyAMA-Pro
2. Click **Browse** to select your ND2 file
3. Configure phase contrast and fluorescence channels
4. Select features to extract
5. Choose output directory
6. Click **Start Complete Workflow**

### 2. Inspect and QC (Recommended)

1. Switch to **Visualization** tab
2. Click **Load Folder** - select processing output
3. Select FOV and channels to display
4. Review traces, mark problematic ones as "bad"
5. Click **Save Inspected CSV** to preserve QC decisions

### 3. Analyze Results

1. Switch to **Analysis** tab
2. Click **Load CSV** - select merged traces
3. Choose a model (e.g., maturation)
4. Click **Start Fitting**
5. Review results and parameter distributions

## Component Details

### Processing Workflow Parameters

**Manual Parameters:**
- `fov_start`: Starting FOV index
- `fov_end`: Ending FOV index
- `batch_size`: FOVs per processing batch
- `n_workers`: Number of parallel threads
- `background_weight`: Fluorescence background correction (0-1)

**Channel Configuration:**
- Phase contrast: Required for segmentation
- Fluorescence: Optional, multiple channels supported
- Features: Selected per channel type

### Visualization Modes

**Data Types Available:**
- Raw phase contrast (`pc_ch_X`)
- Segmentation masks (`seg_ch_X`)
- Labeled tracking (`seg_labeled_ch_X`)
- Fluorescence background (`fl_background_ch_X`)

**Quality Control Features:**
- Multi-select trace inspection
- Right-click to toggle quality
- Pagination for large datasets
- Visual overlays on images

### Analysis Models

**Available Models:**
- **Trivial**: Constant model for testing
- **Maturation**: Exponential rise to plateau
- **Maturation Blocked**: Exponential decay

**Parameter Analysis:**
- Histogram distributions
- Scatter plot correlations
- Good fit filtering (R² > 0.9)

## Advanced Features

### Background Workers

Long-running tasks use QObject workers in separate threads:
- Workflow execution
- ND2 file loading
- Fitting calculations
- Keep UI responsive during operations

### Signal/Slot Architecture

PyAMA-Pro uses Qt's signal-slot mechanism:
- Semantic signals for cross-tab communication
- `operation_started()` / `operation_finished(success, message)` pattern
- Worker threads emit data signals converted to UI updates

### One-Way Data Binding

To prevent circular dependencies:
- UI → Model binding only
- No automatic Model → UI synchronization
- Manual refresh when needed
- Cross-panel updates via signals

## File Formats

### Input Formats
- ND2 microscopy files
- CZI microscopy files

### Output Formats
- `processing_config.yaml`: Processing metadata
- `fov_XXX/`: Per-FOV result directories
- `*_traces.csv`: Per-FOV feature traces
- `*_merged.csv`: Sample-merged traces
- `*_inspected.csv`: Quality-filtered traces
- `*_fitted_*.csv`: Analysis results with parameters

## Performance Tips

### Memory Management
- Use appropriate batch sizes (2-4 FOVs typical)
- Monitor memory with large datasets
- Cancel workflows if system becomes unresponsive

### Processing Optimization
- Match `n_workers` to CPU cores
- Use SSD storage for temporary files
- Consider preprocessing large ND2 files

### UI Responsiveness
- All long operations use background threads
- Progress indicators for user feedback
- Non-blocking signal-slot communication

## Troubleshooting

### Common Issues

**"Failed to load file"**: Check ND2 file permissions and validity

**Workflow runs slowly**: Reduce batch_size or n_workers

**No cells detected**: Verify phase contrast channel selection

**Fitting fails**: Check data quality and parameter bounds

### Logging

Enable debug mode to see detailed logs:
```bash
uv run pyama-pro --debug
```

Log locations:
- Console output during operation
- Status bar messages for UI operations

## Integration with Other Tools

### PyAMA-Air
- Use PyAMA-Air for quick configuration
- Export configurations for PyAMA-Pro use
- Compatible CSV formats

### PyAMA-Core
- Direct import of core algorithms
- Plugin system integration
- API access for custom scripts

### External Tools
- CSV export for other analysis software
- YAML configs for workflow automation
- Python API for custom extensions

## Development Notes

- Built with PySide6 (Qt6 bindings)
- Uses UV workspace for dependency management
- Type hints throughout codebase
- Comprehensive test suite
- Follows PEP 8 style guidelines

## Keyboard Shortcuts

- **Ctrl+O**: Browse for files
- **Ctrl+S**: Save current work (where applicable)
- **Tab**: Navigate between UI elements
- **Enter**: Confirm dialogs and start actions
- **Esc**: Cancel operations and close dialogs

## Next Steps

- See the [User Guide](../user-guide/) for detailed step-by-step instructions
- Check [Processing Tab Guide](../user-guide/processing-tab.md) for workflow details
- Review [Analysis Tab Guide](../user-guide/analysis-tab.md) for model fitting
- Visit the [Reference](../reference/) section for technical details

PyAMA-Pro provides a complete solution for microscope image analysis from raw data to fitted parameters, with comprehensive tools for quality control and visual inspection at every stage.
