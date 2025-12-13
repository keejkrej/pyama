# PyAMA-Core

PyAMA-Core is the core processing library that provides the underlying algorithms, data models, and utilities for microscopy image analysis. It's designed to be imported and used by higher-level applications like PyAMA-Pro and PyAMA-Air.

## Installation

```bash
# Install pyama-core as part of the workspace
uv pip install -e pyama-core/
```

## Main Components

### I/O Utilities (`pyama_core.io`)

Load and work with microscopy data:

```python
from pyama_core.io import load_microscopy_file, MicroscopyMetadata

# Load microscopy file
_, metadata = load_microscopy_file("path/to/file.nd2")

# Access metadata
print(f"Number of FOVs: {metadata.n_fovs}")
print(f"Channels: {metadata.channel_names}")
print(f"Time points: {metadata.n_t}")
```

**Key Functions:**

- `load_microscopy_file()`: Load ND2 or CZI files
- `get_microscopy_frame()`: Extract single frames
- `get_microscopy_channel_stack()`: Get all frames for a channel
- `get_microscopy_time_stack()`: Get time series for specific position

### Processing Workflow (`pyama_core.processing.workflow`)

Run complete processing pipelines:

```python
from pyama_core.processing.workflow import run_complete_workflow
from pyama_core.types.processing import (
    ProcessingContext,
    ChannelSelection,
    Channels,
    ProcessingConfig,
)
from pathlib import Path

# Define channel selections
pc_selection = ChannelSelection(channel=0, features=["area", "aspect_ratio"])
fl_selection = ChannelSelection(channel=1, features=["intensity_total"])

channels = Channels(pc=pc_selection, fl=[fl_selection])

# Create processing config
config = ProcessingConfig(
    output_dir=Path("output"),
    channels=channels,
    params={"background_weight": 1.0},
)

# Run workflow
success = run_complete_workflow(
    metadata=metadata,
    config=config,
    fov_start=0,
    fov_end=metadata.n_fovs - 1,
    batch_size=2,
    n_workers=2,
)
```

**Workflow Steps:**

1. **Copying**: Extract frames from ND2 to NPY format
2. **Segmentation**: Cell segmentation using LOG-STD approach
3. **Correction**: Background estimation for fluorescence channels (correction applied during feature extraction)
4. **Tracking**: Cell tracking across time points using IoU
5. **Extraction**: Feature extraction and trace generation to CSV

### Merge Processing (`pyama_core.processing.merge`)

Combine CSV files from multiple samples:

```python
from pyama_core.processing.merge import run_merge

# Merge results
message = run_merge(
    sample_yaml=Path("samples.yaml"),
    output_dir=Path("output"),
    input_dir=Path("processed_fovs"),  # folder containing fov_000, fov_001, etc.
)
```

### Analysis (`pyama_core.analysis`)

Fit models to trace data:

```python
from pyama_core.analysis.fitting import fit_model
from pyama_core.analysis.models import get_model, list_models

# Get available models
print("Available models:", list_models())

# Get model and prepare parameters
model = get_model("maturation")
fixed_params = model.DEFAULT_FIXED
fit_params = model.DEFAULT_FIT

# Optionally customize fit parameters
# fit_params["ktl"].value = 1e3
# fit_params["ktl"].lb = 1.0
# fit_params["ktl"].ub = 5e8

# Fit a model
result = fit_model(
    model,
    t_data=time_array,
    y_data=intensity_array,
    fixed_params=fixed_params,
    fit_params=fit_params,
)

print(f"R²: {result.r_squared}")
print(f"Parameters:")
for param_name, param in result.fitted_params.items():
    print(f"  {param_name}: {param.value}")
```

**Available Models:**

- `trivial`: Constant model
- `maturation`: Exponential maturation model
- `maturation_blocked`: Blocked maturation model

### Feature Extraction (`pyama_core.processing.extraction.features`)

Extract features from images:

```python
from pyama_core.processing.extraction.features import (
    list_phase_features,
    list_fluorescence_features,
)

# Get available features
pc_features = list_phase_features()  # ['area', 'aspect_ratio']
fl_features = list_fluorescence_features()  # ['intensity_total']
```

**Built-in Features:**

- **Phase contrast**: `area`, `aspect_ratio`
- **Fluorescence**: `intensity_total`

## Key Data Structures

### MicroscopyMetadata

Metadata container for microscopy files:

```python
from pyama_core.io import MicroscopyMetadata

metadata: MicroscopyMetadata
metadata.n_fovs      # Number of fields of view
metadata.n_t         # Number of time points
metadata.n_channels  # Number of channels
metadata.channel_names  # List of channel names
metadata.shape       # Image shape (height, width)
```

### ProcessingConfig

Configuration for workflow execution:

```python
from pyama_core.types.processing import ProcessingConfig

config = ProcessingConfig(
    output_dir=Path("output"),
    channels=Channels(...),
    params={"background_weight": 1.0},  # Background correction weight [0, 1]
)
```

### ChannelSelection

Define channel and feature combinations:

```python
from pyama_core.types.processing import ChannelSelection

# Phase contrast selection
pc = ChannelSelection(channel=0, features=["area", "aspect_ratio"])

# Fluorescence selection
fl = ChannelSelection(channel=1, features=["intensity_total"])
```

## Extending PyAMA-Core

### Adding Custom Features

Create a new feature file in `pyama_core/processing/extraction/features/`:

```python
from pyama_core.processing.extraction.features import FeatureExtractor

@FeatureExtractor("my_feature")
def extract_my_feature(image, mask, context):
    """Extract custom feature from image and mask."""
    # Your extraction logic here
    return feature_value
```

Or manually create:

```python
"""My custom feature extraction."""

import numpy as np

from pyama_core.types.processing import ExtractionContext


def extract_my_feature(ctx: ExtractionContext) -> np.float32:
    """Extract my custom feature for a single cell."""
    mask = ctx.mask.astype(bool, copy=False)
    return np.sum(mask) * 2.0  # Example: double the area
```

Then register in `__init__.py`:

```python
from pyama_core.processing.extraction.features import my_feature

# For phase features (operate on masks)
PHASE_FEATURES["my_feature"] = my_feature.extract_my_feature

# OR for fluorescence features (operate on intensity images)
FLUORESCENCE_FEATURES["my_feature"] = my_feature.extract_my_feature
```

### Adding Custom Models

Create a new model file in `pyama_core/analysis/models/`:

```python
"""My custom analysis model."""

import numpy as np
from typing import Dict, Any

from pyama_core.analysis.models.base import BaseModel

# Model metadata (required for auto-discovery)
MODEL_NAME = "my_model"


class MyModel(BaseModel):
    """My custom analysis model."""
    
    def fit(self, data: np.ndarray, **kwargs) -> Dict[str, Any]:
        """Fit the model to data."""
        # Implement your fitting logic
        return {"status": "success", "parameters": {}}
    
    def predict(self, data: np.ndarray, **kwargs) -> np.ndarray:
        """Make predictions using the fitted model."""
        # Implement your prediction logic
        return np.zeros_like(data)
```

Models are automatically discovered when the module is imported.

## API Reference

### Workflow Functions

- `run_complete_workflow()`: Execute full processing pipeline
- `ensure_config()`: Validate and normalize processing config

### I/O Functions

- `load_microscopy_file()`: Load microscopy metadata
- `get_microscopy_frame()`: Extract single frame
- `load_config()`: Load processing config from YAML file
- `discover_fovs()`: Discover FOV directories in output folder

### Analysis Functions

- `fit_model()`: Fit analysis model to data
- `get_model()`: Get model instance by name
- `list_models()`: List available models

### Merge Functions

- `run_merge()`: Merge CSV files from multiple samples
- `parse_fov_range()`: Parse FOV range strings
- `read_samples_yaml()`: Load sample configuration

## Tips

- **Direct Import**: Import specific functions you need; avoid `import *`
- **Path Objects**: Use `pathlib.Path` for all file paths
- **Type Hints**: Check type hints in function signatures for parameter types
- **Context Managers**: Use existing context structures rather than creating custom ones
- **Extension Points**: Leverage plugin system for features and models
- **Error Handling**: Check return values and catch exceptions appropriately

## Examples

See the tests directory for working examples:

- `tests/test_workflow.py`: End-to-end workflow execution
- `tests/test_merge.py`: Merge operations
- `tests/test_results_yaml.py`: Results file handling

## Integration

PyAMA-Core is designed to be:

- **Importable**: Use in Python scripts and notebooks
- **Extensible**: Add custom features and models via plugins
- **Testable**: Comprehensive test suite included
- **Documented**: Type hints and docstrings throughout

For applications built on top of PyAMA-Core:

- **PyAMA-Pro**: Full-featured Qt GUI with comprehensive visualization and analysis tools
- **PyAMA-Air**: Guided workflow wizards (both CLI and GUI) for quick configuration and execution
