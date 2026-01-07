"""Total intensity feature extraction."""

import numpy as np

from pyama_core.types.processing import ExtractionContext


def extract_intensity_total(ctx: ExtractionContext) -> np.float32:
    """
    Extract total intensity for a single cell.

    Computes background-corrected intensity as (image - weight * background).
    Background may be None if no background subtraction is needed.

    Args:
        ctx: Extraction context containing image, mask, background, and background_weight

    Returns:
        Background-corrected total fluorescence intensity (fl - weight * fl_background)
    """
    image = ctx.image.astype(np.float32, copy=False)
    mask = ctx.mask.astype(bool, copy=False)
    weight = float(ctx.background_weight)

    # Optimize: skip background subtraction when not needed
    if ctx.background is None or weight == 0.0:
        # No background subtraction needed
        corrected_image = image
    else:
        background = ctx.background.astype(np.float32, copy=False)
        corrected_image = image - weight * background

    return corrected_image[mask].sum()
