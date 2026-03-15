# GUI Usage

## Processing
1. Browse ND2 → pick PC channel + features → add FL channel-feature pairs → set save dir
2. Optionally enable manual params (fov_range, batch_size, n_workers, background_weight)
3. Start Complete Workflow; use Assign FOVs → Save to YAML for merge
4. Merge: load samples.yaml + processing_results.yaml → Run Merge

## Visualization
1. Load Folder (processing output dir) → pick FOV and channels → Start Visualization
2. Navigate frames; select traces; right-click to mark good/bad
3. Save Inspected CSV before merging

## Modeling
1. Load CSV (merged or inspected) → pick model (e.g. maturation) → Start Fitting
2. Quality panel: R² color coding, trace pagination by FOV
3. Parameter Analysis: histograms, scatter; Save All Plots

## Statistics
1. Load a `merge_output` folder containing matched `*_intensity_ch_1.csv` and `*_area_ch_0.csv` files
2. Pick `AUC` or `Onset` and run statistics across all discovered samples
3. Inspect per-sample normalized traces and compare sample distributions in the boxplot view

