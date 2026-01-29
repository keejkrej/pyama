# PyAMA

PyAMA is a modular Python application for microscopy image analysis. It provides tools for processing large time-lapse microscopy datasets, extracting quantitative cellular features, and fitting mathematical models to describe cellular dynamics.

## 📚 Documentation

PyAMA documentation is available at **https://pyama.readthedocs.io**

The documentation includes:
- [Installation Guide](https://pyama.readthedocs.io/en/latest/getting-started/installation.html)
- [Quick Start](https://pyama.readthedocs.io/en/latest/getting-started/quickstart.html)
- [User Guide](https://pyama.readthedocs.io/en/latest/user-guide/index.html)
- [Package Documentation](https://pyama.readthedocs.io/en/latest/packages/index.html)
- [API Reference](https://pyama.readthedocs.io/en/latest/reference/index.html)

## 🚀 Quick Install

```bash
# Clone the repository
git clone https://github.com/SoftmatterLMU-RaedlerGroup/pyama.git
cd pyama

# Install all dependencies
uv sync --all-extras

# Launch the Qt GUI
uv run pyama-qt

# Or start the API server (for web frontend)
uv run pyama-core serve
```

### Docker (API Server)

```bash
cd pyama-core

# Build and run with GPU (default)
docker compose up --build

# Or CPU-only (Mac or no GPU)
docker compose --profile cpu up --build pyama-core-cpu

# Server available at http://localhost:8765
```

Configure volume mounts in `docker-compose.yml` to access your data:
- `~/data:/data` - Microscopy files
- `~/results:/results` - Output directory

GPU is the default (requires [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) on Linux). Use `--profile cpu` on Mac or systems without GPU.

## 📦 Packages

PyAMA consists of the following packages:

- **pyama-core**: Core processing library with analysis workflows, CLI tools, and REST API server
- **pyama-qt**: Qt-based GUI for comprehensive analysis
- **pyama-react**: Modern web frontend built with React, Tailwind CSS, and Tauri for desktop deployment
- **pyama-acdc**: Cell-ACDC integration plugin

## 🎯 Key Features

- **Automated Processing**: End-to-end pipeline from ND2/CZI files to CSV traces
- **Multi-channel Support**: Process phase contrast and multiple fluorescence channels
- **Deep Learning**: Spotiflow-based particle detection for fluorescence spot counting
- **Quality Control**: Interactive trace inspection and filtering
- **Model Fitting**: Built-in models for protein maturation and decay analysis
- **Batch Processing**: Handle large datasets with configurable parallelism
- **REST API & MCP**: FastAPI server with Model Context Protocol integration for programmatic access
- **Modern Web UI**: React + Tauri desktop application with task management
- **Extensible**: Plugin system for custom features and models

## 🖥️ CLI Commands

```bash
# Run processing workflow (interactive or config-based)
uv run pyama-core workflow
uv run pyama-core workflow --config config.yaml --nd2-path data.nd2

# Merge CSV outputs from multiple samples
uv run pyama-core merge

# Plot cell trajectories
uv run pyama-core trajectory traces.csv

# Plot numpy array files
uv run pyama-core plot data.npy

# Start the API server
uv run pyama-core serve --port 8000 --reload

# Connect Claude Code as an MCP client (requires server running)
export PYAMA_MCP_URL="http://localhost:8000"  # adjust host/port as needed
claude mcp add pyama --transport http "$PYAMA_MCP_URL/mcp"
```

## 🐍 Requirements

- Python 3.11 or later
- UV package manager (recommended) or pip
- Qt6 for GUI applications (pyama-qt)
- Node.js and Bun/npm for web frontend (pyama-react)

## 📖 Learn More

- Visit the [full documentation](https://pyama.readthedocs.io) for comprehensive guides
- Check the [User Guide](https://pyama.readtheddocs.io/en/latest/user-guide/) for step-by-step instructions
- See the [API Reference](https://pyama.readthedocs.io/en/latest/reference/api-reference.html) for integration details
- Read [contributing guidelines](https://pyama.readthedocs.io/en/latest/development/contributing.html) to help improve PyAMA

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTORS.md](CONTRIBUTORS.md) for a list of contributors and visit our [contributing guide](https://pyama.readthedocs.io/en/latest/development/contributing.html) to get started.

---

For the complete documentation and detailed instructions, please visit **https://pyama.readthedocs.io**
