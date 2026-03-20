# GUI Usage

## Processing
1. Browse ND2 → pick PC channel + features → add FL channel-feature pairs → set save dir
2. Optionally enable manual params (fov_range, batch_size, n_workers, background_weight)
3. Start Complete Workflow; use Assign FOVs → Save to YAML for merge
4. Merge: load samples.yaml + processing output folder → Run Merge

## Visualization
1. Load Folder (processing output dir) → pick FOV and channels → Start Visualization
2. Navigate frames; select traces; right-click to mark good/bad
3. Save Inspected CSV before merging

## Modeling
1. Load CSV (merged or inspected) → pick model (`base`) → set time interval in minutes
2. In the parameter editor, choose preset-backed fixed values such as protein degradation from the dropdown, then start fitting
3. Quality panel: R² color coding, trace pagination by FOV
4. Parameter Analysis only shows parameters of interest, such as Time Onset and mRNA Degradation Rate; Save All Plots as needed

## Statistics
1. Load a `merge_output` folder containing matched frame-based `*_intensity_ch_1.csv` and `*_area_ch_0.csv` files
2. Set the time interval and onset window in minutes, then pick `AUC` or `Onset`
3. Run statistics across all discovered samples
4. Inspect per-sample normalized traces and compare sample distributions in the boxplot view
