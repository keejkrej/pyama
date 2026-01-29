# Installation

## Prerequisites

- Python 3.11 or later
- UV package manager (recommended) or pip
- Git

## Install with UV (Recommended)

```bash
# Clone the repository
git clone https://github.com/SoftmatterLMU-RaedlerGroup/pyama.git
cd pyama

# Install all dependencies including dev tools
uv sync --all-extras

# Install packages in development mode
uv pip install -e pyama-core/
uv pip install -e pyama-qt/
```

## Install with pip

```bash
# Clone the repository
git clone https://github.com/SoftmatterLMU-RaedlerGroup/pyama.git
cd pyama

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e pyama-core/
pip install -e pyama-qt/
```

## Verify Installation

```bash
# Launch the Qt GUI
uv run pyama-qt
# or
python -m pyama_qt.main
```

## Development Dependencies

For development, you'll also want to install the dev dependencies:

```bash
# With UV
uv sync --all-extras

# With pip
pip install pytest ruff ty types-PySide6
```

## Docker (API Server)

Run the pyama-core API server in a Docker container:

```bash
cd pyama-core

# Build and run with GPU (default - Linux with NVIDIA)
docker compose up --build

# Or CPU-only (Mac or no GPU)
docker compose --profile cpu up --build pyama-core-cpu

# Server available at http://localhost:8765
# Health check: curl http://localhost:8765/health
```

### Volume Mounts

Configure data access in `docker-compose.yml`:

```yaml
volumes:
  - ~/data:/data        # Microscopy files (use /data/... in API requests)
  - ~/results:/results  # Output directory (use /results/... in API requests)
  - pyama-db:/root/.pyama  # Persist task database
```

**Important**: Symlinks in mounted directories won't work. Mount the actual data locations instead.

### GPU Support

The container uses PyTorch 2.10.0 with CUDA 13.0:

- **GPU (default)**: `docker compose up` - requires [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) on Linux
- **CPU**: `docker compose --profile cpu up pyama-core-cpu` - works on Mac or systems without GPU

## Troubleshooting

### Python Version
Make sure you're using Python 3.11 or later. Check with:
```bash
python --version
```

### UV Installation
Install UV following the official guide at https://docs.astral.sh/uv/

### Qt Dependencies
PyAMA uses PySide6. On some systems, you may need to install Qt system packages:
- **Ubuntu/Debian**: `sudo apt-get install libqt6gui6 libqt6widgets6`
- **macOS**: Usually works with Homebrew Python
- **Windows**: Usually works out of the box


