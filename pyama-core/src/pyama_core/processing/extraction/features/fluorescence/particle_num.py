"""Fluorescence particle counting feature extraction.

Implements a spot detection algorithm for counting fluorescently-labeled
lipid nanoparticles within cell regions.
"""

import numpy as np
from scipy import ndimage
from scipy.ndimage import label
from skimage.filters import gaussian
from skimage.morphology import remove_small_objects, remove_small_holes, binary_opening, binary_closing, disk

from pyama_core.types.processing import ExtractionContext


def extract_particle_num(ctx: ExtractionContext) -> np.int32:
    """
    Count fluorescent particles within a cell region using spot detection.

    This function implements a simple spot detection algorithm that:
    1. Performs background subtraction
    2. Applies intensity thresholding using Otsu's method
    3. Uses connected components labeling to identify distinct particles
    4. Applies size filtering to remove noise
    5. Returns the particle count within the masked cell region

    Args:
        ctx: Extraction context containing image, mask, background, and background_weight

    Returns:
        Number of particles detected within the cell region as np.int32
    """
    # Extract data from context
    image = ctx.image.astype(np.float32, copy=False)
    background = ctx.background.astype(np.float32, copy=False)
    mask = ctx.mask.astype(bool, copy=False)
    weight = float(ctx.background_weight)
    
    # Default parameters for particle detection
    min_particle_size = 3  # Minimum particle size in pixels
    max_particle_size = 50  # Maximum particle size in pixels
    gaussian_sigma = 1.0  # Sigma for Gaussian smoothing to reduce noise
    
    # Apply background subtraction
    corrected_image = image - weight * background
    
    # Ensure negative values are set to 0 (avoid thresholding artifacts)
    corrected_image = np.clip(corrected_image, 0, None)
    
    # Mask to cell region
    corrected_image = corrected_image * mask
    
    # Apply Gaussian smoothing to reduce noise (optional, can add back if needed)
    smoothed_image = corrected_image.copy()  # For now, skip smoothing

    # Compute robust z-score using median and MAD over masked region
    masked_vals = smoothed_image[mask]
    if masked_vals.size == 0:
        return np.int32(0)

    median = np.median(masked_vals)
    mad = np.median(np.abs(masked_vals - median))
    # Convert MAD to robust sigma estimate
    robust_sigma = 1.4826 * mad
    eps = 1e-6
    z_img = (smoothed_image - median) / (robust_sigma + eps)

    # Threshold on robust z-score
    z_threshold = 1.5  # detects most particles, accepting some false positives from noise
    binary_image = (z_img >= z_threshold) & mask

    # Morphological cleanup: open then close with small structuring element
    selem = disk(1)
    binary_image = binary_opening(binary_image, selem)
    binary_image = binary_closing(binary_image, selem)

    # Remove tiny noise artifacts and fill small holes
    binary_image = remove_small_objects(binary_image, min_size=min_particle_size)
    binary_image = remove_small_holes(binary_image, area_threshold=min_particle_size)

    # Connected components labeling
    labeled_array, num_features = label(binary_image)

    if num_features > 0:
        # Compute region sizes
        label_sizes = ndimage.sum(np.ones_like(mask, dtype=np.int32), labeled_array, index=range(num_features + 1))
        size_mask = (label_sizes >= min_particle_size) & (label_sizes <= max_particle_size)
        size_mask[0] = False  # remove background
        particle_count = int(np.sum(size_mask[1:]))
    else:
        particle_count = 0
    
    return np.int32(particle_count)


__all__ = ["extract_particle_num"]