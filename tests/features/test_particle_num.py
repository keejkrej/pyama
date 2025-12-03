"""Essential visualization test for particle_num.
Single scenario: many Gaussian particles on a noisy background. Each should be
detected and marked with a bounding box. Plots saved to tests/_plots.
"""

import os
from pathlib import Path

import numpy as np
import pytest
from matplotlib import pyplot as plt
from scipy.ndimage import label
from skimage.filters import threshold_otsu
from skimage.measure import find_contours

from pyama_core.types.processing import ExtractionContext

PLOT_DIR = Path(os.environ.get("PYAMA_PLOT_DIR", "tests/_plots")).resolve()
PLOT_DIR.mkdir(parents=True, exist_ok=True)


def create_test_context_with_particles(particle_positions, image_size=100, background_level=50.0, noise_level=2.0):
    np.random.seed(7)
    background = np.ones((image_size, image_size), dtype=np.float32) * background_level
    background += np.random.normal(0, noise_level, (image_size, image_size)).astype(np.float32)
    background = np.clip(background, 0, None)

    # Circular mask
    y, x = np.ogrid[:image_size, :image_size]
    center = image_size // 2
    radius = image_size // 3
    mask = (x - center) ** 2 + (y - center) ** 2 <= radius ** 2

    # Synthesize signal with Gaussian particles
    image = background.copy()
    rng = np.random.RandomState(9)
    sigma = 1.5
    yy, xx = np.mgrid[:image_size, :image_size]
    for (py, px) in particle_positions:
        if 0 <= py < image_size and 0 <= px < image_size and mask[int(py), int(px)]:
            amp = 220.0 + rng.normal(0, 15.0)
            g = amp * np.exp(-((xx - px) ** 2 + (yy - py) ** 2) / (2 * sigma ** 2))
            image = np.maximum(image, g).astype(np.float32)

    # Add shot noise
    image += np.random.poisson(0.4, (image_size, image_size)).astype(np.float32)
    image = np.clip(image, 0, None)

    return ExtractionContext(image=image, mask=mask, background=background, background_weight=1.0)


def detect_particles_with_boxes(ctx: ExtractionContext):
    image = ctx.image.astype(np.float32)
    background = ctx.background.astype(np.float32)
    mask = ctx.mask.astype(bool)

    corrected = np.clip(image - background, 0, None) * mask

    if corrected.sum() > 0:
        thr = threshold_otsu(corrected[mask]) * 0.6
        binary = (corrected > thr) & mask
    else:
        binary = np.zeros_like(corrected, dtype=bool)

    labeled, n = label(binary)

    boxes = []
    for lab in range(1, n + 1):
        ys, xs = np.where(labeled == lab)
        if ys.size == 0:
            continue
        y0, y1 = ys.min(), ys.max()
        x0, x1 = xs.min(), xs.max()
        boxes.append((y0, x0, y1, x1))

    return boxes


def test_particles_visualization_and_detection():
    # 8 well-separated particles inside mask
    positions = [
        (50, 20), (50, 80), (20, 50), (80, 50),
        (35, 35), (35, 65), (65, 35), (65, 65)
    ]
    ctx = create_test_context_with_particles(positions)

    boxes = detect_particles_with_boxes(ctx)

    # Expect all particles detected
    assert len(boxes) == len(positions)

    # Plot
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(ctx.image, cmap="gray")
    for contour in find_contours(ctx.mask, 0.5):
        ax.plot(contour[:, 1], contour[:, 0], color="red", linewidth=2)
    for (y0, x0, y1, x1) in boxes:
        rect = plt.Rectangle((x0, y0), x1 - x0 + 1, y1 - y0 + 1, edgecolor="lime", facecolor="none", linewidth=1.5)
        ax.add_patch(rect)
    ax.set_title(f"Detected particles: {len(boxes)}")
    out_path = str(PLOT_DIR / "particle_many.png")
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved plot to: {out_path}")
