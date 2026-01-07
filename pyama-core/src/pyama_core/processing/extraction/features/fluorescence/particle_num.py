"""Fluorescence particle counting feature extraction.

Implements a spot detection algorithm for counting fluorescently-labeled
lipid nanoparticles within cell regions using sliding window voting threshold
and watershed segmentation.
"""

import numpy as np
from skimage.filters import gaussian, threshold_li
from skimage.feature import peak_local_max
from skimage.segmentation import watershed

from pyama_core.types.processing import ExtractionContext


def _threshold_li_voting_kernel(image, window_size=500, stride=250):
    """
    Sliding window voting threshold kernel.
    
    Applies threshold_li as a 'convolution' over the image:
    1. Slide a window across the image with specified stride
    2. For each window, apply threshold_li and create binary mask (0 or 1)
    3. Each pixel accumulates votes from all windows containing it
    4. Take mean of votes for each pixel
    5. If mean > 0.5, more 1s than 0s, so set to 1
    
    Parameters:
        image (numpy.ndarray): Input image (2D array)
        window_size (int): Size of the sliding window (default: 500)
        stride (int): Stride for sliding window (default: 250)
        
    Returns:
        numpy.ndarray: Binary mask (True/False) of same shape as input image
    """
    h, w = image.shape
    
    # Pad image with reflection to handle edges
    pad_size = window_size // 2
    image_padded = np.pad(image, pad_size, mode='reflect')
    
    # Initialize vote accumulator
    votes = np.zeros_like(image, dtype=float)
    vote_count = np.zeros_like(image, dtype=int)
    
    # Slide window across image with stride
    for r_start in range(0, h, stride):
        for c_start in range(0, w, stride):
            # Extract window from padded image (always full size due to padding)
            r_pad_start = r_start + pad_size
            r_pad_end = r_pad_start + window_size
            c_pad_start = c_start + pad_size
            c_pad_end = c_pad_start + window_size
            
            window = image_padded[r_pad_start:r_pad_end, c_pad_start:c_pad_end]
            
            # Apply threshold_li to window
            try:
                window_threshold = threshold_li(window)
            except Exception:
                window_threshold = np.mean(window)
            
            # Create binary mask for window (0 or 1)
            window_mask = (window > window_threshold).astype(float)
            
            # Find overlap region in original image
            r_end = min(r_start + window_size, h)
            c_end = min(c_start + window_size, w)
            
            # Extract the portion of window_mask that overlaps with original image
            mask_r_size = r_end - r_start
            mask_c_size = c_end - c_start
            
            # Accumulate votes for pixels in this window
            votes[r_start:r_end, c_start:c_end] += window_mask[:mask_r_size, :mask_c_size]
            vote_count[r_start:r_end, c_start:c_end] += 1
    
    # Take mean of votes for each pixel
    vote_mean = votes / vote_count
    
    # If mean > 0.5, more 1s than 0s
    mask = vote_mean > 0.5
    
    return mask


def extract_particle_num(ctx: ExtractionContext) -> np.int32:
    """
    Count fluorescent particles within a cell region using spot detection.

    This function implements a sophisticated spot detection algorithm that:
    1. Performs background subtraction
    2. Applies Gaussian blur to reduce noise
    3. Uses sliding window voting threshold (threshold_li) for robust thresholding
    4. Finds local maxima as particle seeds
    5. Applies watershed segmentation to separate overlapping particles
    6. Filters particles by minimum radius to remove noise
    7. Filters particles by minimum intensity (max intensity within particle mask) to remove dim particles
    8. Returns the filtered particle count within the masked cell region

    Args:
        ctx: Extraction context containing image, mask, background, and background_weight

    Returns:
        Number of particles detected within the cell region (after size and intensity filtering) as np.int32
    """
    # Extract data from context
    image = ctx.image.astype(np.float32, copy=False)
    background = ctx.background.astype(np.float32, copy=False)
    mask = ctx.mask.astype(bool, copy=False)
    weight = float(ctx.background_weight)
    
    # Check if mask is empty
    if not mask.any():
        return np.int32(0)
    
    # Algorithm parameters
    gaussian_sigma = 2.0  # Gaussian blur sigma parameter
    window_size = 1000  # Size of the sliding window for threshold voting
    stride = 50  # Stride for sliding window
    min_distance = 30  # Minimum distance between peak centers
    min_radius = 3.0  # Minimum particle radius in pixels (particles smaller than this are filtered out)
    min_intensity = 50.0  # Minimum maximum intensity within the particle mask (particles dimmer than this are filtered out)
    
    # Apply background subtraction
    corrected_image = image - weight * background
    
    # Ensure negative values are set to 0 (avoid thresholding artifacts)
    corrected_image = np.clip(corrected_image, 0, None)
    
    # Mask to cell region
    corrected_image = corrected_image * mask
    
    # Apply Gaussian blur to reduce noise
    I_peak_blurred = gaussian(corrected_image, sigma=gaussian_sigma)
    
    # Apply sliding window voting threshold kernel
    try:
        # Adapt window size and stride to image dimensions if needed
        h, w = I_peak_blurred.shape
        adapted_window_size = min(window_size, max(h, w))
        adapted_stride = min(stride, adapted_window_size // 4)
        
        I_mask = _threshold_li_voting_kernel(
            I_peak_blurred, 
            window_size=adapted_window_size, 
            stride=adapted_stride
        )
    except Exception:
        # Fallback to simple threshold (mean) if voting fails
        threshold = np.mean(I_peak_blurred[mask])
        I_mask = (I_peak_blurred > threshold) & mask
    
    # Ensure mask is constrained to cell region
    I_mask = I_mask & mask
    
    # Create blurred × binary mask image for peak finding
    I_peak_blurred_masked = I_peak_blurred * I_mask.astype(float)
    
    # Find local maxima (seeds) within the mask
    try:
        coords = peak_local_max(
            I_peak_blurred_masked, 
            min_distance=min_distance, 
            labels=I_mask, 
            exclude_border=False
        )
    except Exception:
        # If peak finding fails, return 0
        return np.int32(0)
    
    if len(coords) == 0:
        return np.int32(0)
    
    # Prepare markers for watershed
    # Create a marker image where each peak center is assigned a unique integer label (1, 2, 3, ...)
    markers = np.zeros(I_peak_blurred.shape, dtype=int)
    for i, (r, c) in enumerate(coords, 1):
        markers[r, c] = i
    
    # Define the topography (segmentation function)
    # Watershed floods from minima, so we invert the intensity map
    I_topo = -I_peak_blurred_masked
    
    # Apply watershed to get instance segmentation map
    try:
        I_instance = watershed(image=I_topo, markers=markers, mask=I_mask)
    except Exception:
        # If watershed fails, return number of seeds found
        return np.int32(len(coords))
    
    # Get unique particle labels (excluding background label 0)
    unique_labels = np.unique(I_instance)
    unique_peaks = unique_labels[unique_labels != 0]
    
    if len(unique_peaks) == 0:
        return np.int32(0)
    
    # Filter particles by minimum radius and intensity
    filtered_count = 0
    
    for label_val in unique_peaks:
        # Isolate the mask for this particle
        instance_mask = (I_instance == label_val)
        
        # Get coordinates within the mask
        rows, cols = np.where(instance_mask)
        
        if len(rows) == 0:
            continue
        
        # Calculate bounding box
        min_row, max_row = np.min(rows), np.max(rows)
        min_col, max_col = np.min(cols), np.max(cols)
        
        # Calculate bounding box dimensions
        bbox_height = max_row - min_row + 1
        bbox_width = max_col - min_col + 1
        
        # Radius is half of the average of bounding box dimensions
        radius = 0.5 * np.mean([bbox_height, bbox_width])
        
        # Skip if radius doesn't meet minimum threshold
        if radius < min_radius:
            continue
        
        # Calculate maximum intensity within the particle mask
        max_intensity = np.max(corrected_image[instance_mask])
        
        # Keep particle if both radius and intensity meet thresholds
        if max_intensity >= min_intensity:
            filtered_count += 1
    
    return np.int32(filtered_count)


__all__ = ["extract_particle_num"]