# Testing Protocol

This document provides step-by-step testing protocols for validating PyAMA functionality across all packages and components.

## Overview

PyAMA testing follows a multi-layered approach:
- **Unit Tests**: Individual function and class testing
- **Integration Tests**: Component interaction testing  
- **Visual Tests**: Algorithm verification with visual output
- **GUI Tests**: Interactive application testing
- **Performance Tests**: Load and stress testing

## Test Organization

Tests are organized within each package directory. Each package has its own `tests/` subdirectory. The main test suite is currently in `pyama-core/tests/`:

```
{package}/tests/  (e.g., pyama-core/tests/)
├── _plots/                    # Generated visual test outputs
├── _results/                  # Test artifacts (gitignored)
├── __init__.py
├── conftest.py                # Pytest configuration
├── analysis/                  # Analysis model tests
│   ├── test_event.py
│   └── test_kinetic.py
├── features/                  # Feature extraction tests
│   ├── __init__.py
│   ├── test_area.py
│   ├── test_intensity_total.py
│   └── test_particle_num.py
├── processing/                # Processing workflow tests
│   ├── test_merge.py
│   ├── test_normalization.py
│   ├── test_seg.py
│   └── test_track.py
└── utils/                     # Utility function tests
    ├── __init__.py
    └── progress.py
```

## Running Tests

### All Tests

```bash
# Run complete test suite
uv run pytest

# Run with coverage
uv run pytest --cov=pyama_core --cov-report=html
```

### Specific Categories

```bash
# Unit tests only
uv run pytest tests/unit/

# Integration tests
uv run pytest tests/integration/

# Visual tests (require manual inspection)
uv run pytest pyama-core/tests/processing/test_seg.py -v

# Performance tests
uv run pytest tests/performance/
```

## Visual Testing Guidelines

### Plot Generation

All visual tests save plots to `{package}/tests/_plots/` (e.g., `pyama-core/tests/_plots/` for core tests):

```python
def test_segmentation_round_cells():
    """Test segmentation on round synthetic cells."""
    # Generate synthetic data
    np.random.seed(42)  # Deterministic RNG
    
    # Create test image
    image = generate_round_cells(n_cells=10, noise_level=0.1)
    
    # Run segmentation
    mask = segment_cells(image, method="logstd")
    
    # Visualize results
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    axes[0].imshow(image, cmap='gray')
    axes[0].set_title('Original Image')
    
    axes[1].imshow(mask, cmap='binary')
    axes[1].set_title('Segmentation Result')
    
    # Add boundaries
    for i, prop in enumerate(regionprops(mask)):
        if prop.area > 50:  # Filter small objects
            y0, x0, y1, x1 = prop.bbox
            rect = Rectangle((x0, y0), x1-x0, y1-y0, 
                           fill=False, edgecolor='red', linewidth=2)
            axes[1].add_patch(rect)
    
    # Save plot (adjust package name as needed)
    plot_dir = os.getenv('PYAMA_PLOT_DIR', 'pyama-core/tests/_plots')
    os.makedirs(plot_dir, exist_ok=True)
    plt.savefig(f'{plot_dir}/segmentation_round_cells.pdf', dpi=150)
    plt.close(fig)  # important: close figure
    
    # Assertions
    n_cells = len([r for r in regionprops(mask) if r.area > 50])
    assert n_cells == 10, f"Expected 10 cells, got {n_cells}"
```

### Test Requirements

From `AGENTS.md` protocol rules:

1. **Essential Tests Only**
   - Event detection: noisy step up/down with event lines
   - Particle counting: many Gaussian particles with bounding boxes

2. **Output Location**
   - Always save to `{package}/tests/_plots/` (e.g., `pyama-core/tests/_plots/` for core tests)
   - Override with `PYAMA_PLOT_DIR` environment variable

3. **Deterministic RNG**
   ```python
   np.random.seed(42)  # Or any fixed seed
   ```

4. **Robust Assertions**
   ```python
   # Good: Count matches expected
   assert len(detected_cells) >= expected_min
   
   # Bad: Tight numerical tolerance
   assert abs(mean_intensity, 2.345, 0.001)  # Too strict
   ```

5. **No OS-Specific Paths**
   ```python
   # Bad: Linux temp
   tempfile.mktemp()  # Don't use
   
   # Good: Current directory
   Path("test_output").mkdir(exist_ok=True)
   ```

## PyAMA-Qt GUI Testing Protocol

The complete GUI testing protocol lives in `tests/PROTOCOL.md`. It includes:

### Automated Checks

```python
# tests/gui/test_ui_components.py
def test_parameter_table_validation():
    """Test parameter input validation."""
    table = ParameterTable()
    
    # Valid input
    table.set_parameter("fov_start", 0)
    assert table.is_valid()
    
    # Invalid input
    table.set_parameter("fov_end", -1)
    assert not table.is_valid()
    assert table.get_error() == "FOV end cannot be negative"
```

### Manual Testing Checklist

Key GUI testing areas:

1. **Processing Tab**
   - [ ] ND2 file loading and metadata extraction
   - [ ] Channel selection and feature configuration
   - [ ] Parameter validation and workflow execution
   - [ ] Progress tracking and cancellation

2. **Visualization Tab**
   - [ ] FOV and channel selection
   - [ ] Image navigation and display
   - [ ] Trace inspection and quality control
   - [ ] CSV export functionality

3. **Analysis Tab**
   - [ ] CSV loading and data validation
   - [ ] Model configuration and fitting
   - [ ] Results visualization and statistics
   - [ ] Parameter analysis and export

## Integration Testing

### Workflow Integration

```python
# tests/integration/test_complete_workflow.py
def test_end_to_end_workflow():
    """Test complete workflow from ND2 to fitted results."""
    
    # Setup
    with TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "output"
        merged_dir = Path(tmpdir) / "merged"
        
        # Step 1: Process ND2
        config = create_test_config(output_dir)
        success = run_complete_workflow(
            metadata=test_metadata,
            config=config,
            fov_start=0,
            fov_end=4,  # Small batch
            batch_size=2,
            n_workers=2
        )
        assert success, "Processing workflow failed"
        
        # Step 2: Verify outputs
        fov_dirs = list(output_dir.glob("fov_*"))
        assert len(fov_dirs) == 5
        
        for fov_dir in fov_dirs:
            trace_file = fov_dir / "test_fov_*_traces.csv"
            assert trace_file.exists(), f"Missing trace in {fov_dir}"
            
            # Verify CSV structure
            df = pd.read_csv(trace_file)
            required_columns = ["fov", "cell", "frame", "good"]
            for col in required_columns:
                assert col in df.columns, f"Missing column: {col}"
        
        # Step 3: Merge results
        sample_yaml = output_dir / "samples.yaml"
        create_sample_file(sample_yaml)
        
        run_merge(sample_yaml, output_dir, merged_dir)
        
        # Verify merged files
        merged_files = list(merged_dir.glob("*_merged.csv"))
        assert len(merged_files) > 0
        
        # Step 4: Analyze results
        for merged_file in merged_files:
            df = pd.read_csv(merged_file)
            model = get_model("maturation")
            result = fit_model(model, df['time'], df['value'])
            assert result['success'], f"Fitting failed for {merged_file}"
            assert result['r_squared'] > 0.5, "Poor fit quality"
```

### API Integration

```python
# tests/integration/test_api_workflow.py
def test_api_complete_workflow():
    """Test API workflow endpoints."""
    
    client = TestClient(app)
    
    # Step 1: Load metadata
    response = client.post(
        "/api/v1/processing/load-metadata",
        json={"file_path": TEST_ND2_PATH}
    )
    assert response.status_code == 200
    metadata = response.json()["data"]
    
    # Step 2: Start workflow
    config = {
        "microscopy_path": TEST_ND2_PATH,
        "output_dir": TEST_OUTPUT_DIR,
        "channels": {
            "phase": {"channel": 0, "features": ["area"]},
            "fluorescence": []
        },
        "parameters": {"fov_start": 0, "fov_end": 4}
    }
    
    response = client.post("/api/v1/processing/workflow/start", json=config)
    assert response.status_code == 200
    job_id = response.json()["data"]["job_id"]
    
    # Step 3: Monitor completion
    for _ in range(60):  # 60 second timeout
        response = client.get(f"/api/v1/processing/workflow/status/{job_id}")
        status = response.json()["data"]["status"]
        
        if status == "completed":
            break
        elif status == "failed":
            pytest.fail("Workflow failed")
        
        time.sleep(1)
    
    # Step 4: Get results
    response = client.get(f"/api/v1/processing/workflow/results/{job_id}")
    assert response.status_code == 200
    
    results = response.json()["data"]
    assert len(results["traces"]) == 5  # FOVs 0-4
```

## Performance Testing

### Memory Usage

```python
# tests/performance/test_memory.py
def test_memory_usage_large_dataset():
    """Test memory usage with large datasets."""
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # Process large dataset
    config = create_large_dataset_config(n_fovs=50, n_frames=100)
    
    with memory_monitor() as memory_log:
        success = run_complete_workflow(
            metadata=large_metadata,
            config=config,
            batch_size=2,
            n_workers=4
        )
    
    peak_memory = max(memory_log)
    memory_increase = peak_memory - initial_memory
    
    # Should not exceed reasonable limits
    assert memory_increase < 4096, f"Memory usage too high: {memory_increase} MB"
    assert success, "Large dataset processing failed"
```

### Processing Speed

```python
# tests/performance/test_speed.py
def test_processing_speed():
    """Benchmark processing speed."""
    import time
    
    sizes = [(10, 50), (20, 100), (50, 200)]  # (FOVs, frames)
    speed_results = []
    
    for n_fovs, n_frames in sizes:
        start_time = time.time()
        
        run_complete_workflow(
            metadata=create_test_metadata(n_fovs=n_fovs, n_frames=n_frames),
            config=test_config,
            n_workers=4
        )
        
        elapsed = time.time() - start_time
        cells_per_second = (n_fovs * n_frames * AVG_CELLS_PER_FOV) / elapsed
        
        speed_results.append((n_fovs, n_frames, cells_per_second))
        print(f"{n_fovs}x{n_frames}: {cells_per_second:.1f} cells/sec")
    
    # Verify scaling is reasonable
    assert speed_results[2][2] > speed_results[0][2], "No speed improvement with larger batches"
```

## Data Validation

### Synthetic Data Generation

```python
# tests/utils/test_data.py
class SyntheticDataGenerator:
    """Generate test microscopy data with known properties."""
    
    @staticmethod
    def create_cell_tracks(n_cells: int, n_frames: int):
        """Create synthetic cell trajectories."""
        tracks = []
        
        for cell_id in range(n_cells):
            # Random walk with drift
            x = np.cumsum(np.random.randn(n_frames) * 0.5)
            y = np.cumsum(np.random.randn(n_frames) * 0.5)
            
            # Add linear drift
            x += np.linspace(0, 10, n_frames)
            y += np.linspace(0, 5, n_frames)
            
            tracks.append({
                'cell_id': cell_id,
                'positions': np.column_stack([x, y])
            })
        
        return tracks
    
    @staticmethod
    def create_fluorescence_trace():
        """Create synthetic fluorescence with maturation kinetics."""
        t = np.linspace(0, 30, 180)  # 30 hours, 180 points
        
        # Maturation model: f(t) = A * (1 - exp(-kt)) + B
        A = 2.0  # Amplitude
        k = 0.1  # Rate constant
        B = 0.5  # Baseline
        
        # Add noise
        signal = A * (1 - np.exp(-k * t)) + B
        noise = np.random.randn(len(t)) * 0.1
        
        return t, signal + noise
```

### CSV Validation

```python
# tests/validation/test_csv.py
def validate_trace_csv(filepath: Path) -> bool:
    """Validate trace CSV format and content."""
    try:
        df = pd.read_csv(filepath)
        
        # Required columns
        required = ['fov', 'cell', 'frame', 'good']
        for col in required:
            if col not in df.columns:
                return False
        
        # Data types
        assert df['fov'].dtype in [int, 'int64']
        assert df['cell'].dtype in [int, 'int64']
        assert df['frame'].dtype in [int, 'int64']
        assert df['good'].dtype == bool
        
        # Value ranges
        assert df['frame'].min() >= 0
        assert df['cell'].min() >= 1
        assert len(df) > 0
        
        return True
        
    except Exception:
        return False
```

## Continuous Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.12']
    
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install UV
      run: pip install uv
    
    - name: Install dependencies
      run: uv sync --all-extras
    
    - name: Run tests
      run: uv run pytest --cov=pyama_core --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### Test Categories in CI

1. **Unit Tests**: Fast, run on all PRs
2. **Integration Tests**: Medium speed, run on PRs
3. **Performance Tests**: Slow, run on main branch
4. **Visual Tests**: Manual verification, artifacts saved

## Test Data Management

### Synthetic Test Data

- Small datasets checked into repository
- Large datasets generated on-the-fly
- Deterministic seed for reproducibility

### Real Test Data

- Anonymized experimental data
- Stored in separate repository
- Accessed via Git LFS or download server

### Test Artifacts

- Plots saved to `_plots/`
- Test reports in HTML format
- Performance benchmarks as JSON

## Debugging Tests

### Debug Mode

```bash
# Run single test with debugging
uv run pytest pyama-core/tests/processing/test_merge.py -v -s --pdb

# Enable debug logging
PYAMA_LOG_LEVEL=DEBUG uv run pytest
```

### Test Output

```python
# In test files
import logging

logger = logging.getLogger(__name__)

def test_something():
    logger.info("Starting test")
    # ... test code ...
    logger.debug(f"Intermediate result: {result}")
```

### Common Issues

1. **Flaky Tests**
   - Use deterministic seeds
   - Add retry logic for network calls
   - Increase timeouts

2. **Environment Specific**
   - Use temp directories
   - Avoid hardcoded paths
   - Test on multiple platforms

3. **Resource Exhaustion**
   - Clean up resources in tearDown
   - Use timeouts for long operations
   - Monitor memory usage

## Contributing to Tests

When adding new features:

1. **Add Unit Tests**
   - Test new functions/classes
   - Cover edge cases
   - Mock external dependencies

2. **Add Integration Tests**
   - Test feature in context
   - Verify end-to-end workflows
   - Include error conditions

3. **Update Documentation**
   - Add test examples
   - Document testing procedures
   - Update checklists

4. **Performance Monitoring**
   - Add benchmarks for significant changes
   - Monitor memory usage
   - Document performance characteristics

## Test Metrics and Targets

### Coverage Targets
- Core packages: > 90% coverage
- GUI packages: > 80% coverage  
- Utilities: > 95% coverage

### Performance Targets
- Small dataset (< 10 FOVs): < 5 minutes
- Medium dataset (10-50 FOVs): < 30 minutes
- Large dataset (> 50 FOVs): < 2 hours

### Quality Targets
- All tests pass on CI
- Zero flaky tests
- Memory usage < 4GB for typical datasets

This comprehensive testing protocol ensures PyAMA remains reliable, performant, and maintainable across all its components.
