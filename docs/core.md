# PyAMA-Core

Core processing library. Use via PyAMA-Pro or import in scripts. Install: `uv sync` from root (or `uv pip install -e pyama-core/` standalone).

## APIs
- **I/O**: `load_microscopy_file`, `get_microscopy_frame`, `load_analysis_csv`, `load_processing_results_yaml`
- **Workflow**: `run_complete_workflow(metadata, context, fov_start, fov_end, batch_size, n_workers)` – `ProcessingContext`, `ChannelSelection`, `Channels` from `pyama_core.types.processing`
- **Merge**: `run_merge(sample_yaml, processing_results_yaml, output_dir)`
- **Modeling**: `fit_model`, `get_model`, `list_models` from `pyama_core.modeling`
- **Statistics**: `discover_sample_pairs`, `run_folder_statistics` from `pyama_core.statistics`
- **Features**: `list_phase_features`, `list_fluorescence_features` – built-in: `area`, `intensity`

## Workflow
Copying → Segmentation (LOG-STD) → Correction → Tracking (IoU) → Extraction.

| Step | Output |
|------|--------|
| 1. Copying | `*_pc_ch_*.npy`, `*_fl_ch_*.npy` |
| 2. Segmentation | `*_seg_ch_*.npy` |
| 3. Correction | `*_fl_background_ch_*.npy` |
| 4. Tracking | `*_seg_labeled_ch_*.npy` |
| 5. Extraction | `*_traces.csv` |

Output: `processing_results.yaml` + `fov_XXX/` dirs. Copying sequential per batch; steps 2–5 parallel. Filtering: min 30 frames, 50px border.

## Extending
- **Features**: `extract_*(ctx) -> float`; register built-ins in the package `__init__.py`
- **Models**: `Params`, `Bounds`, `DEFAULTS`, `BOUNDS`, `eval`; register built-ins in the package `__init__.py`

See `tests/test_workflow.py`, `tests/test_merge.py`.


