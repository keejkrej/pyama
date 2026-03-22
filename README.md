# PyAMA

Python application for microscopy image analysis: core library (pyama) + Qt GUI (pyama-gui).

```bash
uv sync
uv run pyama-gui
```

**Packages**: pyama (workflows, modeling, statistics, I/O) · pyama-gui (Processing, Visualization, Modeling, Statistics tabs)

**Pipeline**: Copying → Segmentation (LOG-STD) → Tracking (IoU) → Background → ROI → Extraction

**Processing config**: `ProcessingParams` now covers positions, workers, background tuning, and `copy_only`; segmentation and tracking use the built-in LOG-STD and IoU pipeline.

**Outputs**: `processing_config.yaml`, `raw.zarr`, `rois.zarr`, `traces/position_*.csv`, and merged sample CSVs under `traces_merged/`

## Docs

- [docs/usage.md](docs/usage.md) – GUI usage
- [docs/core.md](docs/core.md) – API & workflow
- [docs/protocol.md](docs/protocol.md) – Testing
- [AGENTS.md](AGENTS.md) – Developer/AI guidelines
