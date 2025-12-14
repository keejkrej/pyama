# Quick Start

This guide gets you started with PyAMA for basic microscopy image analysis.

## 1. Launch PyAMA-Qt

```bash
# From the repository root
uv run pyama-qt
```

The Qt GUI will open with three main tabs: **Processing**, **Visualization**, and **Analysis**.

## 2. Process Your Data

### Load Microscopy File

1. Switch to the **Processing** tab
2. Click **Browse** next to "Microscopy File:" and select your ND2 file
3. The filename will appear once loaded

### Configure Channels

1. **Phase Contrast**: 
   - Select the phase contrast channel from the dropdown
   - Multi-select features (Ctrl+Click) like `area`, `aspect_ratio`

2. **Fluorescence** (if applicable):
   - Select a fluorescence channel
   - Select a feature from the feature dropdown
   - Click **Add** to include it
   - Repeat for additional channels

### Set Output Folder

Click **Browse** next to "Save Directory:" and choose where results will be saved.

### Run Workflow

Click **Start Complete Workflow**. Progress will be shown in the status bar.

## 3. Visualize Results (Optional)

1. Switch to the **Visualization** tab
2. Click **Load Folder** and select your processing output directory
3. Select FOV number and channels (e.g., `pc_xxx`, `seg_labeled_xxx`, `fl_background_xxx`)
4. Click **Start Visualization**
5. Navigate frames using the navigation buttons
6. Inspect traces by clicking trace IDs in the list
7. Right-click traces to toggle quality (good/bad)

## 4. Merge Multiple Samples

If you processed multiple FOVs:

1. In the **Processing** tab, find the **Assign FOVs** section
2. Click **Add Sample** and enter sample names with FOV ranges (e.g., `sample1`, `0-5`)
3. Click **Save to YAML** to save the sample definitions
4. In the merge section:
   - Load the sample YAML file
   - Select the folder with processed FOVs
   - Select the output directory
5. Click **Run Merge** to create merged CSV files

## 5. Analyze Traces

1. Switch to the **Analysis** tab
2. Click **Load CSV** and select your merged traces file
3. Select a model (e.g., `maturation`)
4. Adjust parameters if needed
5. Click **Start Fitting**
6. Review results in the quality and parameter panels
7. Save plots using **Save All Plots**

## Common Workflows

### Quick Analysis Workflow

1. Load ND2 file
2. Select phase contrast channel with `area` feature
3. Select 1-2 fluorescence channels with `intensity_total`
4. Run complete workflow
5. Load results in Analysis tab
6. Fit with default model
7. Export plots

### Quality Control Workflow

1. Run processing as above
2. Load results in Visualization tab
3. Inspect traces, mark problematic ones as "bad"
4. Save inspected CSV
5. Load inspected CSV in Analysis for fitting

### Multi-Sample Workflow

1. Process all FOVs for all samples
2. Create sample assignments in FOV Assign section
3. Save to YAML file
4. Run merge to create per-sample CSVs
5. Load and analyze each sample separately

## Tips

- **File Organization**: Keep all related files in one directory per experiment
- **Batch Processing**: Adjust `batch_size` and `n_workers` based on your CPU cores
- **Background Correction**: Set `background_weight` between 0 (no correction) and 1 (full correction)
- **Quality First**: Always use Visualization tab before merging to ensure data quality
- **Save Often**: Save sample YAML files for reuse across experiments

## Next Steps

- Read the detailed [User Guide](../user-guide/) for comprehensive information
- Check the [Package Documentation](../packages/) for specific components
- Visit the [Reference section](../reference/) for technical details
