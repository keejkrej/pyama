# PyAMA-Core

Core processing library. Use via PyAMA-Pro or import in scripts. Install: `uv sync` from root (or `uv pip install -e pyama/` standalone).

## APIs
- **I/O**: `load_microscopy_file`, `get_microscopy_frame`, `load_analysis_csv`, `scan_processing_results`
- **Tasks**: `submit_processing`, `submit_merge`, `submit_model_fit`, `submit_statistics`, `submit_visualization`, `subscribe`, `unsubscribe`
- **Workflow types**: `ProcessingContext`, `ChannelSelection`, `Channels` from `pyama.types.processing`
- **Merge**: `run_merge(samples, processing_results_dir)` for synchronous library callers
- **Modeling**: `fit_model`, `get_model`, `list_models` from `pyama.modeling` (`base` is the built-in model)
- **Statistics**: `discover_sample_pairs`, `run_folder_statistics` from `pyama.statistics`
- **Features**: `list_phase_features`, `list_fluorescence_features` from `pyama.apps.processing.extract` – built-in: `area`, `intensity`

## Workflow
Copying → Segmentation (LOG-STD) → Correction → Tracking (IoU) → Extraction.

| Step | Output |
|------|--------|
| 1. Copying | `*_pc_ch_*.npy`, `*_fl_ch_*.npy` |
| 2. Segmentation | `*_seg_ch_*.npy` |
| 3. Correction | `*_fl_background_ch_*.npy` |
| 4. Tracking | `*_seg_labeled_ch_*.npy` |
| 5. Extraction | `*_traces.csv` |

Output: `fov_XXX/` dirs containing traces and channel arrays. Trace CSVs are frame-based; merged analysis CSVs use `frame,fov,cell,value`, and analysis/modeling/statistics derive minute time from a configurable frame interval (default 10 minutes). Copying sequential per batch; steps 2–5 parallel. Filtering: min 30 frames, 50px border.

## Extending
- **Features**: `extract_*(ctx) -> float`; register built-ins in `pyama.apps.processing.extract`
- **Models**: `Params`, `Bounds`, `DEFAULTS`, `BOUNDS`, `eval`; register built-ins in the package `__init__.py`

See `tests/test_workflow.py`, `tests/test_merge.py`.
