# Workflow Pipeline Reference

This reference document provides complete technical details of the PyAMA-Core processing workflow, including algorithm specifications, data formats, and implementation details for creating plugins or reproducing the pipeline in other systems.

## Overview

The PyAMA-Core processing workflow processes time-lapse microscopy images through five sequential steps to extract cell traces with quantitative features. The workflow operates on individual Fields of View (FOVs) and processes data in configurable batches for efficiency.

**Processing Order:**
1. **Copying** - Extract frames from microscopy files (ND2/CZI) to disk
2. **Segmentation** - Identify cell boundaries using phase contrast images
3. **Correction** - Apply background correction to fluorescence channels
4. **Tracking** - Track cells across time points using consistent cell IDs
5. **Extraction** - Extract quantitative features and generate trace CSV files

## Input Requirements

### Microscopy Data

- **Input format**: ND2 or CZI files containing time-lapse microscopy images
- **Multiple FOVs**: Supported and processed in parallel
- **Time-lapse**: Each FOV contains multiple time frames
- **Multi-channel**: One phase contrast and one or more fluorescence channels

### Channel Configuration

- **Phase Contrast (PC) Channel**: Required for segmentation. One channel specified for cell boundary detection.
- **Fluorescence (FL) Channels**: Optional, one or more channels specified for feature extraction.

### Processing Context

- Output directory paths
- Channel configurations (`Channels` dataclass)
- Processing parameters
- Configuration saved to `processing_config.yaml`
- FOV outputs discovered by naming convention (`fov_XXX/`)

## Workflow Steps

### Step 1: Copying Service

**Purpose**: Extract raw image frames from microscopy file formats and save as memory-mapped NumPy arrays for efficient access.

#### Input
- Microscopy file path (ND2 or CZI)
- FOV index range
- Channel configuration

#### Processing Algorithm

For each FOV and specified channel:
1. Load frames sequentially from microscopy file
2. Create memory-mapped array: `{basename}_fov_{fov:03d}_{pc|fl}_ch_{channel_id}.npy`
3. Write all time frames `(T, H, W)` where:
   - `T` = number of time frames
   - `H,W` = image dimensions
4. Data type: `uint16` for raw pixel values

#### Output Format
- Phase contrast: `{basename}_fov_{fov:03d}_pc_ch_{pc_id}.npy`
- Fluorescence: `{basename}_fov_{fov:03d}_fl_ch_{fl_id}.npy`

#### Implementation Notes
- Runs sequentially per batch to avoid I/O bottlenecks
- Files are memory-mapped for efficient random access
- Existing files are detected and skipped (supports resuming)

### Step 2: Segmentation Service

**Purpose**: Identify cell boundaries in each frame using phase contrast microscopy images using LOG-STD method.

#### Input
- Phase contrast stack from Step 1: `(T, H, W)` of `uint16`

#### LOG-STD Algorithm

For each time frame `t`:

1. **Local Standard Deviation**:
   ```
   local_mean = uniform_filter(image, size=window_size)
   local_var = uniform_filter(image**2, size=window_size) - local_mean**2
   logstd = 0.5 * log(local_var)
   ```

2. **Automatic Thresholding**:
   - Build histogram of log-STD values
   - Find valley threshold between background/cell modes
   - Binary mask: `binary = logstd > threshold`

3. **Morphological Cleanup**:
   ```
   mask = binary_closing(binary, structure=disk(7), iterations=3)
   mask = remove_small_objects(mask)
   mask = binary_fill_holes(mask)
   mask = binary_opening(mask, structure=disk(7), iterations=3)
   ```

#### Output
- Labeled segmentation: `{basename}_fov_{fov:03d}_seg_labeled_ch_{pc_id}.npy`
- Format: `(T, H, W)` of `uint16`
- `0` = background, `1-N` = cell IDs (frame-specific)

#### Algorithm Characteristics
- Computes per-pixel local intensity variation
- LOG-STD is effective for phase contrast where boundaries create local intensity changes
- Parameters: window size (default from neighborhood), number of iterations (default: 3)

### Step 3: Correction Service

**Purpose**: Estimate background fluorescence using tiled interpolation for each frame.

#### Input
- Binary segmentation mask from Step 2: `(T, H, W)` of `bool`
- Raw fluorescence from Step 1: `(T, H, W)` of `uint16`

#### Tiled Interpolation Algorithm

For each fluorescence channel and frame `t`:

1. **Mask Foreground**:
   ```
   dilated = binary_dilation(seg_labeled, disk(10))
   masked = np.where(dilated, np.nan, fluorescence_image)
   ```

2. **Tile Medians**:
   - Divide frame into overlapping tiles (typical: 50-100 px)
   - Compute median of non-NaN pixels in each tile
   - Handle tiles with insufficient background via interpolation

3. **Interpolate Background**:
   ```
   from scipy.interpolate import RectBivariateSpline
   
   # Grid of tile medians
   x_grid, y_grid = np.meshgrid(tile_centers_x, tile_centers_y)
   z_grid = tile_medians
   
   # Interpolate to full resolution
   spline = RectBivariateSpline(x_grid.ravel(), y_grid.ravel(), z_grid.T)
   background = spline(flat_x_coords, flat_y_coords)
   ```

#### Output
- Background stack: `{basename}_fov_{fov:03d}_fl_background_ch_{fl_id}.npy`
- Format: `(T, H, W)` of `float32`
- Ready for correction during extraction

#### Algorithm Notes
- Each fluorescence channel processed independently
- Background saved separately for flexible correction weights
- Tile size configurable (default: 50-100 px with overlap)
- Interpolation preserves spatial variation patterns

### Step 4: Tracking Service

**Purpose**: Track cells across time frames by assigning consistent cell IDs using Intersection over Union (IoU).

#### Input
- Binary segmentation mask from Step 2: `(T, H, W)` of `bool`

#### IoU-based Hungarian Assignment Algorithm

**Per-frame Processing**:

1. **Extract Regions**:
   ```python
   from skimage.measure import regionprops_table
   
   props = regionprops_table(labeled_frame, 
                           properties=['label', 'area', 'bbox'])
   ```

2. **IoU Cost Matrix**:
   ```python
   from scipy.spatial.distance import cdist
   
   # Calculate IoU for all current vs previous region pairs
   cost_matrix = np.zeros((n_current, n_previous))
   for i, current in enumerate(current_regions):
       for j, prev in enumerate(prev_regions):
           iou = calculate_iou(current.bbox, prev.bbox)
           cost_matrix[i, j] = 1.0 - iou  # Convert distance
   ```

3. **Hungarian Assignment**:
   ```python
   from scipy.optimize import linear_sum_assignment
   
   row_ind, col_ind = linear_sum_assignment(cost_matrix)
   
   # Apply minimum IoU threshold
   for r, c in zip(row_ind, col_ind):
       if (1.0 - cost_matrix[r, c]) < min_iou:
           # Mark as new cell
           assign_new_id(r)
       else:
           # Assign previous ID
           assign_previous_id(r, c)
   ```

4. **Cell ID Management**:
   - Frame 0: Assign new IDs 1, 2, 3, ...
   - Frame n: Matched cells inherit IDs, new cells get new IDs
   - Disappeared cells: terminate trace

#### Output
- Labeled tracking: `{basename}_fov_{fov:03d}_seg_tracked_ch_{pc_id}.npy`
- Format: `(T, H, W)` of `uint16`
- `0` = background, `1-N` = cell IDs (consistent across frames)

#### Implementation Details
- IoU计算使用边界框近似，性能优化
- 最小`min_iou`阈值（默认0.1）过滤低质量匹配
- 匈牙利算法保证全局最优匹配
- 支持`min_size`和`max_size`过滤

### Step 5: Extraction Service

**Purpose**: Extract quantitative features for each tracked cell at each time point and generate CSV traces.

#### Input
- Labeled tracking from Step 4: `(T, H, W)` of `uint16`
- Phase contrast and fluorescence stacks from Step 1
- Background stacks from Step 3 (optional)
- Feature configuration list

#### Feature Extraction Algorithm

For each FOV and time point:

1. **Cell Iteration**:
   ```python
   for cell_id in unique_labels:
       mask = (labeled_frame == cell_id)
       cell_pixels = np.where(mask)
       n_pixels = np.sum(mask)
   ```

2. **Feature Computation**:
   ```python
   # Base features (always computed)
   row['fov'] = fov_id
   row['cell'] = cell_id
   row['frame'] = frame_index
   row['time'] = frame_index * frame_interval_minutes
   row['good'] = not on_border(mask)
   row['position_x'] = np.mean(col_coords)
   row['position_y'] = np.mean(row_coords)
   
   # Bounding box
   bbox = measure.regionprops(mask)[0].bbox
   row['bbox_x0'] = bbox[0]
   row['bbox_y0'] = bbox[3]
   row['bbox_x1'] = bbox[2]
   row['bbox_y1'] = bbox[1]
   ```

3. **Channel-Specific Features**:
   ```python
   # Phase contrast features
   if 'area' in pc_features:
       row['area_ch_0'] = np.sum(mask)
   
   if 'aspect_ratio' in pc_features:
       ellipse = regionprops(mask.astype(int))[0]
       row['aspect_ratio_ch_0'] = ellipse.major_axis_length / ellipse.minor_axis_length
   
   # Fluorescence features with background correction
   if 'intensity_total' in fl_features:
       raw_intensity = np.sum(image_pixels[mask])
       background_intensity = np.sum(background_pixels[mask] * background_weight)
       row[f'intensity_total_ch_{ch_id}'] = raw_intensity - background_intensity
   ```

4. **Background Correction**:
   ```python
   # Configurable weight from params["background_weight"]
   background_weight = clip(params.get("background_weight", 1.0), 0.0, 1.0)
   
   # Apply weight during extraction
   corrected_intensity = raw_intensity - background_weight * background_intensity
   ```

#### Quality Filtering

1. **Trace Length Filter**:
   ```python
   min_frames = params.get('min_frames', 30)
   trace_lengths = calculate_trace_lengths(traces)
   filtered = traces[trace_lengths >= min_frames]
   ```

2. **Border Filter**:
   ```python
   border_margin = params.get('border_margin', 50)
   
   def on_border(mask):
       return np.any(mask[:border_margin, :]) or \
              np.any(mask[-border_margin:, :]) or \
              np.any(mask[:, :border_margin]) or \
              np.any(mask[:, -border_margin:])
   
   # Remove border cells entirely
   filtered = filtered[~filtered['cell'].isin(border_cells)]
   ```

#### Output Format

**Per-FOV CSV**: `{basename}_fov_{fov:03d}_traces.csv`

```
fov,cell,frame,good,position_x,position_y,bbox_x0,bbox_y0,bbox_x1,bbox_y1,area_ch_0,aspect_ratio_ch_0,intensity_total_ch_1
0,0,0,True,100.5,200.3,85,165,115,235,450,1.234,1234.5
0,0,1,True,101.2,199.8,86,166,116,236,455,1.236,1356.2
```

**Column Naming Convention**:
- Base columns: fov, cell, frame, good, position_x/y, bbox_*
- Feature columns: `{feature}_ch_{channel_id}` (e.g., `intensity_total_ch_1`)

## Output Structure

```
output_dir/
├── processing_config.yaml           # Metadata, channels, parameters
├── fov_000/
│   ├── basename_fov_000_pc_ch_0.npy          # Raw PC stack
│   ├── basename_fov_000_fl_ch_1.npy          # Raw FL stacks (one per channel)
│   ├── basename_fov_000_seg_labeled_ch_0.npy         # Labeled segmentation (untracked)
│   ├── basename_fov_000_seg_tracked_ch_0.npy # Tracked cell IDs
│   ├── basename_fov_000_fl_background_ch_1.npy # Background interpolation stacks
│   └── basename_fov_000_traces.csv                 # Combined feature traces
├── fov_001/
│   └── ...
```

## Batch Processing Implementation

### Thread Pool Executor Pattern

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def run_batch(fov_batch, config, n_workers):
    """Process a batch of FOVs in parallel."""
    
    # Sequential copying (I/O bound)
    for fov in fov_batch:
        copying_service.copy_fov(fov, config)
    
    # Parallel processing (CPU bound)
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = []
        
        for fov in fov_batch:
            future = executor.submit(
                process_fov_parallel,
                fov,
                config
            )
            futures.append(future)
        
        # Wait for completion with progress tracking
        for future in as_completed(futures, timeout=None):
            result = future.result()
            update_progress(result)
```

### Memory Management

```python
def process_worker(fov_id, config):
    """Worker function for parallel FOV processing."""
    
    try:
        # Load data lazily
        pc_stack = np.load(get_filepath(fov_id, 'pc'), mmap_mode='r')
        
        # Process frames one at a time to reduce memory
        for frame in range(n_frames):
            frame_data = pc_stack[frame]
            processed = process_frame(frame_data)
            save_frame_result(processed)
            
            # Check for cancellation
            if check_cancelled():
                return {'fov': fov_id, 'status': 'cancelled'}
        
        return {'fov': fov_id, 'status': 'completed'}
        
    except Exception as e:
        logger.error(f"Error processing FOV {fov_id}: {e}")
        return {'fov': fov_id, 'status': 'failed', 'error': str(e)}
```

### Cancellation Support

Cancellation is handled via `threading.Event` within the task runner:

```python
# Usage in workflow
if cancel_event.is_set():
    logger.info("Cancellation requested, cleaning up")
    cleanup_partial_results()
    return False
```

## Data Type Specifications

### Image Arrays

| Stage | File Type | Data Type | Dimensions | Notes |
|-------|-----------|-----------|------------|-------|
| Raw Images | .npy | uint16 | (T, H, W) | Memory-mapped for efficiency |
| Segmentation | .npy | uint16 | (T, H, W) | Labeled mask (untracked) |
| Tracking | .npy | uint16 | (T, H, W) | Cell IDs, 0=background |
| Background | .npy | float32 | (T, H, W) | Estimate per channel |

### CSV Schemas

**Processing Traces** (per-FOV):
- All columns prefixed by channel ID
- Frame-based, time computed after loading
- Includes quality flag (`good` column)

**Merged Traces** (per-sample):
- Same format as processing traces
- Multiple FOVs combined
- Includes sample metadata in headers

**Fitted Results** (post-analysis):
- One row per cell
- Includes model type, R², parameters
- Additional columns per model parameters

## Algorithm Parameters

### Segmentation Parameters

```python
segmentation_params = {
    'logstd_window_size': 3,  # Neighborhood for std computation
    'morph_size': 7,         # Structuring element size
    'morph_iterations': 3,   # Number of opening/closing iterations
    'min_object_size': 50,   # Minimum cell size in pixels
    'max_object_size': 10000, # Maximum cell size in pixels
}
```

### Tracking Parameters

```python
tracking_params = {
    'min_iou': 0.1,     # Minimum IoU for cell matching
    'min_frames': 30,   # Minimum trace length
    'border_margin': 50, # Exclusion margin (pixels)
}
```

### Extraction Parameters

```python
extraction_params = {
    'background_weight': 1.0,  # Background correction weight [0-1]
    'frame_interval': 10.0,    # Minutes per frame (default)
    'time_mapping': None,      # Custom frame->time mapping (dict)
    'features': {
        'phase': ['area', 'aspect_ratio'],
        'fluorescence': ['intensity_total', 'intensity_mean']
    }
}
```

## Performance Characteristics

### Memory Usage

| Dataset Size | Approximate RAM Usage | Notes |
|--------------|----------------------|-------|
| 10 FOVs, 50 frames | 1-2 GB | Single workstation |
| 100 FOVs, 180 frames | 8-12 GB | Requires 16GB+ RAM |
| 500+ FOVs | 32GB+ | Consider distributed processing |

### Processing Speed

| Operation | Speed (per FOV) | Parallel Scaling |
|-----------|------------------|------------------|
| Copying (sequential) | 2-5 sec | No parallelization |
| Segmentation | 10-30 sec | 4-8 threads optimal |
| Tracking | 5-15 sec | Linear up to CPU count |
| Extraction | 2-8 sec | CPU-bound, parallel |

### Optimization Strategies

1. **Memory Mapping**: Use `mmap_mode='r'` for large arrays
2. **Batch Size**: Tune based on RAM availability
3. **Worker Count**: Match to CPU cores (typically 4-8)
4. **SSD Storage**: Improves I/O for large datasets

## Extension Points

### Custom Features

```python
def extract_custom_feature(image, mask, context):
    """User-defined feature extraction."""
    # Implement custom logic
    return feature_value

# Register in feature system
PHASE_FEATURES['custom_feature'] = extract_custom_feature
```

### Alternative Algorithms

Replace core algorithms while maintaining interface:
- Segmentation: watershed, deep learning
- Tracking: Kalman filter, graph-based
- Feature extraction: custom metrics

### Integration Hooks

```python
class CustomPreprocessor:
    """Pre-process frames before segmentation."""
    def process(self, image):
        # Custom preprocessing
        return processed_image

# Inject into workflow
workflow.register_preprocessor(CustomPreprocessor())
```

## Implementation Guidelines

### Plugin Development

1. **Follow Interface Contracts**: Maintain input/output shapes
2. **Handle Errors Gracefully**: Return status codes, not exceptions
3. **Consider Performance**: Use vectorized operations where possible
4. **Document Parameters**: Include bounds, defaults, units
5. **Provide Tests**: Visual verification for image-based operations

### Quality Assurance

1. **Deterministic RNG**: Use fixed seeds for reproducibility
2. **Parameter Validation**: Check bounds before processing
3. **Progress Reporting**: Provide meaningful status updates
4. **Cleanup on Failure**: Preserve partial results for debugging
5. **Logging**: Include sufficient diagnostic information

This reference provides complete technical specifications for implementing, extending, or reproducing the PyAMA processing pipeline in any environment.
