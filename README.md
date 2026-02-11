# PyAMA

Python application for microscopy image analysis: core library (pyama-core) + Qt GUI (pyama-pro).

```bash
uv sync
uv run pyama-pro
```

**Packages**: pyama-core (workflows, analysis, I/O) · pyama-pro (Processing, Visualization, Analysis tabs)

**Pipeline**: Copying → Segmentation (LOG-STD) → Correction → Tracking (IoU) → Extraction → traces CSV + `processing_results.yaml`

## Docs

- [docs/usage.md](docs/usage.md) – GUI usage
- [docs/core.md](docs/core.md) – API & workflow
- [docs/plugins.md](docs/plugins.md) – Extensions
- [docs/protocol.md](docs/protocol.md) – Testing
- [AGENTS.md](AGENTS.md) – Developer/AI guidelines
