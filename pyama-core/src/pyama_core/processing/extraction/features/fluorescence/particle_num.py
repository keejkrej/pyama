"""Fluorescence particle counting using Spotiflow.

Uses a pretrained deep learning model for subpixel-accurate spot detection
in fluorescence microscopy images.
"""

import numpy as np
from spotiflow.model import Spotiflow

from pyama_core.types.processing import ExtractionContext

# Lazy-loaded model cache
_model: Spotiflow | None = None


def _get_model() -> Spotiflow:
    """Get or load the spotiflow model (cached)."""
    global _model
    if _model is None:
        _model = Spotiflow.from_pretrained("general")
    return _model


def extract_particle_num(ctx: ExtractionContext) -> np.int32:
    """
    Count fluorescent particles within a cell region using Spotiflow.

    Algorithm:
    1. Apply background subtraction
    2. Run spotiflow detection on full cropped image
    3. Filter detected spots to keep only those inside cell mask
    4. Return filtered count

    Args:
        ctx: Extraction context containing image, mask, background, and background_weight

    Returns:
        Number of particles detected within the cell region as np.int32
    """
    image = ctx.image.astype(np.float32, copy=False)
    mask = ctx.mask.astype(bool, copy=False)

    # Check if mask is empty
    if not mask.any():
        return np.int32(0)

    # Background subtraction
    if ctx.background is not None and ctx.background_weight > 0.0:
        background = ctx.background.astype(np.float32, copy=False)
        image = image - ctx.background_weight * background
        image = np.clip(image, 0, None)

    # Get cached model
    model = _get_model()

    # Detect spots on full image
    points, _ = model.predict(image)

    if len(points) == 0:
        return np.int32(0)

    # Filter spots by cell mask
    # points are (y, x) coordinates
    count = 0
    for y, x in points:
        iy, ix = int(round(y)), int(round(x))
        if 0 <= iy < mask.shape[0] and 0 <= ix < mask.shape[1]:
            if mask[iy, ix]:
                count += 1

    return np.int32(count)


__all__ = ["extract_particle_num"]
