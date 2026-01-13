# PyAMA Workflow Configurations Reference

This document explains how the PyAMA processing pipeline adapts to different channel configurations. 

This is a companion to the [Workflow Pipeline Reference](workflow-pipeline.md) which covers the complete technical pipeline details, while this document focuses on configuration flexibility and practical usage patterns.

## Overview

The PyAMA workflow automatically skips steps that don't have the required channel data. This makes it flexible for different analysis scenarios:

- **Full analysis**: PC + FL channels (all steps)
- **PC-only tracking**: PC channel only (background estimation auto-skipped)
- **Position/bbox tracking**: PC with no features (extraction still gives tracking data)

## Workflow Steps and Channel Requirements

| Step | Required Channels | Behavior When Missing |
|------|-----------------|----------------------|
| **Copy** | Any configured | Runs with any channels (PC/FL) |
| **Segmentation** | PC channel | **Skipped** with warning if no PC |
| **Tracking** | PC channel | **Skipped** with warning if no PC |
| **Background Estimation** | FL channels | **Skipped automatically** if no FL |
| **Cropping** | PC channel | **Skipped** with warning if no PC |
| **Extraction** | PC channel | Creates empty CSV if no channels, **always includes base fields** if PC present |

## Key Behaviors

### Background Estimation Auto-Skip

```python
# In BackgroundEstimationService.process_fov():
if not fl_channels:
    logger.info("No fluorescence channels, skipping background estimation")
    return  # Skipped automatically
```

### Extraction with PC-Only

```python
# In ExtractionService.process_fov():
if pc_channel is not None:
    # Always include PC channel if configured, even with no features
    channel_configs.append(ChannelFeatureConfig(
        channel_name=f"pc_ch_{pc_channel}",
        channel_id=pc_channel,
        features=[],  # Empty features OK!
        background_name=None,
    ))
```

### Base Fields Always Included

When PC channel is configured, extraction always outputs:
- `cell` - Cell ID (consistent across frames)
- `frame` - Frame index (0-based)
- `good` - Quality flag (always True for extracted)
- `position_x`, `position_y` - Cell centroid coordinates
- `bbox_x0`, `bbox_y0`, `bbox_x1`, `bbox_y1` - Bounding box coordinates

No additional feature columns are added unless explicitly configured.

## Example Configurations

### Full Analysis (PC + FL)

```yaml
channels:
  pc:
    channel: 0
    features: ["area", "aspect_ratio"]
  fl:
    - channel: 1
      features: ["intensity_total"]
    - channel: 2
      features: ["particle_num"]
```

**Result**: All steps run, full CSV with PC + FL features.

### PC-Only Tracking

```yaml
channels:
  pc:
    channel: 0
    features: ["area"]
  fl: []  # No FL channels
```

**Result**: Background estimation skipped, CSV with PC features + base fields.

### Position/Bbox Tracking Only

```yaml
channels:
  pc:
    channel: 0
    features: []  # Empty features!
  fl: []  # No FL channels
```

**Result**: Background estimation skipped, CSV with only base fields.

## Output Files by Configuration

| Configuration | Background Files | CSV Features |
|---------------|-----------------|-------------|
| Full (PC+FL) | `fl_background_ch_{N}.npy` | PC + FL features |
| PC-only | (none) | PC features + base fields |
| Position-only | (none) | Base fields only |

## Use Cases

### Cell Movement Analysis

Configure PC channel with empty features to get position/bbox data:

```python
# You get this in traces.csv:
cell,frame,good,position_x,position_y,bbox_x0,bbox_y0,bbox_x1,bbox_y1
1,0,True,104.5,50.5,100,45,110,55
1,1,True,105.5,51.5,101,46,111,56
1,2,True,106.5,52.5,102,47,112,57
```

Perfect for trajectory analysis, velocity calculations, migration studies.

### Morphology Analysis

Add PC features like `area`, `aspect_ratio` to get shape data.

### Fluorescence Intensity Analysis

Configure FL channels with intensity features after background estimation.

## Implementation Details

The conditional skipping happens at the service level, not in the workflow orchestration:

1. **Service-level checks**: Each service checks channel requirements
2. **Early returns**: Services log messages and return if requirements not met
3. **Consistent API**: All services have the same interface, regardless of skipping
4. **Output caching**: Services also skip if their output already exists

This approach keeps the pipeline flexible while maintaining clean separation of concerns.

## File Format Details

For complete documentation of all file formats including the HDF5 structure, NumPy arrays, and CSV formats, see:

**📄 [File Formats Reference](file-formats.md)**

This includes:
- Complete HDF5 structure with dataset details
- NumPy array formats and memory-mapped access
- CSV column specifications  
- File size estimates and access patterns