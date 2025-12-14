# Contributing to PyAMA

This guide covers contributing to PyAMA, including coding guidelines, development workflow, and contribution process.

## Development Environment

### Prerequisites

- Python 3.11+ 
- UV package manager
- Git
- Code editor (VS Code recommended with Python extension)

### Setup

1. **Clone the Repository**
   ```bash
   git clone https://github.com/your-org/pyama.git
   cd pyama
   ```

2. **Install Dependencies**
   ```bash
   uv sync --all-extras
   ```

3. **Install in Development Mode**
   ```bash
   uv pip install -e pyama-core/
   uv pip install -e pyama-qt/
   ```

4. **Verify Installation**
   ```bash
   uv run pyama-qt --version
   uv run pytest tests/
   ```

### Recommended VS Code Extensions

- Python
- Pylance
- Python Docstring Generator
- GitLens
- EditorConfig

## Coding Guidelines

### Style Guide

PyAMA follows PEP 8 with additional conventions:

```python
# Use snake_case for variables and functions
def process_cell_data(input_data: np.ndarray) -> Dict[str, float]:
    """Process cell data and return metrics.
    
    Args:
        input_data: Array of cell measurements
        
    Returns:
        Dictionary with calculated metrics
    """
    return {"mean": np.mean(input_data), "std": np.std(input_data)}


# Use PascalCase for classes
class CellProcessor:
    """Handles processing of cell data."""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        
    def process(self, data: CellData) -> ProcessedData:
        """Process cell data according to configuration."""
        return ProcessedData(data, self.config)


# Use UPPER_CASE for constants
DEFAULT_MIN_CELL_SIZE = 50
MAX_WORKERS = 8
```

### Type Hints

Use built-in generics and union types:

```python
# Preferred
def load_config(path: Path) -> Dict[str, Any]:
    """Load configuration from file."""
    return {}
    
def process_data(
    items: List[str],
    options: Optional[Dict] = None
) -> Tuple[List[str],]:
    """Process items with optional options."""
    pass

# Avoid
from typing import Dict, List, Tuple, Optional
def load_config(path: 'Dict[str, str]'):
    pass
```

### Import Organization

All imports at the top of the file:

```python
# Standard library
import os
from pathlib import Path
from typing import Any, Dict, List

# Third-party
import numpy as np
from PySide6.QtWidgets import QWidget
from scipy import ndimage

# Local imports
from pyama_core.types.processing import ProcessingContext
from pyama_core.utils import validate_config
```

### Docstring Format

Use Google-style docstrings:

```python
def segment_cells(
    image: np.ndarray,
    method: str = "logstd",
    parameters: Optional[Dict[str, Any]] = None
) -> np.ndarray:
    """Segment cells in microscopy image.
    
    Args:
        image: Input microscopy image (2D array)
        method: Segmentation method to use ('logstd', 'threshold')
        parameters: Optional method-specific parameters
        
    Returns:
        Binary mask where True indicates cell pixels
        
    Raises:
        ValueError: If method is not supported
        ValueError: If image is not 2D
        
    Example:
        >>> image = np.random.random((100, 100))
        >>> mask = segment_cells(image, method="threshold")
        >>> print(mask.shape)
        (100, 100)
    """
    if image.ndim != 2:
        raise ValueError("Image must be 2D")
    
    if method not in ["logstd", "threshold"]:
        raise ValueError(f"Method {method} not supported")
    
    # Implementation
    return binary_mask
```

### Signal/Slot Guidelines (PyQt)

Use semantic signals and proper slot decorators:

```python
class AnalysisTab(QWidget):
    """Analysis tab with semantic signals."""
    
    # Semantic signals - specific to operations
    model_selected = Signal(str)  # Model name
    fitting_started = Signal()
    fitting_finished = Signal(bool, str)  # Success, message
    
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._connect_signals()
    
    @Slot()
    def _on_model_changed(self):
        """Handle model selection change."""
        model_name = self.model_combo.currentText()
        self.model_selected.emit(model_name)
    
    def _connect_signals(self):
        """Connect signals and slots."""
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        
        # Connect worker signals to semantic signals
        self.worker.finished.connect(self._on_fitting_complete)
    
    @Slot(bool, str)
    def _on_fitting_complete(self, success: bool, message: str) -> None:
        """Handle worker completion and emit semantic signal."""
        if success:
            self.fitting_finished.emit(True, message)
        else:
            self.fitting_finished.emit(False, f"Failed: {message}")
```

## Testing Guidelines

### Test Structure

```python
# tests/test_processing.py
import pytest
import numpy as np
from pyama_core.processing.segmentation import segment_cells

class TestSegmentation:
    """Test cell segmentation functionality."""
    
    @pytest.fixture
    def sample_image(self):
        """Create test image with known cells."""
        image = np.zeros((100, 100), dtype=np.float32)
        # Add circular cells
        y, x = np.ogrid[-50:50, -50:50]
        mask = x*x + y*y <= 20*20
        image[mask] = 1.0
        return image
    
    def test_segment_cells_logstd(self, sample_image):
        """Test LOG-STD segmentation."""
        result = segment_cells(sample_image, method="logstd")
        
        # Verify basic properties
        assert result.dtype == bool
        assert result.shape == sample_image.shape
        assert np.any(result)  # Should detect cells
        
        # Verify specific properties
        n_cells = len(np.unique(result)) - 1  # Exclude background
        assert n_cells == 1
    
    def test_segment_cells_invalid_method(self, sample_image):
        """Test error handling for invalid method."""
        with pytest.raises(ValueError, match="not supported"):
            segment_cells(sample_image, method="invalid")
```

### Visual Testing Rules

From `AGENTS.md` testing requirements:

1. **Essential tests only**: Implement minimal tests that demonstrate correctness
2. **Save plots** to `tests/_plots/` directory
3. **Use deterministic RNG** with `np.random.seed()`
4. **Keep assertions robust**: Avoid tight numerical tolerances

```python
tests/
├── _plots/          # Generated test plots
├── test_workflow.py # End-to-end workflow
├── test_algo.py     # Visual algorithm tests
└── test_unit/       # Unit tests
    ├── test_segmentation.py
    └── test_tracking.py
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_workflow.py

# Run with coverage
uv run pytest --cov=pyama_core

# Run visual tests
uv run python tests/test_algo.py
```

## Documentation Guidelines

### Code Documentation

- Every public function/class has a docstring
- Document all parameters and return types
- Include examples for complex functions
- Use cross-references with `:class:`, `:func:`, etc.

### README Files

Each package has minimal README with:
- Brief description
- Installation instructions  
- Usage example
- Link to full documentation

### Changes Documentation

Update:
- `CHANGELOG.md` for user-facing changes
- Inline code comments for technical notes
- Documentation for new features

## Git Workflow

### Branch Structure

```
main                # Stable release branch
├── develop         # Integration branch
├── feature/xxx     # Feature branches
├── bugfix/xxx      # Bug fix branches
└── release/vX.Y.Z  # Release branches
```

### Commit Messages

Follow conventional commits:

```
type(scope): description

feat(core): add support for new file format
fix(pro): fix crash when loading invalid config
docs(readme): update installation instructions
refactor(backend): improve error handling
test(visualization): add tests for trace plotting
```

### Development Workflow

1. **Create Branch**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make Changes**
   - Write code
   - Add tests
   - Update documentation

3. **Test Changes**
   ```bash
   uv run pytest
   uv run ruff check
   uv run ruff format
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: implement awesome feature"
   ```

5. **Push and Create PR**
   ```bash
   git push origin feature/my-feature
   # Create PR on GitHub
   ```

### Pull Request Process

1. **PR Requirements**
   - All tests pass
   - Code formatted with ruff
   - Documentation updated
   - At least one review

2. **PR Template**
   ```markdown
   ## Description
   Brief description of changes
   
   ## Changes
   - What was changed
   - Why it was changed
   
   ## Testing
   - How tested
   - Test coverage
   
   ## Checklist
   - [ ] Tests pass
   - [ ] Code formatted
   - [ ] Documentation updated
   ```

## Code Quality

### Linting and Formatting

```bash
# Check code style
uv run ruff check

# Format code
uv run ruff format

# Type checking
uv run ty check
```

### Pre-commit Hooks (Optional)

```bash
# Install pre-commit
pip install pre-commit

# Setup hooks
pre-commit install

# Hooks will run automatically on commit
```

### Code Review Focus Areas

1. **Correctness**: Does the code work as intended?
2. **Performance**: Is it efficient for large datasets?
3. **Readability**: Is the code clear and maintainable?
4. **Testing**: Are edge cases covered?
5. **Documentation**: Is it well-documented?

## Package-specific Guidelines

### pyama-core

- Focus on pure Python algorithms
- Minimal dependencies
- Extensive type hints
- Performance-critical sections use numpy

### pyama-qt

- Follow Qt signal/slot patterns
- Handle threading correctly
- Provide user feedback for all operations
- Graceful error handling and recovery

## Performance Considerations

### Memory Management

```python
# Good: Use memory mapping for large arrays
image_stack = np.load("large_file.npy", mmap_mode="r")

# Good: Process frames one at a time
for frame in frames:
    process_frame(frame)
    del frame  # Explicit cleanup

# Avoid: Loading entire dataset into memory
all_data = [load_file(f) for f in file_list]  # Bad for large datasets
```

### Threading

```python
# Correct: Use ThreadPoolExecutor for CPU work
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(process_fov, fov) for fov in fovs]
    
# Avoid: Creating too many threads
threads = [Thread(target=worker) for _ in range(100)]  # Bad
```

### Vectorization

```python
# Good: Use numpy operations
result = np.sum(image > threshold)  # Fast

# Avoid: Python loops
count = 0
for i in range(image.shape[0]):
    for j in range(image.shape[1]):
        if image[i, j] > threshold:
            count += 1  # Slow
```

## Release Process

### Version Management

Use semantic versioning (MAJOR.MINOR.PATCH):
- MAJOR: Breaking changes
- MINOR: New features
- PATCH: Bug fixes

### Release Checklist

1. **Update Version**
   - Update `version` in pyproject.toml
   - Update version in each package's `__init__.py`

2. **Changelog**
   - Update `CHANGELOG.md`
   - Document all changes

3. **Testing**
   - Run full test suite
   - Test installation from source

4. **Documentation**
   - Update user documentation
   - Check for broken links

5. **Tag and Push**
   ```bash
   git tag -a v1.2.0 -m "Release v1.2.0"
   git push origin v1.2.0
   ```

### Publishing

Each package can be published independently:
```bash
cd pyama-core
uv publish

cd pyama-pro
uv publish
# etc.
```

## Getting Help

### Resources

- **Documentation**: Full reference at https://pyama.readthedocs.io
- **Issues**: Report bugs at https://github.com/your-org/pyama/issues
- **Discussions**: Feature requests and questions
- **Discord**: Real-time chat (if available)

### Asking Good Questions

1. Check existing issues and documentation
2. Provide minimal reproducible example
3. Include system information (OS, Python version)
4. Share error messages and logs

## Recognition

Contributors are recognized in:
- `CONTRIBUTORS.md` file
- Release notes
- git commit history (co-authorship)

Thank you for contributing to PyAMA! Your improvements help the microscopy community analyze data more effectively.
