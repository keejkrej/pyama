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
git clone https://github.com/your-org/pyama.git
cd pyama

# Install all dependencies
uv sync --all-extras

# Launch the GUI
uv run pyama-pro
```

## 📦 Packages

PyAMA consists of the following packages:

- **pyama-core**: Core processing library with analysis workflows
- **pyama-pro**: Qt-based GUI for comprehensive analysis
- **pyama-air**: CLI and GUI wizards for quick workflow configuration
- **pyama-backend**: FastAPI REST API server
- **pyama-frontend**: Next.js web application interface
- **pyama-acdc**: Cell-ACDC integration plugin
- **pyama-blazor**: .NET MAUI Blazor Hybrid desktop app (in development)

## 🎯 Key Features

- **Automated Processing**: End-to-end pipeline from ND2 files to CSV traces
- **Multi-channel Support**: Process phase contrast and multiple fluorescence channels
- **Quality Control**: Interactive trace inspection and filtering
- **Model Fitting**: Built-in models for protein maturation and decay analysis
- **Batch Processing**: Handle large datasets with configurable parallelism
- **Extensible**: Plugin system for custom features and models

## 🐍 Requirements

- Python 3.11 or later
- UV package manager (recommended) or pip
- Qt6 for GUI applications
- Node.js 18+ for web frontend

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
