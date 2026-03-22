# PyAMA Core

Core processing library. Use via `pyama-gui`, `pyama-cli`, or import it directly in scripts. Install with `uv sync` from the workspace root.

## APIs
- **I/O**: `pyama.io.load_microscopy_file`, `pyama.io.load_analysis_csv`, `pyama.io.scan_processing_results`
- **Tasks facade**: `pyama.tasks.submit_processing`, `submit_merge`, `submit_model_fit`, `submit_statistics`, `submit_visualization`, `subscribe`, `unsubscribe`
- **Internal processing config**: `pyama.types.processing.{Channels, ProcessingParams, ProcessingConfig}`
- **Merge helpers**: `pyama.apps.processing.service.run_merge`, `pyama.apps.processing.service.run_merge_traces`
- **Modeling**: `pyama.apps.modeling.service.fit_csv_file`, `pyama.apps.modeling.models.{get_model, list_models}`
- **Statistics**: `pyama.apps.statistics.discovery.discover_sample_pairs`, `pyama.apps.statistics.service.run_folder_statistics`
- **Features**: `pyama.apps.processing.extract.list_phase_features`, `list_fluorescence_features`

## Workflow
Copying → Segmentation (LOG-STD) → Tracking (IoU) → Background → ROI → Extraction.

`ProcessingParams` now only controls `positions`, `n_workers`, `background_weight`, `background_min_samples`, and `copy_only`. Segmentation and tracking use the built-in LOG-STD and IoU implementations.

| Step | Output |
|------|--------|
| 1. Copying | `raw.zarr` |
| 2. Segmentation / Tracking / Background | datasets under `raw.zarr` |
| 3. ROI extraction staging | `rois.zarr` |
| 4. Per-position traces | `traces/position_*.csv` |
| 5. Merged sample traces | `traces_merged/*.csv` |

The workflow also writes `processing_config.yaml` at the project root. Trace CSVs are frame-based. Merged analysis CSVs use canonical columns `frame,position,roi,value`, and `load_analysis_csv()` derives `time_min` from a configurable frame interval (default 10 minutes).

## Extending
- **Features**: register built-ins in `pyama.apps.processing.extract`; current built-ins are `area` and `intensity_total`
- **Models**: register built-ins in `pyama.apps.modeling.models.__init__`; `base` is the built-in model

See `pyama/tests/test_tasks.py`, `pyama/tests/test_statistics.py`, and `pyama/tests/test_merge.py`.
