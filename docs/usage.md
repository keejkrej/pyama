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

## Analysis
1. Load CSV (merged or inspected) → pick model (e.g. maturation) → Start Fitting
2. Quality panel: R² color coding, trace pagination by FOV
3. Parameter Analysis: histograms, scatter; Save All Plots
