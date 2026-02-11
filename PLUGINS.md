# Plugin Systems

PyAMA supports explicit feature registration for extraction and model plugins for analysis.

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

The scanner **recursively** searches all subdirectories, so you can organize plugins however you prefer.

## Example Plugins

Example plugins are included in the `examples/plugins/` directory using this same structure:

- **`features/phase_contrast/circularity.py`** - Phase contrast feature measuring cell roundness
- **`features/fluorescence/intensity_variance.py`** - Fluorescence feature measuring signal heterogeneity
- **`fitting/exponential_decay.py`** - Example exponential decay model for time-series fitting

To use example plugins, choose one of these methods:

### Method 1: GUI Installation (Recommended)

1. Launch PyAMA-Pro: `uv run pyama-pro`
2. Click **File → Install Plugin...**
3. Select a `.py` plugin file
4. Plugin is validated, installed, and automatically reloaded

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

# Restart PyAMA-Pro
uv run pyama-pro
```

Or customize the example plugins as templates for your own plugins. The GUI installer automatically places plugins in the correct subdirectory based on their type.

## Feature Registration System

The extraction features module uses explicit registration. To add a new feature, create a Python file in `pyama-core/src/pyama_core/processing/extraction/features/` and register it in `__init__.py`.

## Creating a New Feature

### Quick Start

Copy an example feature (e.g. `aspect_ratio.py` from `examples/plugins/features/phase_contrast/`) and modify it:

```bash
cp examples/plugins/features/phase_contrast/aspect_ratio.py \
   pyama-core/src/pyama_core/processing/extraction/features/my_feature.py
```

Edit the file to implement your `extract_*` function, then register it in `__init__.py`:

### Manual Creation

Create a new file: `my_feature.py`

```python
"""My custom feature extraction."""

import numpy as np

from pyama_core.types.processing import ExtractionContext


def extract_my_feature(ctx: ExtractionContext) -> np.float32:
    """Extract my custom feature for a single cell."""
    mask = ctx.mask.astype(bool, copy=False)
    return np.sum(mask) * 2.0  # Example: double the area
```

### 2. Register the Feature

Add the feature to `__init__.py`:

```python
from pyama_core.processing.extraction.features import my_feature

# For phase features (operate on masks)
PHASE_FEATURES["my_feature"] = my_feature.extract_my_feature

# OR for fluorescence features (operate on intensity images)
FLUORESCENCE_FEATURES["my_feature"] = my_feature.extract_my_feature
```

### 3. Required Components

Each feature module must have:

- **extract_{feature_name}()** function: The extractor function that takes an `ExtractionContext` and returns a numeric value
- **Registration in `__init__.py`**: Add to either `PHASE_FEATURES` or `FLUORESCENCE_FEATURES` dictionary

### 4. Feature Type Guidelines

**Phase Features** (registered in `PHASE_FEATURES`):

- Operate on segmentation masks derived from phase contrast images
- Use `ctx.mask` to access the cell mask
- Examples: `area`, `aspect_ratio`

**Fluorescence Features** (registered in `FLUORESCENCE_FEATURES`):

- Operate on intensity images from fluorescence channels
- Use `ctx.image` to access the intensity data
- Examples: `intensity_total`

### 5. Testing Your Feature

```python
from pyama_core.processing.extraction.features import (
    list_features,
    list_phase_features,
    list_fluorescence_features,
    get_feature_extractor,
)

# Check if your feature is registered
print(list_features())  # Should include "my_feature"
print(list_phase_features())  # If registered in PHASE_FEATURES
print(list_fluorescence_features())  # If registered in FLUORESCENCE_FEATURES

# Get the extractor function
extractor = get_feature_extractor("my_feature")
```

**Note**: After creating your feature file, you must restart the application or reload the module for the registration in `__init__.py` to take effect.

## ExtractionContext

The `ExtractionContext` dataclass contains the data needed for feature extraction:

```python
@dataclass
class ExtractionContext:
    image: np.ndarray      # 2D intensity image (for fluorescence features)
    mask: np.ndarray       # 2D binary mask of the cell (for phase features)
```

- **image**: 2D numpy array of pixel intensities (used by fluorescence features)
- **mask**: 2D numpy array with non-zero values for pixels belonging to the cell (used by phase features)

## Model Plugin System

The analysis models module uses an automatic plugin discovery system. To add a new model, create a Python file in `pyama-core/src/pyama_core/analysis/models/` with the required metadata.

### Creating a New Model

#### Model Quick Start

Copy `exponential_decay.py` (the example model) and modify it:

```bash
cp examples/plugins/fitting/exponential_decay.py \
   pyama-core/src/pyama_core/analysis/models/my_model.py
```

Edit the file:

- Add your model to `MODELS` in `pyama_core/analysis/models/__init__.py`, or use `register_plugin_model()` at runtime
- Implement `Params`, `Bounds`, `DEFAULTS`, `BOUNDS`, and `eval`

#### Model Required Components

Each model module must have:

- **Params** (dataclass): Parameter container
- **Bounds** (dataclass): Bounds for each parameter
- **DEFAULTS**: Default parameter values
- **BOUNDS**: Default bounds
- **eval(t, params)**: Function that evaluates the model

See `maturation.py` and `examples/plugins/fitting/exponential_decay.py` for the full interface.

### Testing Your Model

```python
from pyama_core.analysis.models import (
    list_models,
    get_model,
)

# Check if your model is registered
print(list_models())  # Should include "my_model"

# Get the model module
model_module = get_model("my_model")
```
