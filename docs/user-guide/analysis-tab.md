# Analysis Tab

The Analysis tab allows you to fit mathematical models to cell trace data, evaluate fitting quality, and analyze parameter distributions.

## Workflow Overview

1. **Load Data** - Load trace CSV files (merged or inspected)
2. **Select Model** - Choose and configure fitting model
3. **Run Fitting** - Execute model fitting on all traces
4. **Review Results** - Evaluate fits and quality metrics
5. **Analyze Parameters** - Explore parameter distributions
6. **Export Results** - Save fits and plots

## Step-by-Step Guide

### 1. Load Data

**Primary Data:**
1. Click **Load CSV** button
2. Select merged traces CSV or inspected traces CSV
3. All traces plot with mean overlay
4. Title shows: "All Sequences (X cells)" where X is total cells

**Optional: Load Previous Fits**
1. Click **Load Fitted Results** button
2. Select fitted results CSV (e.g., `traces_fitted_maturation.csv`)
3. Model dropdown automatically updates to match saved model
4. Parameter table loads saved parameters
5. Allows reviewing or comparing previous analysis

### 2. Select Model

1. In the **Fitting** section, select a **Model** from dropdown:
   - **`trivial`** - Constant model for testing
   - **`maturation`** - Exponential maturation model
   - **`maturation_blocked`** - Maturation with production blocking

2. Parameter table updates automatically with default values:
   - **Parameter name** (e.g., `amplitude`, `rate`, `offset`)
   - **Lower bound** - Minimum allowed value
   - **Upper bound** - Maximum allowed value
   - **Current value** - Initial guess for fitting

3. **Manual Parameter Mode:**
   - Check **Set parameters manually** checkbox
   - Edit parameter values and bounds in the table
   - Useful for:
     - Constrained fitting
     - Testing different initial conditions
     - Domain-specific parameter ranges

### 3. Run Fitting

1. Ensure data is loaded and model is selected
2. Click **Start Fitting** button
3. Progress bar shows: "Fitting analysis models..."
4. Completion messages:
   - Status: "Fitting completed successfully"
   - File location: "filename_fitted_model.csv saved to [directory]"

**During Fitting:**
- Each cell trace is fitted independently
- Progress updates show current cell/total cells
- Can be cancelled if needed

### 4. Review Results

**Fitting Quality Panel (Middle):**

1. **Quality Statistics** (top label):
   - **Good**: R² > 0.9 fits (green percentage)
   - **Mid**: 0.7 < R² ≤ 0.9 fits (yellow percentage)
   - **Bad**: R² ≤ 0.7 fits (red percentage)

2. **Trace Selection List:**
   - Groups traces by FOV
   - Color-coded by quality:
     - Green: Good fits (R² > 0.9)
     - Orange: Mid fits (0.7 < R² ≤ 0.9)
     - Red: Poor fits (R² ≤ 0.7)
   - Use **Previous**/**Next** buttons to browse FOVs
   - Click individual traces to view details

3. **Fitted Traces Plot:**
   - Shows raw data (blue line) and fitted curve (red)
   - Title includes: cell ID, model type, R², fit status
   - Use **Show Random Trace** to explore different cells

**Inspecting Individual Fits:**

1. Click on a trace in the list
2. Plot updates to show that specific cell
3. Check text below plot for:
   - Cell ID and FOV
   - Model parameters
   - Goodness of fit metrics

### 5. Analyze Parameters

**Parameter Analysis Panel (Right):**

1. **Single Parameter Analysis:**
   - Select parameter from dropdown
   - Histogram shows parameter distribution
   - Title: "Distribution of [parameter_name]"
   - Check **Good fits only** to filter high-quality fits

2. **Double Parameter Analysis:**
   - Select X and Y parameters from dropdowns
   - Scatter plot shows parameter correlations
   - Title: "Scatter Plot: X vs Y"
   - Useful for finding parameter relationships

3. **Parameter Insights:**
   - Look for multimodal distributions
   - Identify outlier populations
   - Correlate parameters with biology

### 6. Export Results

**Save Analysis Results:**

1. **Fitted Results CSV** - Saved automatically
   - Contains all fit results with parameters
   - Naming: `basename_fitted_modelname.csv`
   - Includes: fov, cell, model_type, success, r_squared, parameters

2. **Save All Plots:**
   - Click **Save All Plots** button
   - Select output directory
   - Exports:
     - Parameter histograms (one per parameter)
     - Parameter scatter plots (all combinations)
     - 300 DPI resolution for publications

**CSV Format:**
```csv
fov,cell,model_type,success,r_squared,amplitude,rate,offset
0,0,maturation,True,0.95,1.234,0.567,0.123
0,1,maturation,True,0.88,2.345,0.678,0.234
```

## Model Descriptions

### Trivial Model
$$f(t) = A \cdot + B$$
- **Purpose**: Testing, baseline comparison
- **Parameters**: amplitude (A), offset (B)
- **Use Case**: Verify fitting pipeline works

### Maturation Model
$$f(t) = A \cdot (1 - e^{-kt}) + B$$
- **Purpose**: Protein maturation kinetics
- **Parameters**: amplitude (A), rate (k), offset (B)
- **Use Case**: Fluorescent protein production curves

### Maturation Blocked Model
$$f(t) = A \cdot e^{-kt} + B$$
- **Purpose**: Protein degradation/no production
- **Parameters**: amplitude (A), rate (k), offset (B)
- **Use Case**: Chase experiments, protein turnover

## Quality Guidelines

### Good Fits (R² > 0.9)
- Curve follows data closely
- Residuals are random and small
- Parameters are physically reasonable

### Mid-Quality Fits (0.7 < R² ≤ 0.9)
- General trends captured
- Some systematic deviation
- May need parameter adjustment

### Poor Fits (R² ≤ 0.7)
- Model doesn't describe data
- Consider:
  - Different model
  - Data preprocessing
  - Biological complexity

### Parameter Validation

1. **Check Reasonable Ranges:**
   - Maturation rates: 0.01 - 1.0 hour⁻¹
   - Amplitudes: positive for production
   - Offsets: non-zero baseline

2. **Identify Outliers:**
   - Extreme parameter values
   - Poor R²
   - Negative amplitudes/rates

3. **Biological Validation:**
   - Match known kinetics
   - Compare across conditions
   - Check for population shifts

## Advanced Features

### Reusing Fits

- Load previous fitted results
- Compare different models
- Batch analyze multiple conditions

### Parameter Constraints

- Use manual parameter mode for constraints
- Apply biological knowledge to bounds
- Test parameter sensitivity

### Batch Analysis

1. Load and fit multiple datasets
2. Save results to consistent naming
3. Compare parameter distributions
4. Export for statistical analysis

## Tips and Best Practices

**Before Fitting:**
- Ensure traces are properly QC'd in Visualization tab
- Check time units are consistent
- Verify data preprocessing needs

**During Fitting:**
- Start with default parameters
- Adjust bounds if fitting fails
- Monitor progress for early warnings

**After Fitting:**
- Always review fit quality distribution
- Check parameter distributions for outliers
- Document any manual parameter adjustments

**For Publications:**
- Use "Good fits only" for main figures
- Save high-resolution plots
- Include fit quality metrics in methods

## Troubleshooting

**"Fitting failed for many cells":**
- Check data quality in Visualization tab
- Relax parameter bounds
- Try different initial values
- Verify model choice matches data

**Parameter distribution is unrealistic:**
- Check for outliers
- Verify unit consistency
- Consider biological constraints
- Review data preprocessing**

## Next Steps

- Export plots for your figures
- Compare parameters across experimental conditions
- Use fitted results in statistical analysis
- See the [Reference](../reference/) section for technical details

The Analysis tab turns raw traces into quantitative parameters that describe your biological system. Take time to validate fits and understand parameter meanings for your specific application.
