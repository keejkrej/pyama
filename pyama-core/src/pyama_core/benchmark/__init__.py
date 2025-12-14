"""Benchmark module for comparing patterned vs unpatterned cell trajectories."""

from pyama_core.benchmark.trajectory import (
    TrajectoryStats,
    CellFrame,
    extract_trajectories,
)
from pyama_core.benchmark.metrics import compute_trajectory_stats
from pyama_core.benchmark.comparison import (
    StatTestResult,
    BenchmarkResult,
    compare_conditions,
)
from pyama_core.benchmark.report import generate_report

__all__ = [
    "TrajectoryStats",
    "CellFrame",
    "extract_trajectories",
    "compute_trajectory_stats",
    "StatTestResult",
    "BenchmarkResult",
    "compare_conditions",
    "generate_report",
]
