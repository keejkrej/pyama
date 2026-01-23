"""Tests for tracking methods with visualization."""

import os
from pathlib import Path

import numpy as np
import pytest
from tqdm import tqdm

try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    from skimage.measure import regionprops

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from pyama_core.processing.tracking import get_tracker, list_trackers
from tests.utils import create_progress_callback

# Stable output directories - relative to test file location
_test_dir = Path(__file__).parent.parent
PLOT_DIR = Path(os.environ.get("PYAMA_PLOT_DIR", str(_test_dir / "_plots"))).resolve()
RESULTS_DIR = (_test_dir / "_results").resolve()
DATA_DIR = (_test_dir.parent.parent / "data" / "tests").resolve()

if HAS_MATPLOTLIB:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def plot_tracking_frame(seg_input, track_result, method, frame_idx):
    """Plot a single frame showing segmentation input and tracking result."""
    if not HAS_MATPLOTLIB:
        pytest.skip("matplotlib not available")

    fig, axes = plt.subplots(1, 2, figsize=(12, 6))

    # Left: Input segmentation (labeled mask)
    im0 = axes[0].imshow(seg_input, cmap="nipy_spectral", interpolation="nearest")
    axes[0].set_title(f"Input Segmentation (Frame {frame_idx})")
    axes[0].axis("off")

    # Add text labels for each cell ID
    if HAS_SCIPY:
        props = regionprops(seg_input)
        for prop in props:
            if prop.label > 0:  # Skip background (label 0)
                y, x = prop.centroid
                axes[0].text(
                    x, y, str(prop.label),
                    ha="center", va="center",
                    color="white", fontsize=8, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.5, edgecolor="none")
                )

    # Right: Tracking result (tracked labels)
    im1 = axes[1].imshow(track_result, cmap="nipy_spectral", interpolation="nearest")
    axes[1].set_title(f"Tracking: {method} (Frame {frame_idx})")
    axes[1].axis("off")

    # Add text labels for each track ID
    if HAS_SCIPY:
        props = regionprops(track_result)
        for prop in props:
            if prop.label > 0:  # Skip background (label 0)
                y, x = prop.centroid
                axes[1].text(
                    x, y, str(prop.label),
                    ha="center", va="center",
                    color="white", fontsize=8, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.5, edgecolor="none")
                )

    plt.tight_layout()
    filename = f"track_{method}_frame_{frame_idx:04d}.png"
    out_path = PLOT_DIR / filename
    fig.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved plot to: {out_path}")


def test_tracking_methods():
    """Test all available tracking methods."""
    print("="*60)
    print("Testing Tracking Methods")
    print("="*60)

    # Load input data
    seg_path = DATA_DIR / "seg_labeled.npy"
    if not seg_path.exists():
        pytest.skip(f"Test data not found: {seg_path}")

    print(f"\n1. Loading input data from: {seg_path}")
    seg_input = np.load(seg_path)
    print(f"   Shape: {seg_input.shape}")
    print(f"   Dtype: {seg_input.dtype}")

    if seg_input.ndim != 3:
        raise ValueError(f"Expected 3D array (T, H, W), got shape {seg_input.shape}")

    # Ensure uint16 dtype for tracking
    if seg_input.dtype != np.uint16:
        seg_input = seg_input.astype(np.uint16)

    # Get available tracking methods
    methods = list_trackers()
    print(f"\n2. Available tracking methods: {methods}")

    # Test each method
    for method in methods:
        print(f"\n3. Testing method: {method}")
        try:
            tracker = get_tracker(method)

            # Preallocate output array
            track_result = np.zeros(seg_input.shape, dtype=np.uint16)

            # Run tracking with progress tracking
            num_frames = seg_input.shape[0]
            print("   Running tracking...")
            with tqdm(total=num_frames, desc=f"Tracking ({method})", unit="frame") as pbar:
                progress_callback = create_progress_callback(pbar)
                tracker(
                    image=seg_input,
                    out=track_result,
                    progress_callback=progress_callback,
                )
            print("   Tracking complete")

            # Save results
            result_path = RESULTS_DIR / f"track_{method}.npy"
            np.save(result_path, track_result)
            print(f"   Saved results to: {result_path}")

            # Plot every 20 frames
            print("   Generating plots (every 20 frames)...")
            num_frames = seg_input.shape[0]
            frame_indices = list(range(0, num_frames, 20))
            for frame_idx in tqdm(frame_indices, desc="Plotting", unit="frame", leave=False):
                plot_tracking_frame(
                    seg_input=seg_input[frame_idx],
                    track_result=track_result[frame_idx],
                    method=method,
                    frame_idx=frame_idx,
                )

            # Basic validation
            num_tracks = len(np.unique(track_result))
            print(f"   Detected {num_tracks} unique track IDs across all frames")
            assert num_tracks > 1, f"Expected multiple track IDs, got {num_tracks}"

            # Check that tracking maintains some consistency (non-zero overlap with input)
            overlap = np.sum((seg_input > 0) & (track_result > 0))
            total_cells = np.sum(seg_input > 0)
            if total_cells > 0:
                overlap_ratio = overlap / total_cells
                print(f"   Overlap ratio: {overlap_ratio:.2%}")
                assert overlap_ratio > 0.5, f"Expected >50% overlap, got {overlap_ratio:.2%}"

            print(f"   ✓ {method} tracking test passed")

        except Exception as e:
            print(f"   ❌ {method} tracking test failed: {e}")
            # For btrack, it might not be available due to dependencies
            if method == "btrack" and "btrack" in str(e).lower():
                print(f"   (btrack may not be available due to dependency issues)")
                continue
            raise

    print("\n" + "="*60)
    print("✓ All tracking tests completed")
    print("="*60)


if __name__ == "__main__":
    test_tracking_methods()
