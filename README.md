# PyAMA

Python application for microscopy image analysis: core library (pyama) + Qt GUI (pyama-gui).

```bash
uv sync
uv run pyama-gui
```

**Packages**: pyama (workflows, modeling, statistics, I/O) · pyama-gui (Processing, Visualization, Modeling, Statistics tabs)

**Pipeline**: ROI Crop (bbox CSV) → Background → Extraction

**Processing config**: `ProcessingParams` now covers positions, workers, and background tuning for the bbox-driven ROI workflow.

**Outputs**: `processing_config.yaml`, `rois.zarr`, `traces/position_*.csv`, and merged sample CSVs under `traces_merged/`

## Development

```bash
uv sync
uv run pyama-gui
```

## Windows Installer

The Windows installer is source-based: it embeds `uv.exe`, installs into `%LOCALAPPDATA%\Programs\PyAMA`, downloads Python `3.12` during setup, and runs `uv sync --frozen --no-dev --all-packages --no-editable` to create an app-local `.venv`.

After installation:

- `pyama-gui` is available on the user `PATH`
- the GUI gets a Start Menu shortcut
- the installer can optionally create a Desktop shortcut

To build the installer on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\windows\build-installer.ps1
```

Build prerequisites:

- Inno Setup 6 with `ISCC.exe` available
- network access to download the pinned `uv` binary during the build
- network access during installation so embedded `uv` can download Python and package wheels

The build script validates that `pyama` and `pyama-gui` share the same version before producing `PyAMA-Setup-<version>.exe`.

## Docs

- [docs/usage.md](docs/usage.md) – GUI usage
- [docs/core.md](docs/core.md) – API & workflow
- [docs/protocol.md](docs/protocol.md) – Testing
- [AGENTS.md](AGENTS.md) – Developer/AI guidelines
