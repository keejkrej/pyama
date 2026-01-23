"""Tests for CUSUM event detection with essential visualization."""

import os
from pathlib import Path

import numpy as np
import pytest

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from pyama_core.analysis.event_detection import detect_event_cusum

# Stable output directory for plots
PLOT_DIR = Path(os.environ.get("PYAMA_PLOT_DIR", "tests/_plots")).resolve()
if HAS_MATPLOTLIB:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)


def plot_event_detection(y_data, t_data, result, title, filename):
    """Plot a single essential test case with detected event."""
    if not HAS_MATPLOTLIB:
        pytest.skip("matplotlib not available")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(t_data, y_data, 'b-', linewidth=2, label='Noisy Signal')

    if result.event_detected and result.event_time is not None:
        ax.axvline(result.event_time, color='r', linestyle='--', linewidth=2,
                   label=f'Event at t={result.event_time:.1f}')
        ax.scatter([result.event_time], [y_data[int(result.event_time)]],
                   color='r', s=100, zorder=5, marker='o')

    ax.set_xlabel('Time (frames)')
    ax.set_ylabel('Intensity')
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.tight_layout()

    out_path = str(PLOT_DIR / filename)
    fig.savefig(out_path, dpi=100, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved plot to: {out_path}")


def test_noisy_step_up():
    """Test detection of a noisy upward step and generate a plot."""
    np.random.seed(42)
    y_before = np.random.normal(100, 8.0, size=50)
    y_after = np.random.normal(200, 8.0, size=50)
    y_data = np.concatenate([y_before, y_after])
    t_data = np.arange(len(y_data), dtype=np.float64)
    
    result = detect_event_cusum(t_data, y_data)
    
    assert result.event_detected is True, "Event should be detected in noisy upward step"
    assert 40 < result.event_index < 60, "Event index should be near the step"
    assert result.event_magnitude > 80, "Magnitude should be significant"
    assert result.confidence > 0.8, "Confidence should be high for a clear step"
    
    plot_event_detection(y_data, t_data, result, "Noisy Upward Step", "event_noisy_up.png")


def test_noisy_step_down():
    """Test detection of a noisy downward step and generate a plot."""
    np.random.seed(43)
    y_before = np.random.normal(200, 8.0, size=50)
    y_after = np.random.normal(100, 8.0, size=50)
    y_data = np.concatenate([y_before, y_after])
    t_data = np.arange(len(y_data), dtype=np.float64)
    
    result = detect_event_cusum(t_data, y_data)
    
    assert result.event_detected is True, "Event should be detected in noisy downward step"
    assert 40 < result.event_index < 60, "Event index should be near the step"
    assert result.event_magnitude < -80, "Magnitude should be significant and negative"
    assert result.confidence > 0.8, "Confidence should be high for a clear step"

    plot_event_detection(y_data, t_data, result, "Noisy Downward Step", "event_noisy_down.png")
