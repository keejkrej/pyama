# PyAMA Core

Core processing library. Use via `pyama-gui` or import it directly in scripts. Install with `uv sync` from the workspace root.

## APIs
- **I/O**: `pyama.io.load_microscopy_file`, `pyama.io.load_analysis_csv`, `pyama.io.scan_processing_results`
- **Async jobs**: `pyama.tasks.submit_processing`, `submit_merge`, `submit_model_fit`, `submit_statistics`, `get_task`, `cancel_task`, `subscribe`, `unsubscribe`
- **Internal processing config**: `pyama.types.processing.{Channels, ProcessingParams, ProcessingConfig}`
- **Sync helpers**: import directly from `pyama.io.*` and `pyama.apps.*` instead of routing through `pyama.tasks`
- **Merge helpers**: `pyama.apps.processing.merge.normalize_samples`, `parse_positions_field`, `run_merge_traces`
- **Modeling**: `pyama.apps.modeling.service.fit_csv_file`, `pyama.apps.modeling.models.{get_model, list_models}`
- **Statistics**: `pyama.io.samples.discover_statistics_sample_pairs`, `pyama.apps.statistics.service.run_folder_statistics`
- **Features**: `pyama.apps.processing.extract.list_phase_features`, `list_fluorescence_features`

## Workflow
ROI Crop → Background → Extraction.

Before running processing, save bbox CSVs from the `Alignment` tab into `workspace/bbox/Pos{position_id}.csv` with header `crop,x,y,w,h`.

For fixed-ROI processing, `rois.zarr` stores only static ROI metadata per position: `roi_ids` and `roi_bboxes` with rows `[x, y, w, h]`.

`ProcessingParams` now controls `positions`, `n_workers`, `background_weight`, and `background_min_samples`. `background_min_samples` is retained for config compatibility but is not used by the bbox-based workflow.

| Step | Output |
|------|--------|
| 1. ROI extraction staging | `rois.zarr` metadata + per-frame ROI raw tiles |
| 2. Background | per-frame ROI background tiles under `rois.zarr` |
| 3. Per-position traces | `traces/position_*.csv` |
| 4. Merged sample traces | `traces_merged/*.csv` |

The workflow also writes `processing_config.yaml` at the project root. Trace CSVs are frame-based. Merged analysis CSVs use canonical columns `frame,position,roi,value`, and `load_analysis_csv()` derives `time_min` from a configurable frame interval (default 10 minutes).

## Extending
- **Features**: register built-ins in `pyama.apps.processing.extract`; current built-ins are `area` and `intensity_total`
- **Models**: register built-ins in `pyama.apps.modeling.models.__init__`; `base` is the built-in model

See `pyama/tests/test_tasks.py`, `pyama/tests/test_statistics.py`, and `pyama/tests/test_merge.py`.
