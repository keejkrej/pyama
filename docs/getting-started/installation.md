# Installation

## Prerequisites

- Python 3.11 or later
- UV package manager (recommended) or pip
- Git

## Install with UV (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-org/pyama.git
cd pyama

# Install all dependencies including dev tools
uv sync --all-extras

# Install packages in development mode
uv pip install -e pyama-core/
uv pip install -e pyama-pro/
uv pip install -e pyama-air/
```

## Install with pip

```bash
# Clone the repository
git clone https://github.com/your-org/pyama.git
cd pyama

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e pyama-core/
pip install -e pyama-pro/
pip install -e pyama-air/
```

## Verify Installation

```bash
# Launch the Qt GUI
uv run pyama-pro
# or
python -m pyama_pro.main

# Use the CLI helpers
pyama-air gui
pyama-air cli
```

## Development Dependencies

For development, you'll also want to install the dev dependencies:

```bash
# With UV
uv sync --all-extras

# With pip
pip install pytest ruff ty types-PySide6
```

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

### ND2 File Support
ND2 file reading requires the `nd2` package, which is included in the dependencies. If you encounter issues, ensure you have the latest version:
```bash
uv pip install --upgrade nd2
```
