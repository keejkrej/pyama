# GUI Usage

## Workflow
1. Start in `Welcome`, set a workspace folder, and choose an ND2/CZI microscopy file
2. Open `Alignment` and save `bbox/Pos{position_id}.csv` for the positions you want to process
3. Open `Processing`, pick phase-contrast and fluorescence features, then adjust `position_start`, `position_end`, `n_workers`, and `background_weight` if needed
4. Click `Start` to run the workflow into the workspace; use the sample table to define merge groups
5. Save or load `samples.yaml` as needed, then click `Run` in the Merge section to write merged sample CSVs to `traces_merged/`

## Visualization
1. Optional: load a processing output folder after the core workflow
2. Load Folder (processing output dir) → pick FOV and channels → Start Visualization
3. For ROI-backed workspaces, select a trace/ROI to browse its cropped image stack
4. Navigate frames; select traces; right-click to mark good/bad
5. Save Inspected CSV before merging

## Modeling
1. Optional: load a merged or inspected CSV after the core workflow
2. Load CSV (merged or inspected) → pick model (`base`) → set time interval in minutes
3. In the parameter editor, choose preset-backed fixed values such as protein degradation from the dropdown, then start fitting
4. Quality panel: R² color coding, trace pagination by position
5. Parameter Analysis only shows parameters of interest, such as Time Onset and mRNA Degradation Rate; Save All Plots as needed

## Statistics
1. Load a `traces_merged` folder containing matched frame-based `*_intensity_total_c1.csv` and `*_area_c0.csv` files
2. Set the time interval and onset window in minutes, then pick `AUC` or `Onset`
3. Run statistics across all discovered samples
4. Inspect per-sample normalized traces and compare sample distributions in the boxplot view
