# PyAMA File Formats Reference

This document describes all file formats created and used by the PyAMA processing pipeline.

## Overview

PyAMA creates intermediate and final output files in standardized formats. Files are organized in per-FOV directories with consistent naming conventions.

```
output_dir/
├── processing_config.yaml     # Configuration metadata
├── fov_000/                   # First FOV output directory
│   ├── sample_fov_000_pc_ch_0.npy     # Phase contrast data
│   ├── sample_fov_000_fl_ch_1.npy     # Fluorescence channel 1
│   ├── sample_fov_000_fl_ch_2.npy     # Fluorescence channel 2
│   ├── sample_fov_000_fl_background_ch_1.npy  # Background estimate 1
│   ├── sample_fov_000_fl_background_ch_2.npy  # Background estimate 2
│   ├── sample_fov_000_seg_labeled_ch_0.npy    # Segmentation masks
│   ├── sample_fov_000_seg_tracked_ch_0.npy    # Tracked segmentation
│   ├── sample_fov_000_crops.h5              # Cropped cell data (HDF5)
│   └── sample_fov_000_traces.csv            # Extracted features
├── fov_001/                   # Second FOV output directory
│   └── ...
└── ...
```

## Naming Convention

All per-FOV files follow the pattern: `{base}_fov_{id:03d}_{type}{_ch_{channel}}.{ext}`

- `{base}`: Base name from input microscopy file
- `{id}`: Zero-padded FOV index (e.g., 000, 001, 002)
- `{type}`: Data type (pc, fl, seg_labeled, seg_tracked, fl_background, crops, traces)
- `{channel}`: Channel index (omitted for crops and traces)
- `{ext}`: File extension (npy, h5, csv)

---

## NumPy Array Files (.npy)

### Phase Contrast Data: `*_pc_ch_{N}.npy`

**Purpose**: Raw phase contrast image stack for cell detection.

**Shape**: `(T, H, W)` where:
- `T`: Number of time frames
- `H`: Height in pixels  
- `W`: Width in pixels

**Data Type**: `uint16` (16-bit grayscale)

**Format**: NumPy memory-mapped array (`.npy` with `mmap_mode='r'`)

**Example**: 100 frames of 512×512 images → shape `(100, 512, 512)`

### Fluorescence Data: `*_fl_ch_{N}.npy`

**Purpose**: Raw fluorescence image stacks for intensity analysis.

**Shape**: `(T, H, W)`

**Data Type**: `uint16` (16-bit grayscale)

**Format**: NumPy memory-mapped array

### Background Estimate: `*_fl_background_ch_{N}.npy`

**Purpose**: Estimated background fluorescence for correction.

**Shape**: `(T, H, W)`

**Data Type**: `float32` (32-bit float, can have negative values)

**Algorithm**: Tiled interpolation from cell-free regions

### Segmentation Masks: `*_seg_labeled_ch_{N}.npy`

**Purpose**: Cell segmentation masks with unique cell labels.

**Shape**: `(T, H, W)`

**Data Type**: `uint16` (cell IDs as integers)

**Values**:
- `0`: Background (no cell)
- `1, 2, 3, ...`: Cell labels (may vary per frame)

**Algorithm**: LOG-STD or CellPose detection, connected component labeling

### Tracked Segmentation: `*_seg_tracked_ch_{N}.npy`

**Purpose**: Segmentation masks with consistent cell IDs across time.

**Shape**: `(T, H, W)`

**Data Type**: `uint16`

**Values**:
- `0`: Background
- `1, 2, 3, ...`: Cell IDs (persistent across frames)

**Algorithm**: IoU-based tracking or BTrack integration

---

## HDF5 Files: `*_crops.h5`

**Purpose**: Efficient storage of cropped cell regions for feature extraction.

**Format**: HDF5 with hierarchical organization by cell ID.

### File Structure

```
*_crops.h5
├── cell_0001/                          # Cell ID 1
│   ├── bboxes          (N, 5) int32    # Frame data
│   ├── frames          (N,) int32      # Frame indices  
│   ├── masks/                        # Segmentation masks
│   │   ├── frame_000    (h, w) bool   # Frame 0 mask
│   │   ├── frame_001    (h, w) bool   # Frame 1 mask
│   │   └── ...
│   ├── channels/                     # Cropped image data
│   │   ├── pc_ch_0/                  # Phase contrast channel
│   │   │   ├── frame_000  (h, w) uint16
│   │   │   ├── frame_001  (h, w) uint16
│   │   │   └── ...
│   │   ├── fl_ch_1/                  # Fluorescence channel 1  
│   │   │   ├── frame_000  (h, w) uint16
│   │   │   └── ...
│   │   └── fl_ch_2/                  # Fluorescence channel 2
│   │       ├── frame_000  (h, w) uint16
│   │       └── ...
│   └── backgrounds/                  # Background corrections (optional)
│       ├── fl_ch_1/                  # Background for FL channel 1
│       │   ├── frame_000  (h, w) float32
│       │   └── ...
│       └── fl_ch_2/
│           ├── frame_000  (h, w) float32
│           └── ...
├── cell_0002/                          # Cell ID 2
│   └── ...
└── ...
```

### Dataset Details

#### `bboxes` Dataset
- **Shape**: `(N, 5)` where `N` = number of frames for this cell
- **Data Type**: `int32`
- **Columns**: `[frame_idx, y0, x0, y1, x1]` (per-frame bounding boxes)
- **Coordinates**: Pixel indices, `(x0, y0)` inclusive, `(x1, y1)` exclusive

#### `frames` Dataset  
- **Shape**: `(N,)`
- **Data Type**: `int32`
- **Values**: Frame indices where this cell exists

#### `masks/` Group
- **Format**: Boolean masks of shape `(crop_height, crop_width)`
- **Purpose**: Exact cell segmentation within bounding box
- **Data Type**: `bool`

#### `channels/` Group
- **Format**: Cropped image regions
- **Data Type**: `uint16` for raw channel data
- **Purpose**: Efficient feature extraction without loading full frames
- **PC channel**: Always present if PC configured
- **FL channels**: Optional, present if configured

#### `backgrounds/` Group
- **Format**: Background correction data
- **Data Type**: `float32`
- **Purpose**: Background subtraction for fluorescence channels
- **Optional**: Only present if FL channels and background estimation ran

### Data Access Examples

**Reading with h5py:**
```python
import h5py
import numpy as np

with h5py.File('sample_fov_000_crops.h5', 'r') as f:
    cell_1 = f['cell_0001']
    
    # Get cell metadata
    bboxes = cell_1['bboxes'][:]           # (N, 5) int32
    frames = cell_1['frames'][:]           # (N,) int32
    
    # Get PC channel data
    pc_crops = cell_1['channels/pc_ch_0']
    for i, frame_idx in enumerate(frames):
        pc_img = pc_crops[f'frame_{frame_idx:04d}'][:]
        mask = cell_1['masks'][f'frame_{frame_idx:04d}'][:]
        
        # Process crop...
```

**Memory Efficiency:**
- Crops are typically 20-50 pixels per dimension
- Loading per-cell vs per-frame reduces memory usage
- Compression with `gzip` reduces file size ~60-80%

---

## CSV Files: `*_traces.csv`

**Purpose**: Tabular cell feature data for analysis.

**Format**: Comma-separated values (CSV) with header row.

### Column Structure

#### Base Columns (always present when PC configured)
| Column | Type | Description |
|--------|------|-------------|
| `fov` | int | Field of view index |
| `cell` | int | Cell ID (consistent across frames) |
| `frame` | int | Frame index (0-based) |
| `good` | bool | Quality flag (always `True` for extracted traces) |
| `position_x` | float | Cell centroid X coordinate (pixels) |
| `position_y` | float | Cell centroid Y coordinate (pixels) |
| `bbox_x0` | float | Bounding box left coordinate |
| `bbox_y0` | float | Bounding box top coordinate |
| `bbox_x1` | float | Bounding box right coordinate |
| `bbox_y1` | float | Bounding box bottom coordinate |

#### Feature Columns (channel-dependent)

Format: `{feature}_ch_{channel_id}`

**PC Features:**
- `area_ch_0` - Cell area in pixels
- `aspect_ratio_ch_0` - Bounding box aspect ratio
- `eccentricity_ch_0` - Shape eccentricity

**Fluorescence Features:**
- `intensity_total_ch_1` - Sum intensity per cell
- `intensity_mean_ch_1` - Mean intensity per cell  
- `particle_num_ch_2` - Particle count in cell

### Example Output

```csv
fov,cell,frame,good,position_x,position_y,bbox_x0,bbox_y0,bbox_x1,bbox_y1,area_ch_0
0,1,0,True,104.5,50.5,100,45,110,55,225.0
0,1,1,True,105.5,51.5,101,46,111,56,227.0
0,1,2,True,106.5,52.5,102,47,112,57,229.0
0,2,0,True,204.3,100.2,200,95,210,105,180.0
```

### Data Organization

- **One row per cell per frame** (tidy format)
- **Sorted**: Primary by `cell`, secondary by `frame`
- **Float precision**: 6 decimal places for coordinates, 3 for features
- **Missing data**: NaN for features that couldn't be extracted

---

## Configuration Files

### `processing_config.yaml`

**Purpose**: Complete record of processing configuration for reproducibility.

**Format**: YAML with two main sections:

```yaml
params:
  segmentation_method: logstd
  tracking_method: iou
  crop_padding: 5
  mask_margin: 0
  min_frames: 30
  border_margin: 50
  background_weight: 1.0

channels:
  pc:
    channel: 0
    features: [area, aspect_ratio]
  fl:
    - channel: 1
      features: [intensity_total, intensity_mean]
    - channel: 2
      features: [particle_num]
```

**Location**: Saved to output directory root
**Usage**: Loaded by downstream analysis tools for parameter tracking

---

## Data Access Examples

### Python Access Patterns

**Loading NumPy arrays:**
```python
import numpy as np

# Memory-mapped access (doesn't load into RAM)
pc_data = np.load('sample_fov_000_pc_ch_0.npy', mmap_mode='r')
seg_data = np.load('sample_fov_000_seg_tracked_ch_0.npy', mmap_mode='r')

# Get specific frame (loaded into RAM on demand)
frame_5 = pc_data[5]  # (H, W) uint16
cells_frame_5 = seg_data[5]  # (H, W) uint16
```

**CSV analysis:**
```python
import pandas as pd

df = pd.read_csv('sample_fov_000_traces.csv')

# Get trajectory for cell 1
cell_1_trajectory = df[df['cell'] == 1]

# Calculate velocity
velocity = np.sqrt(np.diff(cell_1_trajectory['position_x'])**2 + 
                  np.diff(cell_1_trajectory['position_y'])**2)
```

**HDF5 exploration:**
```python
import h5py

with h5py.File('sample_fov_000_crops.h5', 'r') as f:
    print("Cells found:", list(f.keys()))
    
    for cell_name in f.keys():
        cell_data = f[cell_name]
        n_frames = len(cell_data['frames'])
        channels = list(cell_data['channels'].keys())
        print(f"{cell_name}: {n_frames} frames, channels={channels}")
```

---

## File Size Estimates

Typical file sizes for a 100-frame, 512×512, multi-FOV dataset:

| File Type | Per FOV | Compression | 10 FOVs Total |
|-----------|---------|-------------|----------------|
| PC data (`.npy`) | 50 MB | Memory-mapped | 500 MB |
| FL data (`.npy`) | 50 MB | Memory-mapped | 500 MB |
| Background (`.npy`) | 200 MB | Float32 | 2 GB |
| Segmentation (`.npy`) | 100 MB | Memory-mapped | 1 GB |
| Crops (`.h5`) | 10-50 MB | gzip | 100-500 MB |
| Traces (`.csv`) | 1-5 MB | Text | 10-50 MB |

**Tips:**
- Use memory-mapped NumPy files for large datasets
- HDF5 crops provide per-cell access without loading full frames
- CSV traces are text-based but compact for analysis

---

## Format Compatibility

- **NumPy**: PyAMA-specific format, requires pyama-core for reading
- **HDF5**: Standard format, accessible with h5py, HDF5 libraries, MATLAB, etc.
- **CSV**: Universal format, accessible in Excel, pandas, R, etc.
- **YAML**: Human-readable configuration, compatible with standard parsers

This standardized format enables integration with existing microscopy analysis pipelines while maintaining reproducibility and efficiency.