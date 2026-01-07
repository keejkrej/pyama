# Processing Tab

The Processing tab handles the complete microscopy image analysis workflow, from loading ND2 files to extracting cell traces.

## Workflow Overview

1. **Load Microscopy File** - Browse and select your ND2 file
2. **Configure Channels** - Select phase contrast and fluorescence channels with features
3. **Set Output Folder** - Choose where to save processing results
4. **Configure Parameters** (optional) - Adjust FOV range, batching, and workers
5. **Run Workflow** - Execute the complete processing pipeline
6. **Merge Results** (optional) - Combine multiple samples into merged CSVs

## Step-by-Step Guide

### 1. Load Microscopy File

1. Click **Browse** next to "Microscopy File:"
2. Select your ND2 file
3. The filename appears once loaded successfully

### 2. Configure Channels

**Phase Contrast Channel:**

1. Select the phase contrast channel from the dropdown
2. In the "Phase Contrast Features" list, multi-select (Ctrl+Click or Shift+Click) the features you want
   - Common features: `area`, `aspect_ratio`

**Fluorescence Channels:**

1. Select a fluorescence channel from the dropdown
2. Select a feature from the feature dropdown
3. Click **Add** to add the channel-feature combination
4. Repeat for additional channels
5. To remove: select in "Fluorescence Features" list and click **Remove Selected**

### 3. Set Output Folder

1. Click **Browse** next to "Save Directory:"
2. Select where processed results will be saved
3. This directory will contain:
   - `processing_config.yaml` - Configuration metadata
   - `fov_XXX/` folders - Per-FOV processing results
   - Merged CSVs (if you use the merge feature)

### 4. Configure Parameters (Optional)

Check **Set parameters manually** to show advanced options:

- **fov_start**: Starting FOV index (default: 0)
- **fov_end**: Ending FOV index (default: -1, uses last FOV)
- **batch_size**: FOVs per batch (default: 2, increase for faster processing)
- **n_workers**: Parallel threads (default: 2, match to CPU cores)
- **background_weight**: Fluorescence background correction (0-1 range)
  - 0.0 = no correction
  - 1.0 = full background subtraction  
  - Values between 0 and 1 apply partial correction

### 5. Run Workflow

1. Click **Start Complete Workflow**
2. Progress bar appears during processing
3. Click **Cancel** to stop if needed
4. Status message shows completion

**Processing Steps:**
1. **Copying** - Extract frames from ND2 to NPY format
2. **Segmentation** - Cell segmentation using phase contrast
3. **Correction** - Background estimation for fluorescence
4. **Tracking** - Track cells across time points
5. **Extraction** - Generate feature traces to CSV

### 6. Assign FOVs to Samples (for Multiple Samples)

1. In the **Assign FOVs** section (right side):
   - Click **Add Sample** to create a new row
   - Enter a sample name (e.g., `sample1`)
   - Enter FOV range (e.g., `0-5` for FOVs 0 through 5)
   - Use format `0, 2, 4-6` for non-consecutive FOVs
2. Use **Remove Selected** to delete rows
3. Click **Save to YAML** to save sample definitions

### 7. Merge Processing Results

1. Click **Browse** next to **Sample YAML:** and load your samples file
2. Click **Browse** next to **Folder of processed FOVs:** - select your processing output
3. Click **Browse** next to **Output folder:** - where merged CSVs will be saved
4. Click **Run Merge**
5. Merged CSVs are created with sample names

## Output Structure

After processing, your output directory contains:

```
output_dir/
├── processing_config.yaml           # Metadata and parameters
├── samples.yaml                     # Sample assignments (if created)
├── sample1_merged.csv               # Merged results (if merged)
├── sample2_merged.csv
├── fov_000/                         # Per-FOV results
│   ├── basename_fov_000_pc_ch_0.npy         # Raw phase contrast
│   ├── basename_fov_000_fl_ch_1.npy         # Raw fluorescence
│   ├── basename_fov_000_seg_labeled_ch_0.npy        # Labeled segmentation (untracked)
│   ├── basename_fov_000_seg_tracked_ch_0.npy# Tracked cell IDs
│   ├── basename_fov_000_fl_background_ch_1.npy# Background estimate
│   └── basename_fov_000_traces.csv          # Feature traces
├── fov_001/
└── ...
```

## Tips and Tricks

- **Start Small**: Process 1-2 FOVs first to verify parameters
- **Check Memory**: Large datasets may need smaller batch sizes
- **Monitor Progress**: Watch status messages for each processing stage
- **Cancel Safely**: Canceling preserves completed FOVs
- **Reuse Configs**: Save sample YAML files for consistent batch processing

## Common Issues

**"Workflow cancelled" appears immediately:**
- Check if output directory has write permissions
- Verify ND2 file exists and is readable
- Reduce batch_size if memory is limited

**Fewer cells detected than expected:**
- Check phase contrast channel selection
- Verify cell features are selected
- Consider adjusting segmentation parameters (advanced)

**Fluorescence traces are all zero:**
- Ensure fluorescence channels are configured
- Verify fluorescence features are added to queue
- Check background_weight isn't set to 1.0 with weak signal

## Next Steps

- Use the **Visualization Tab** to inspect your results
- Load merged CSVs in the **Analysis Tab** for model fitting
- See [Visualization Tab Guide](visualization-tab.md) for quality control
