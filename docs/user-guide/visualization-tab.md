# Visualization Tab

The Visualization tab allows you to inspect processed microscopy images and cell traces, perform quality control, and save filtered results for analysis.

## Workflow Overview

1. **Load Project** - Load processing results directory
2. **Configure Visualization** - Select FOV and channels to display
3. **Navigate Images** - Browse through time points
4. **Inspect Traces** - Review and quality-filter cell traces
5. **Save Results** - Export inspected traces with quality flags

## Step-by-Step Guide

### 1. Load Project

1. Click **Load Folder** button
2. Select the folder containing processing results (same as "Save Directory" from Processing tab)
3. Status bar shows: "X FOVs loaded from [directory]"
4. Project details display:
   - Total FOV count
   - Available data types (channels)
   - Image dimensions

### 2. Configure Visualization

**Select FOV:**

- Use the **FOV** spinbox (range: 0 to max_FOV-1)
- Each FOV contains independent cell traces

**Select Channels:**

1. Multi-select channels from the channel list
2. Common selection for full inspection:
   - `pc_xxx` - Raw phase contrast
   - `seg_labeled_xxx` Segmented/tracked cells with IDs
   - `fl_background_xxx` - Background-corrected fluorescence
3. Notice channel suffixes (`ch_0`, `ch_1`) - only load needed channels
4. **Start Visualization** button enables when channels are selected

### 3. Start Visualization and Navigate

1. Click **Start Visualization** button
2. Progress bar shows "Loading visualization data..."
3. Once complete, status shows "FOV loaded successfully"
4. **Image Controls:**
   - **Data Type dropdown**: Switch between loaded channels
   - **Frame navigation**: `<<` `prev_10` `<` `prev` `next` `>` `next_10` `>>`
   - **Frame label**: Shows current position (e.g., "Frame 1/100")

**Image Display:**
- Image updates when changing data types or frames
- Title shows current data type and frame number
- Rendering adapts to data type (binary masks, raw intensity, etc.)

### 4. Inspect Traces

**Load Traces:**

1. Traces automatically load after visualization
2. **Feature dropdown**: Select which feature to plot
   - Common: `intensity_total`, `area`, `aspect_ratio`
3. Trace plot appears with all traces overlayed
4. Mean trace shown as thick line

**Navigate Traces:**

1. Trace list shows 10 traces per page (paginated)
2. Traces are color-coded:
   - **Blue**: Good quality (default)
   - **Green**: Bad quality (hidden from plot)
   - **Red**: Currently active/selected trace

**Select and Inspect Traces:**

1. Click trace IDs in the list to select them
   - Selected trace turns red in list
   - Red circle overlay appears on image showing cell position
2. Right-click trace IDs to toggle quality (good/bad)
   - Bad traces turn green and hide from plot
3. Click on trace overlays in image to select trace by position

**Quality Control:**

1. Review each trace for:
   - Physically realistic behavior
   - Correct tracking (no sudden jumps)
   - Stable background levels
2. Mark problematic traces as "bad" (right-click)
3. Use pagination controls to browse all traces in current FOV
4. Page label shows current page (e.g., "Page 1/15")

### 5. Save Inspected Results

1. After reviewing traces, click **Save Inspected CSV**
2. File saves with `_inspected` suffix (e.g., `traces_inspected.csv`)
3. Status shows: "filename.csv saved to [directory]"
4. The inspected file includes quality information:
   - `good` column indicates trace quality
   - Only "good" traces will be included in merged results
5. Reload project to load inspected file automatically

## Quality Control Guidelines

### When to Mark Traces as Bad

**Tracking Errors:**
- Sudden position jumps indicating ID swaps
- Traces that merge/split incorrectly

**Segmentation Issues:**
- Cells on image edges (border effects)
- Extremely large or small areas (wrong segmentation)
- Intensity spikes or drops (background artifacts)

**Biological Outliers:**
- Cell death events (sudden intensity loss)
- Division events (sudden area increase) - mark if analyzing single cells
- Debris or artifacts mistaken for cells

### Systematic QC Workflow

1. **First Pass - Quick Scan:**
   - Load all FOVs sequentially
   - Mark obviously bad traces
   - Note patterns (e.g., all traces on edges)

2. **Detailed Review:**
   - Focus on FOVs with many bad traces
   - Check feature plausibility
   - Verify fluorescence baseline stability

3. **Final Check:**
   - Save inspected file
   - Load in Analysis tab
   - Verify data quality before fitting

## Output Files

**Standard Traces CSV:**
```csv
fov,cell,frame,good,position_x,position_y,area_ch_0,intensity_total_ch_1
0,0,0,True,100.5,200.3,450,1234.5
0,0,1,True,101.2,199.8,455,1356.2
```

**Inspected Traces CSV:**
Same format with updated `good` column based on your QC.

## Tips and Optimization

**Performance:**
- Select fewer channels if loading is slow
- Use `prev_10`/`next_10` for quick browsing
- Large datasets: QC a subset first

**Quality Assessment:**
- Use feature plots to spot anomalies visually
- Cross-reference multiple features for the same cell
- Pay attention to edge cells (often problematic)

**Workflow Efficiency:**
- Save often if doing extensive QC
- Document your QC criteria for reproducibility
- Consider creating a QC checklist for your experiment

## Troubleshooting

**"No traces found":**
- Verify you loaded the correct directory
- Check that processing completed successfully
- Look for trace CSV files in output folders

**Image doesn't load:**
- Ensure channels are selected before clicking "Start Visualization"
- Check if required NPY files exist in FOV folders
- Try loading fewer channels

**Traces appear disconnected:**
- This is normal for fragmented tracking
- Mark badly fragmented traces as "bad"
- Consider adjusting tracking parameters in new processing run

## Next Steps

- Use **Save Inspected CSV** to preserve your quality decisions
- Load the inspected file in the Analysis tab for model fitting
- See [Merge Workflow](merge-workflow.md) to combine multiple samples

The Visualization tab is crucial for ensuring data quality before analysis. Take time to properly QC your traces for reliable fitting results.
