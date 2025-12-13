# Merge Workflow

The merge workflow combines processed FOV results into sample-specific CSV files for analysis. This is essential when you have multiple experimental conditions or time points.

## When to Use Merge

- **Multiple experiments**: Different samples or conditions
- **Time series**: Different time points as separate samples
- **Technical replicates**: Multiple slides analyzed as separate samples
- **Spatial samples**: Different regions or positions

## Overview

1. **Assign FOVs to samples** - Define which FOVs belong to each sample
2. **Save sample configuration** - Create YAML file for reproducibility
3. **Configure merge paths** - Select input and output directories
4. **Run merge** - Generate per-sample CSV files
5. **Verify results** - Check merged files before analysis

## Step-by-Step Guide

### 1. Assign FOVs to Samples

**Using the Processing Tab:**

1. In the **Processing** tab, find the **Assign FOVs** section (right side)
2. Click **Add Sample** to create new rows
3. Fill in each row:
   - **Sample Name**: Descriptive name (e.g., `control`, `treatment`, `timepoint_1`)
   - **FOVs**: Range or list of FOV indices

**FOV Specification Formats:**

| Format | Example | Description |
|--------|---------|-------------|
| Single FOV | `5` | Individual FOV |
| Range | `0-10` | FOVs 0 through 10 (inclusive) |
| Multiple ranges | `0-5, 10-15` | Two separate ranges |
| Mixed | `0, 2, 4-7, 10` | Individual FOVs and ranges |

**Example Sample Assignments:**

```
Sample Name     | FOVs
---------------|---------
control_01     | 0-9
control_02     | 10-19
treatment_01   | 20-29
treatment_02   | 30-39
edge_control   | 95-99
```

**Managing Samples:**

- **Add Sample**: Creates new row for another sample
- **Remove Selected**: Deletes selected rows (check boxes to select)
- Rows can be edited by clicking directly in cells

### 2. Save Sample Configuration

1. After defining all samples, click **Save to YAML**
2. Choose a location and filename (e.g., `samples.yaml`)
3. **Why save YAML?**
   - Reuse for later analyses
   - Share with collaborators
   - Documentation of sample organization
   - Prevent mistakes in large projects

### 3. Configure Merge Settings

**File Path Configuration:**

1. **Sample YAML**:
   - Click **Browse** next to "Sample YAML:"
   - Select your saved `.yaml` file
   - Loaded samples appear in table

2. **Folder of processed FOVs**:
   - Click **Browse** next to "Folder of processed FOVs:"
   - Select directory containing `fov_000/`, `fov_001/`, etc.
   - Must be the same directory used for processing

3. **Output folder**:
   - Click **Browse** next to "Output folder:"
   - Choose where merged CSVs will be saved
   - Usually same as processing directory for organization

**Verification:**

- Check that all sample paths exist
- Verify FOV ranges don't overlap
- Ensure output directory has write permissions

### 4. Run Merge

1. Verify all paths are correct
2. Click **Run Merge** button
3. Progress appears:
   - Status message updates
   - Processing shows current sample
4. Completion:
   - "Merge completed successfully"
   - Shows location of created files

### 5. Verify Results

**Check Created Files:**

1. Navigate to output directory
2. Verify files exist:
   ```
   output_dir/
   ├── control_01_merged.csv
   ├── control_02_merged.csv
   ├── treatment_01_merged.csv
   ├── treatment_02_merged.csv
   └── edge_control_merged.csv
   ```

3. Spot-check files:
   - Open in spreadsheet software
   - Verify expected number of cells
   - Check FOV values in data

**CSV Format:**

```csv
fov,cell,frame,good,position_x,position_y,area_ch_0,intensity_total_ch_1
0,0,0,True,100.5,200.3,450,1234.5
0,0,1,True,101.2,199.8,455,1356.2
...
```

- **fov**: Original FOV index (preserved for reference)
- **cell**: Cell ID within original FOV
- **frame**: Time frame index
- **good**: Quality flag from Visualization tab
- **position_x/y**: Cell centroid coordinates
- **area_ch_X**: Morphological features from phase contrast
- **intensity_*_ch_X**: Fluorescence features

## Advanced Usage

### Using Inspected Data

If you performed quality control in the Visualization tab:

1. Save inspected CSV: `traces_inspected.csv`
2. Run merge with inspected file
3. Only "good" traces will be included in merged results

**Benefit**: Higher quality data for fitting, as bad traces are excluded

### Batch Processing Multiple Experiments

For multiple experiments:

1. Process all experiments to separate folders
2. Create separate sample YAML for each experiment
3. Run merge for each experiment
4. Combine all CSVs in Analysis tab if needed

### FOV Verification

Before merging:

```bash
# Check available FOVs
ls your_processing_folder/ | grep "fov_"

# Should show: fov_000, fov_001, ..., fov_099
```

Ensure your YAML ranges match existing FOVs to avoid errors.

## YAML File Format

**Example `samples.yaml`:**

```yaml
samples:
  - name: control
    fovs: "0-10"
  - name: treatment
    fovs: "11-20"
  - name: timepoint_1
    fovs: "0, 5, 10-15"
  - name: timepoint_2
    fovs: "16-25"
```

**Manual Editing:**

- Can edit YAML in text editor
- Follow format exactly (dashes, spaces)
- FOV strings use same specification as UI

## Best Practices

### Sample Naming

- Use descriptive, consistent names
- Include time points or conditions
- Avoid spaces (use underscores or hyphens)
- Examples:
  - `cell_line_A_time0`
  - `experiment_1_dose_10uM`
  - `replicate_1`

### FOV Assignment

1. **Keep biological samples together**:
   - Same slide/experiment = different time points may be separate samples
   - Technical replicates = separate samples
   
2. **Maintain spatial context**:
   - Edge FOVs often have different behavior
   - Consider edge effects in biology
   
3. **Balance sample sizes**:
   - Similar number of cells per sample
   - Adjust if natural variation exists

### File Organization

```
experiment_2024_01/
├── raw/
│   └── *.nd2 files
├── processing/
│   ├── samples.yaml
│   ├── processing_config.yaml
│   ├── fov_000/
│   ├── fov_001/
│   └── ...
└── merged/
    ├── control_01_merged.csv
    ├── treatment_01_merged.csv
    └── samples.yaml  # copy for reference
```

## Troubleshooting

### Common Errors

**"Specified FOV range is invalid":**
- Check if FOV numbers exist (0-based indexing)
- Verify no negative numbers
- Ensure no overlaps between samples

**"CSV file not found for FOV X":**
- Verify processing completed for that FOV
- Check `fov_X/traces.csv` exists
- Re-run processing if needed

**"Output directory not accessible":**
- Check directory permissions
- Ensure path exists
- Try different output location

### Recovery Strategies

**Merge Failed Partially:**

1. Check which files were created
2. Identify problematic sample in YAML
3. Remove or fix problematic assignment
4. Run merge again

**Wrong Sample Assignment:**

1. Edit YAML file to correct assignments
2. Delete incorrect merged files
3. Run merge with updated YAML

## Command Line Alternative

For batch processing or automation:

```bash
# Using pyama-air CLI
pyama-air cli merge
```

Prompts for:
- Sample definitions (same format as GUI)
- Input directory path
- Output directory path

## Next Steps

- Load merged CSVs in Analysis tab for fitting
- Compare parameters across conditions
- Use consistent naming for downstream analysis

The merge workflow is crucial for organizing your data before statistical analysis. Take care to document your sample assignments for reproducible science.
