# PyAMA

Python application for microscopy image analysis: core library (pyama) + Qt GUI (pyama-gui).

```bash
uv sync
uv run pyama-gui
```

**Packages**: pyama (workflows, modeling, statistics, I/O) · pyama-gui (Processing, Visualization, Modeling, Statistics tabs)

**Pipeline**: Copying → Segmentation (LOG-STD) → Correction → Tracking (IoU) → Extraction → traces CSV + `processing_results.yaml`

## Docs

- [docs/usage.md](docs/usage.md) – GUI usage
- [docs/core.md](docs/core.md) – API & workflow
- [docs/protocol.md](docs/protocol.md) – Testing
- [AGENTS.md](AGENTS.md) – Developer/AI guidelines

