"""Report generation for benchmark results."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from pyama_core.benchmark.comparison import METRIC_NAMES, BenchmarkResult
from pyama_core.benchmark.trajectory import TrajectoryStats


def _stats_to_dict(stats: TrajectoryStats, condition: str) -> dict:
    """Convert TrajectoryStats to a dictionary for DataFrame."""
    return {
        "condition": condition,
        "cell_id": stats.cell_id,
        "fov": stats.fov,
        "duration_frames": stats.duration_frames,
        "mean_velocity": stats.mean_velocity,
        "std_velocity": stats.std_velocity,
        "mean_circularity": stats.mean_circularity,
        "std_circularity": stats.std_circularity,
        "mean_area": stats.mean_area,
        "std_area": stats.std_area,
    }


def generate_report(result: BenchmarkResult, output_dir: Path) -> None:
    """Generate CSV reports and boxplot visualization.

    Args:
        result: BenchmarkResult with patterned and unpatterned stats.
        output_dir: Directory to save output files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate benchmark_summary.csv
    rows = []
    for stats in result.patterned:
        rows.append(_stats_to_dict(stats, "patterned"))
    for stats in result.unpatterned:
        rows.append(_stats_to_dict(stats, "unpatterned"))

    summary_df = pd.DataFrame(rows)
    summary_path = output_dir / "benchmark_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    # Generate comparison_stats.csv
    comparison_rows = []
    for metric, test_result in result.metrics_comparison.items():
        comparison_rows.append({
            "metric": test_result.metric,
            "patterned_median": test_result.patterned_median,
            "unpatterned_median": test_result.unpatterned_median,
            "u_statistic": test_result.u_statistic,
            "p_value": test_result.p_value,
        })

    comparison_df = pd.DataFrame(comparison_rows)
    comparison_path = output_dir / "comparison_stats.csv"
    comparison_df.to_csv(comparison_path, index=False)

    # Generate boxplots
    _generate_boxplots(summary_df, output_dir)


def _generate_boxplots(df: pd.DataFrame, output_dir: Path) -> None:
    """Generate boxplot comparing metrics between conditions."""
    n_metrics = len(METRIC_NAMES)
    n_cols = 3
    n_rows = (n_metrics + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(12, 4 * n_rows))
    axes = axes.flatten()

    for idx, metric in enumerate(METRIC_NAMES):
        ax = axes[idx]

        patterned_data = df[df["condition"] == "patterned"][metric]
        unpatterned_data = df[df["condition"] == "unpatterned"][metric]

        box_data = [patterned_data.dropna(), unpatterned_data.dropna()]
        bp = ax.boxplot(box_data, labels=["Patterned", "Unpatterned"], patch_artist=True)

        bp["boxes"][0].set_facecolor("#4C72B0")
        bp["boxes"][1].set_facecolor("#DD8452")

        ax.set_title(metric.replace("_", " ").title())
        ax.set_ylabel(metric)

    # Hide unused subplots
    for idx in range(len(METRIC_NAMES), len(axes)):
        axes[idx].set_visible(False)

    plt.tight_layout()
    boxplot_path = output_dir / "metrics_boxplots.png"
    fig.savefig(boxplot_path, dpi=150)
    plt.close(fig)
