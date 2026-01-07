# PyAMA-ACDC

PyAMA-ACDC is a Cell-ACDC integration plugin that exposes PyAMA workflow helpers inside Cell-ACDC's Qt welcome window, allowing seamless access to PyAMA's advanced analysis capabilities from within the Cell-ACDC environment.

## Purpose

The plugin enables Cell-ACDC users to:
- Access PyAMA workflows from Cell-ACDC's interface
- Run PyAMA's advanced segmentation and tracking
- Transition smoothly between Cell-ACDC and PyAMA analysis
- Use PyAMA as an option in Cell-ACDC's modular system

## Installation

```bash
# Install as part of the PyAMA workspace
uv pip install -e pyama-acdc/

# For standalone installation (in Cell-ACDC environment)
pip install pyama-acdc
```

## Architecture

The plugin exposes a minimal API designed to integrate with Cell-ACDC's plugin system:

```python
from pyama_acdc import pyAMA_Win

# Main integration point - PyAMA window that can be launched from Cell-ACDC
class pyAMA_Win(QWidget):
    """Main PyAMA workflow window for Cell-ACDC integration."""
```

## Usage in Cell-ACDC

### Basic Integration

```python
# In Cell-ACDC's main window
from pyama_acdc import pyAMA_Win

class mainWin(QMainWindow):
    def showPyamaWorkflow(self):
        """Launch PyAMA workflow from Cell-ACDC."""
        win = pyAMA_Win(self)
        win.show()
```

### Advanced Integration

```python
# Direct API access
from pyama_acdc._run import run_gui, icon_path, logo_path

# Get assets for Cell-ACDC launcher
icon = icon_path()
logo = logo_path()

# Launch with configuration
run_gui(parent=cell_acdc_window, config_path="path/to/config.yaml")
```

## Workflow Integration

### PyAMA Workflow Steps in Cell-ACDC Context

The integrated workflow follows a Cell-ACDC-friendly sequence:

1. **Step 0** - Cell-ACDC's native "Create data structure" dialog
   - Initializes experiment folders
   - Sets up standard Cell-ACDC directory structure

2. **Step 1** - PyAMA segmentation module
   - Runs LOG-STD segmentation immediately after structuring
   - Creates tracked cell IDs
   - Exports CSV traces

3. **Step 2** - PyAMA data prep module
   - Handles background correction
   - Applies quality filters
   - Prepares for analysis

4. **Step 3** - PyAMA analysis GUI
   - Model fitting interface
   - Parameter analysis
   - Export capabilities

### File Integration

```
cell_acdc_experiment/
├── Images/              # Cell-ACDC images
├── pyama/               # PyAMA outputs
│   ├── processing_config.yaml
│   ├── fov_XXX/
│   └── *_traces.csv
└── analysis/            # Combined analysis outputs
```

## Configuration

### Cell-ACDC Plugin Registration

The plugin registers with Cell-ACDC's system by exposing:

```python
# Required for Cell-ACDC discovery
MODULE_NAME = "PyAMA Analysis"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Advanced microscopy analysis workflow"
```

### Integration Points

```python
# pyama_acdc/__init__.py

# Entry points for Cell-ACDC
icon_path: str  # Path to PyAMA icon
logo_path: str  # Path to PyAMA logo
run_gui: Callable # Launch PyAMA GUI

# Configuration
def get_config():
    """Return configuration for Cell-ACDC integration."""
    return {
        "workflow_type": "pyama",
        "compatible_versions": ["1.0.0"],
        "requires_nd2": True,
        "supports_tracking": True
    }
```

## API Reference

### Main Classes

```python
class pyAMA_Win(QWidget):
    """Main PyAMA window launched from Cell-ACDC."""
    
    def __init__(self, parent=None):
        """Initialize with optional Cell-ACDC parent window."""
        
    def load_from_cell_acdc(self, exp_path):
        """Load Cell-ACDC experiment data."""
        
    def export_to_cell_acdc_format(self):
        """Export results to Cell-ACDC compatible format."""
```

### Utility Functions

```python
def run_gui(parent=None, config_path=None):
    """Launch PyAMA GUI with optional configuration."""
    
def get_available_workflows():
    """Return list of PyAMA workflows compatible with Cell-ACDC."""
    
def validate_cell_acdc_structure(path):
    """Check if path follows Cell-ACDC structure."""
```

## Migration Path

### From Cell-ACDC to PyAMA

1. **Data Structure**:
   - Cell-ACDC organizes: `Images/Position_X/Time_Y/`
   - PyAMA uses: Single ND2 with FOV metadata
   - Plugin handles conversion automatically

2. **Segmentation**:
   - Cell-ACDC: Manual or basic algorithms
   - PyAMA: LOG-STD with IoU tracking
   - Plugin imports Cell-ACDC masks if available

3. **Analysis**:
   - Cell-ACDC: Basic measurements
   - PyAMA: Advanced model fitting
   - Plugin exports results to both formats

### Hybrid Workflows

```python
# Use Cell-ACDC for initial processing
cell_acdc.segmentation.run(image_path)

# Continue with PyAMA analysis
pyama_Win.load_from_cell_acdc(exp_path)
pyama_Win.run_analysis()
```

## Examples

### Basic Usage Example

```python
from pyama_acdc import pyAMA_Win
from cell_acdc import main as cell_acdc

# In Cell-ACDC application
def launch_pyama_analysis():
    # Get current experiment
    exp_path = cell_acdc.get_current_experiment()
    
    # Launch PyAMA
    pyama_window = pyAMA_Win(parent=cell_acdc.main_window)
    pyama_window.load_from_cell_acdc(exp_path)
    pyama_window.show()
```

### Data Integration Example

```python
# Analyze Cell-ACDC data with PyAMA
def analyze_with_pyama(cell_acdc_path):
    from pyama_acdc.helpers import convert_cell_acdc_to_pyama
    
    # Convert data structure
    pyama_path = convert_cell_acdc_to_pyama(cell_acdc_path)
    
    # Run PyAMA analysis
    from pyama_core.processing.analysis import run_complete_analysis
    results = run_complete_analysis(pyama_path)
    
    # Export back to Cell-ACDC format
    from pyama_acdc.export import to_cell_acdc_format
    to_cell_acdc_format(results, cell_acdc_path)
```

## Development

### Building the Plugin

```bash
# Install in development mode
uv pip install -e pyama-acdc/

# Test integration with Cell-ACDC
python -c "from pyama_acdc import pyAMA_Win; print('Plugin works')"
```

### Testing Integration

```python
# tests/test_integration.py
def test_cell_acdc_integration():
    """Test that plugin integrates correctly with Cell-ACDC."""
    from pyama_acdc import pyAMA_Win
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication([])
    window = pyAMA_Win()
    assert window.windowTitle() == "PyAMA Workflow"
```

### Debug Mode

```python
# Enable debug logging
import pyama_acdc
pyama_acdc.set_debug_level("DEBUG")

# Check Cell-ACDC compatibility
from pyama_acdc.compatibility import check_cell_acdc_version
check_cell_acdc_version()
```

## Troubleshooting

### Common Issues

**"Plugin not found in Cell-ACDC":**
- Ensure pyama-acdc is in Python path
- Check Cell-ACDC plugin directory configuration
- Verify PyQt6 dependencies

**"Data conversion failed":**
- Check Cell-ACDC data structure
- Verify image formats are supported
- Ensure sufficient disk space

**"Window won't open":**
- Check Qt application initialization
- Verify parent window is valid
- Check for Qt version conflicts

### Debug Information

```python
# Get diagnostic information
from pyama_acdc.diagnostics import get_system_info
info = get_system_info()
print(info)

# Check compatibility
from pyama_acdc.compatibility import CompatibilityReport
report = CompatibilityReport()
print(report.summary())
```

## Best Practices

### Data Organization

1. Keep Cell-ACDC and PyAMA outputs separate
2. Use consistent naming conventions
3. Document conversion steps
4. maintain both formats when possible

### Workflow Integration

1. Start with Cell-ACDC for initial data organization
2. Use PyAMA for advanced analysis
3. Export results back to Cell-ACDC if needed
4. Keep track of data provenance

### Performance

1. Preprocess data in Cell-ACDC when beneficial
2. Use PyAMA's optimized algorithms for large datasets
3. Cache conversion results
4. Monitor memory usage during conversions

## Future Enhancements

- Direct data synchronization between Cell-ACDC and PyAMA
- Shared parameter configurations
- Unified analysis dashboard
- Export to additional formats (Fiji, ImageJ)
- Batch processing across multiple experiments

## Resources

- Cell-ACDC documentation: https://github.com/pycellacdc/pycellacdc
- PyAMA user guide: [User Guide](../user-guide/)
- Integration examples in `examples/` directory
- Test data for development in `tests/test_data/`

PyAMA-ACDC bridges the gap between Cell-ACDC's user-friendly interface and PyAMA's advanced analytical capabilities, providing a seamless experience for microscopy image analysis workflows.
