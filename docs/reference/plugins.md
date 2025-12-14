# Plugin System

PyAMA supports extensible plugins for custom feature extraction and analysis models. This guide covers creating, installing, and managing plugins.

## Overview

PyAMA uses two separate plugin systems:

1. **Feature Plugins** - Add custom feature extraction algorithms
2. **Model Plugins** - Add custom analysis fitting models
3. **GUI Installation** - Install plugins through the PyAMA-Qt interface

## Plugin Directory Structure

Plugins are organized in `~/.pyama/plugins/` by type:

```
~/.pyama/plugins/
├── features/
│   ├── phase_contrast/          # Phase contrast features
│   │   └── circularity.py       # Measure cell roundness
│   └── fluorescence/             # Fluorescence features
│       └── intensity_variance.py # Measure signal heterogeneity
└── fitting/                      # Analysis/fitting models
    └── exponential_decay.py      # Example decay model
```

The scanner recursively searches all subdirectories, so you can organize plugins however you prefer.

## Example Plugins

Example plugins are included in the `examples/plugins/` directory.

### Available Examples

- **`features/phase_contrast/circularity.py`** - Phase contrast feature measuring cell roundness
- **`features/fluorescence/intensity_variance.py`** - Fluorescence feature measuring signal heterogeneity  
- **`fitting/exponential_decay.py`** - Exponential decay model for time-series fitting

## Feature Plugins

### Creating a Phase Contrast Feature

**File structure:** `~/.pyama/plugins/features/phase_contrast/my_feature.py`

```python
"""Custom phase contrast feature extraction."""

import numpy as np
from typing import Dict, Any

from pyama_core.types.processing import ExtractionContext


def extract_my_feature(ctx: ExtractionContext) -> np.float32:
    """
    Extract my custom feature from a cell mask.
    
    Args:
        ctx: Extraction context containing cell mask
        
    Returns:
        Feature value as float32
    """
    mask = ctx.mask.astype(bool, copy=False)
    
    # Your feature extraction logic here
    # Example: Calculate circularity of the cell
    from skimage.measure import regionprops
    
    # Convert to labeled image for regionprops
    labeled = mask.astype(int)
    props = regionprops(labeled)[0]
    
    # Circularity = 4π × Area / Perimeter²
    area = props.area
    perimeter = props.perimeter
    
    if perimeter > 0:
        circularity = 4 * np.pi * area / (perimeter ** 2)
    else:
        circularity = 0.0
    
    return np.float32(circularity)


# Optional: Add metadata for GUI display
FEATURE_METADATA = {
    "name": "My Circularity Feature",
    "description": "Measures how circular the cell is (1.0 = perfect circle)",
    "units": "ratio",
    "range": [0.0, 1.0],
    "category": "morphology"
}
```

### Creating a Fluorescence Feature

**File structure:** `~/.pyama/plugins/features/fluorescence/my_fl_feature.py`

```python
"""Custom fluorescence feature extraction."""

import numpy as np
from scipy import ndimage

from pyama_core.types.processing import ExtractionContext


def extract_texture_entropy(ctx: ExtractionContext) -> np.float32:
    """
    Extract texture entropy from fluorescence intensity.
    
    Measures the texture complexity of fluorescence signal.
    
    Args:
        ctx: Extraction context with intensity image and mask
        
    Returns:
        Shannon entropy of intensity distribution
    """
    image = ctx.image
    mask = ctx.mask.astype(bool, copy=False)
    
    # Extract pixel values within the cell
    cell_pixels = image[mask]
    
    # Calculate histogram
    hist, _ = np.histogram(cell_pixels, bins=16, density=True)
    
    # Calculate Shannon entropy
    # Remove zeros to avoid log(0)
    hist = hist[hist > 0]
    entropy = -np.sum(hist * np.log2(hist))
    
    return np.float32(entropy)


# Optional metadata
FEATURE_METADATA = {
    "name": "Texture Entropy",
    "description": "Measures texture complexity using Shannon entropy",
    "units": "bits",
    "range": [0.0, 4.0],
    "category": "texture"
}
```

## Model Plugins

### Creating a Custom Analysis Model

**File structure:** `~/.pyama/plugins/fitting/my_model.py`

```python
"""Custom exponential decay model with lag phase."""

import numpy as np
from typing import Dict, Any

from pyama_core.analysis.models.base import BaseModel

# Required metadata for auto-discovery
MODEL_NAME = "decay_with_lag"


class DecayWithLagModel(BaseModel):
    """
    Exponential decay with initial lag phase.
    
    Model: f(t) = {
        A,                   for t <= t_lag
        A * exp(-k*(t-t_lag)), for t > t_lag
    }
    
    Parameters:
    - A: Initial amplitude
    - k: Decay rate constant
    - t_lag: Lag time before decay begins
    """
    
    def __init__(self):
        super().__init__()
        self.DEFAULT_FIXED = {}
        self.DEFAULT_FIT = {
            "amplitude": {"value": 1.0, "lb": 0.01, "ub": 10.0},
            "rate": {"value": 0.1, "lb": 0.001, "ub": 1.0},
            "lag_time": {"value": 5.0, "lb": 0.0, "ub": 50.0}
        }
    
    def fit(self, t_data: np.ndarray, y_data: np.ndarray, **kwargs) -> Dict[str, Any]:
        """Fit model to data using non-linear least squares."""
        from scipy.optimize import curve_fit
        
        # Initial guesses
        p0 = [1.0, 0.1, 5.0]  # [A, k, t_lag]
        bounds = ([0.01, 0.001, 0.0], [10.0, 1.0, 50.0])
        
        try:
            # Fit the model
            popt, pcov = curve_fit(
                self.predict,
                t_data,
                y_data,
                p0=p0,
                bounds=bounds
            )
            
            # Calculate R²
            y_pred = self.predict(t_data, *popt)
            ss_res = np.sum((y_data - y_pred) ** 2)
            ss_tot = np.sum((y_data - np.mean(y_data)) ** 2)
            r_squared = 1 - (ss_res / ss_tot)
            
            return {
                "success": True,
                "parameters": {
                    "amplitude": popt[0],
                    "rate": popt[1],
                    "lag_time": popt[2]
                },
                "covariance": pcov,
                "r_squared": r_squared
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "parameters": {k: v["value"] for k, v in self.DEFAULT_FIT.items()},
                "r_squared": 0.0
            }
    
    def predict(self, t_data: np.ndarray, amplitude: float, rate: float, 
                lag_time: float, **kwargs) -> np.ndarray:
        """Generate predictions from model parameters."""
        result = np.zeros_like(t_data)
        
        # Constant phase (before lag)
        mask = t_data <= lag_time
        result[mask] = amplitude
        
        # Decay phase (after lag)
        mask = t_data > lag_time
        result[mask] = amplitude * np.exp(-rate * (t_data[mask] - lag_time))
        
        return result


# Optional metadata for GUI
MODEL_METADATA = {
    "name": "Decay with Lag",
    "description": "Exponential decay with initial lag phase",
    "equation": "f(t) = A for t <= t_lag; f(t) = A * exp(-k*(t-t_lag)) for t > t_lag",
    "parameters": [
        {
            "name": "amplitude",
            "symbol": "A",
            "description": "Initial signal amplitude",
            "unit": "arbitrary"
        },
        {
            "name": "rate", 
            "symbol": "k",
            "description": "Decay rate constant",
            "unit": "1/time"
        },
        {
            "name": "lag_time",
            "symbol": "t_lag", 
            "description": "Time before decay begins",
            "unit": "time"
        }
    ]
}
```

## Installation Methods

### Method 1: GUI Installation (Recommended)

1. Launch PyAMA-Qt: `uv run pyama-qt`
2. Click **File → Install Plugin...**
3. Select a `.py` plugin file
4. Plugin is:
   - Validated for syntax errors
   - Automatically placed in correct directory
   - Immediately available for use

### Method 2: Manual Installation

```bash
# Create directory structure
mkdir -p ~/.pyama/plugins/features/phase_contrast
mkdir -p ~/.pyama/plugins/features/fluorescence
mkdir -p ~/.pyama/plugins/fitting

# Copy phase contrast features
cp examples/plugins/features/phase_contrast/*.py ~/.pyama/plugins/features/phase_contrast/

# Copy fluorescence features
cp examples/plugins/features/fluorescence/*.py ~/.pyama/plugins/features/fluorescence/

# Copy fitting models
cp examples/plugins/fitting/*.py ~/.pyama/plugins/fitting/

# Restart PyAMA-Qt to load new plugins
```

### Method 3: Batch Installation Script

```bash
#!/bin/bash
# install_plugins.sh

PLUGIN_DIR="$HOME/.pyama/plugins"
EXAMPLE_DIR="examples/plugins"

# Create directories
mkdir -p "$PLUGIN_DIR/features/phase_contrast"
mkdir -p "$PLUGIN_DIR/features/fluorescence" 
mkdir -p "$PLUGIN_DIR/fitting"

# Install all example plugins
cp -r "$EXAMPLE_DIR/features/"* "$PLUGIN_DIR/features/"
cp -r "$EXAMPLE_DIR/fitting/"* "$PLUGIN_DIR/fitting/"

echo "Plugins installed to: $PLUGIN_DIR"
echo "Restart PyAMA-Qt to use new plugins"
```

## Using Plugins

### Feature Plugins

Features automatically appear in the GUI:

1. In **Processing** tab, feature lists include:
   - Built-in features (area, aspect_ratio, intensity_total)
   - Your custom features
   
2. Features are grouped by type:
   - **Phase Contrast**: Features operating on masks
   - **Fluorescence**: Features operating on intensity images

3. Features with metadata show:
   - Description tooltips
   - Unit displays
   - Expected value ranges

### Model Plugins

Models appear in the **Analysis** tab:

1. Model dropdown includes:
   - Built-in models (trivial, maturation, maturation_blocked)
   - Your custom models

2. Parameter table shows:
   - Parameter names and descriptions
   - Default values and bounds
   - Units when specified

## Plugin Development Guidelines

### General Practices

1. **Follow Naming Conventions**:
   - File names: `lowercase_with_underscores.py`
   - Function names: `extract_feature_name`
   - Models: PascalCase class names

2. **Include Documentation**:
   - Docstrings for all functions
   - Parameter descriptions
   - Usage examples

3. **Handle Errors Gracefully**:
   - Return default values on failure
   - Log warnings for edge cases
   - Validate inputs

### Feature Development

```python
def extract_my_feature(ctx: ExtractionContext) -> np.float32:
    """Extract custom feature with error handling."""
    try:
        mask = ctx.mask.astype(bool, copy=False)
        
        # Validate input
        if not np.any(mask):
            return np.float32(0.0)
        
        # Extract feature
        value = complex_calculation(mask)
        
        # Validate output
        if np.isnan(value) or np.isinf(value):
            return np.float32(0.0)
        
        return np.float32(value)
        
    except Exception:
        # Log error and return default
        return np.float32(0.0)
```

### Model Development

```python
class MyModel(BaseModel):
    def fit(self, t_data, y_data, **kwargs):
        """Robust fitting with error handling."""
        try:
            # Validate data
            if len(t_data) < 5:
                return self._failed_result("Insufficient data points")
            
            if np.std(y_data) < 1e-6:
                return self._failed_result("Data has no variance")
            
            # Perform fitting
            # ... fitting logic ...
            
        except Exception as e:
            return self._failed_result(f"Fitting failed: {str(e)}")
    
    def _failed_result(self, error_msg):
        """Helper for consistent error results."""
        return {
            "success": False,
            "error": error_msg,
            "parameters": {k: v["value"] for k, v in self.DEFAULT_FIT.items()},
            "r_squared": 0.0
        }
```

## Testing Plugins

### Local Testing

```python
# test_my_feature.py
import numpy as np
from pyama_core.types.processing import ExtractionContext

# Create test context
def create_test_context():
    context = ExtractionContext()
    context.mask = np.zeros((100, 100), dtype=bool)
    context.mask[40:60, 40:60] = True  # Square in center
    context.image = np.random.random((100, 100)) * 100
    return context

# Test feature
ctx = create_test_context()
feature_value = extract_my_feature(ctx)
print(f"Feature value: {feature_value}")
```

### GUI Testing Workflow

1. **Install Plugin**: Use File → Install Plugin...
2. **Test with Simple Data**:
   - Process single FOV
   - Check plugin results in output CSV
   - Verify values are reasonable

3. **Test Edge Cases**:
   - Empty cells
   - Very large cells
   - Low signal fluorescence

### Integration Testing

```python
# test_plugin_integration.py
from pyama_core.processing.workflow import run_complete_workflow

# Run workflow with custom feature
config = ProcessingConfig(
    output_dir="test_output",
    channels=Channels(
        pc=ChannelSelection(channel=0, features=["area", "my_feature"]),
        fl=[]
    ),
    params={}
)

# Run single FOV for quick test
success = run_complete_workflow(
    metadata=test_metadata,
    config=config,
    fov_start=0,
    fov_end=0,  # Single FOV
    batch_size=1,
    n_workers=1
)

# Check output
import pandas as pd
df = pd.read_csv("test_output/fov_000/test_fov_000_traces.csv")
assert "my_feature_ch_0" in df.columns
```

## troubleshooting

### Common Issues

**"Plugin Not Appearing":**
- Check file location matches expected structure
- Verify Python syntax is correct
- Restart PyAMA-Qt
- Check console for error messages

**"Import Error":**
- Ensure all dependencies are installed
- Check import paths are correct
- Use absolute imports when needed

**"Feature Returns NaN":**
- Add error handling in feature function
- Check for empty masks
- Validate calculation parameters

**"Model Fitting Fails":**
- Verify initial parameter values
- Check parameter bounds are reasonable
- Add fallback for failed fits

### Debugging Tips

1. **Enable Debug Mode**:
   ```bash
   uv run pyama-qt --debug
   ```

2. **Check Plugin Loading**:
   ```python
   # In PyAMA-Qt Python console
   from pyama_core.processing.extraction.features import list_features
   print(list_features())
   ```

3. **Test in Isolation**:
   ```python
   # Import directly
   import sys
   sys.path.append("~/.pyama/plugins/features/phase_contrast")
   import my_feature
   print(my_feature.extract_my_feature(test_context))
   ```

## Best Practices

### Performance

- Use vectorized NumPy operations
- Avoid loops over pixels when possible
- Cache expensive calculations

### Compatibility

- Test with different Python versions
- Handle different image resolutions
- Support both uint16 and float32 data

### Documentation

- Include parameter ranges
- Provide example outputs
- Document assumptions

### Distribution

- Include usage examples
- Create README for plugin
- Consider versioning for breaking changes

The plugin system enables PyAMA to be extended for specific research needs while maintaining a clean, modular architecture.
