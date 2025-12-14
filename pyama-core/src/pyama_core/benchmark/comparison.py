"""Statistical comparison between patterned and unpatterned conditions."""

from dataclasses import dataclass, field

from scipy import stats

from pyama_core.benchmark.trajectory import TrajectoryStats


METRIC_NAMES = [
    "duration_frames",
    "mean_velocity",
    "std_velocity",
    "mean_circularity",
    "std_circularity",
    "mean_area",
    "std_area",
]


@dataclass
class StatTestResult:
    """Result of a statistical test."""

    metric: str
    patterned_median: float
    unpatterned_median: float
    u_statistic: float
    p_value: float


@dataclass
class BenchmarkResult:
    """Comparison results between two conditions."""

    patterned: list[TrajectoryStats]
    unpatterned: list[TrajectoryStats]
    metrics_comparison: dict[str, StatTestResult] = field(default_factory=dict)


def _get_metric_values(stats_list: list[TrajectoryStats], metric: str) -> list[float]:
    """Extract metric values from a list of TrajectoryStats."""
    return [getattr(s, metric) for s in stats_list]


def compare_conditions(
    patterned: list[TrajectoryStats],
    unpatterned: list[TrajectoryStats],
) -> BenchmarkResult:
    """Compare patterned vs unpatterned conditions using Mann-Whitney U test.

    Args:
        patterned: List of TrajectoryStats for patterned condition.
        unpatterned: List of TrajectoryStats for unpatterned condition.

    Returns:
        BenchmarkResult with statistical comparison for each metric.
    """
    result = BenchmarkResult(patterned=patterned, unpatterned=unpatterned)

    for metric in METRIC_NAMES:
        patterned_values = _get_metric_values(patterned, metric)
        unpatterned_values = _get_metric_values(unpatterned, metric)

        if len(patterned_values) < 2 or len(unpatterned_values) < 2:
            # Not enough data for statistical test
            result.metrics_comparison[metric] = StatTestResult(
                metric=metric,
                patterned_median=float("nan"),
                unpatterned_median=float("nan"),
                u_statistic=float("nan"),
                p_value=float("nan"),
            )
            continue

        import numpy as np

        patterned_median = float(np.median(patterned_values))
        unpatterned_median = float(np.median(unpatterned_values))

        # Mann-Whitney U test (non-parametric)
        u_stat, p_value = stats.mannwhitneyu(
            patterned_values,
            unpatterned_values,
            alternative="two-sided",
        )

        result.metrics_comparison[metric] = StatTestResult(
            metric=metric,
            patterned_median=patterned_median,
            unpatterned_median=unpatterned_median,
            u_statistic=float(u_stat),
            p_value=float(p_value),
        )

    return result
