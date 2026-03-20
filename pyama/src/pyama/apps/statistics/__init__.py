"""Statistics app exports."""

from pyama.apps.statistics.discovery import discover_sample_pairs
from pyama.apps.statistics.metrics import evaluate_onset_trace
from pyama.apps.statistics.service import run_folder_statistics

__all__ = [
    "discover_sample_pairs",
    "evaluate_onset_trace",
    "run_folder_statistics",
]
