"""Pytest configuration for pyama-core tests."""

import sys
from pathlib import Path

# Add pyama-core directory to Python path so tests can import from tests.*
_pyama_core_root = Path(__file__).parent.parent
if str(_pyama_core_root) not in sys.path:
    sys.path.insert(0, str(_pyama_core_root))
