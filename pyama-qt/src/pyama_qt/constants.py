"""Application constants for PyAMA Qt."""

import os
from pathlib import Path

# Default folder for file dialogs
DEFAULT_DIR = os.path.expanduser("~")

# Ensure the default folder exists
Path(DEFAULT_DIR).mkdir(parents=True, exist_ok=True)
