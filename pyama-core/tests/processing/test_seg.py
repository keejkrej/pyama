"""Tests for segmentation methods with visualization."""

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

from pyama_core.processing.segmentation import get_segmenter, list_segmenters
from tests.utils import create_progress_callback

# Stable output directories - relative to test file location
_test_dir = Path(__file__).parent.parent
PLOT_DIR = Path(os.environ.get("PYAMA_PLOT_DIR", str(_test_dir / "_plots"))).resolve()
RESULTS_DIR = (_test_dir / "_results").resolve()
DATA_DIR = (_test_dir.parent.parent / "data" / "tests").resolve()

if HAS_MATPLOTLIB:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def plot_segmentation_frame(seg_result, method, frame_idx, pc_image):
    """Plot a single frame showing input and segmentation result."""
    if not HAS_MATPLOTLIB:
        pytest.skip("matplotlib not available")

    fig, axes = plt.subplots(1, 2, figsize=(12, 6))

    # Left: Input phase contrast image
    axes[0].imshow(pc_image, cmap="gray")
    axes[0].set_title(f"Input PC (Frame {frame_idx})")
    axes[0].axis("off")

    # Right: Segmentation result (labeled mask)
    im = axes[1].imshow(seg_result, cmap="nipy_spectral", interpolation="nearest")
    axes[1].set_title(f"Segmentation: {method} (Frame {frame_idx})")
    axes[1].axis("off")
    plt.colorbar(im, ax=axes[1], label="Cell ID")

    plt.tight_layout()
    filename = f"seg_{method}_frame_{frame_idx:04d}.png"
    out_path = PLOT_DIR / filename
    fig.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved plot to: {out_path}")


def test_segmentation_methods():
    """Test all available segmentation methods."""
    print("=" * 60)
    print("Testing Segmentation Methods")
    print("=" * 60)

    # Load input data
    pc_path = DATA_DIR / "pc.npy"
    if not pc_path.exists():
        pytest.skip(f"Test data not found: {pc_path}")

    print(f"\n1. Loading input data from: {pc_path}")
    pc_image = np.load(pc_path)
    print(f"   Shape: {pc_image.shape}")
    print(f"   Dtype: {pc_image.dtype}")

    if pc_image.ndim != 3:
        raise ValueError(f"Expected 3D array (T, H, W), got shape {pc_image.shape}")

    # Get available segmentation methods
    methods = list_segmenters()
    print(f"\n2. Available segmentation methods: {methods}")

    # Test each method
    for method in methods:
        print(f"\n3. Testing method: {method}")
        try:
            segmenter = get_segmenter(method)

            # Preallocate output array
            seg_result = np.zeros(pc_image.shape, dtype=np.uint16)

            # Run segmentation with progress tracking
            num_frames = pc_image.shape[0]
            print("   Running segmentation...")
            with tqdm(
                total=num_frames, desc=f"Segmentation ({method})", unit="frame"
            ) as pbar:
                progress_callback = create_progress_callback(pbar)
                segmenter(
                    image=pc_image,
                    out=seg_result,
                    progress_callback=progress_callback,
                )
            print("   Segmentation complete")

            # Save results
            result_path = RESULTS_DIR / f"seg_{method}.npy"
            np.save(result_path, seg_result)
            print(f"   Saved results to: {result_path}")

            # Plot every 20 frames
            print("   Generating plots (every 20 frames)...")
            num_frames = pc_image.shape[0]
            frame_indices = list(range(0, num_frames, 20))
            for frame_idx in tqdm(
                frame_indices, desc="Plotting", unit="frame", leave=False
            ):
                plot_segmentation_frame(
                    seg_result=seg_result[frame_idx],
                    method=method,
                    frame_idx=frame_idx,
                    pc_image=pc_image[frame_idx],
                )

            # Basic validation
            num_cells = len(np.unique(seg_result))
            print(f"   Detected {num_cells} unique cell IDs across all frames")
            assert num_cells > 1, f"Expected multiple cell IDs, got {num_cells}"

            print(f"   ✓ {method} segmentation test passed")

        except Exception as e:
            print(f"   ❌ {method} segmentation test failed: {e}")
            raise

    print("\n" + "=" * 60)
    print("✓ All segmentation tests completed")
    print("=" * 60)


if __name__ == "__main__":
    test_segmentation_methods()
