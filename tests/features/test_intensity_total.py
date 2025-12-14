"""Tests for intensity_total feature extraction."""

import numpy as np

from pyama_core.processing.extraction.features.fluorescence.intensity_total import extract_intensity_total
from pyama_core.types.processing import ExtractionContext


def test_extract_intensity_total_no_background():
    """Test intensity extraction with no background correction."""
    # Create test image with 5 bright pixels
    image = np.zeros((10, 10), dtype=np.float32)
    image[2, 2] = 100.0
    image[3, 3] = 150.0
    image[4, 4] = 200.0
    image[5, 5] = 120.0
    image[6, 6] = 80.0
    
    # Full mask
    mask = np.ones((10, 10), dtype=bool)
    
    # Zero background
    background = np.zeros((10, 10), dtype=np.float32)
    
    ctx = ExtractionContext(
        image=image,
        mask=mask,
        background=background,
        background_weight=1.0,
    )
    
    # Expected sum of all pixels
    expected_intensity = 100.0 + 150.0 + 200.0 + 120.0 + 80.0
    actual_intensity = extract_intensity_total(ctx)
    
    assert np.isclose(actual_intensity, expected_intensity)


def test_extract_intensity_total_with_background():
    """Test intensity extraction with background correction."""
    # Create test image
    image = np.ones((10, 10), dtype=np.float32) * 100.0  # All pixels at 100
        
    # Background
    background = np.ones((10, 10), dtype=np.float32) * 50.0  # Background at 50
    
    # Full mask
    mask = np.ones((10, 10), dtype=bool)
    
    ctx = ExtractionContext(
        image=image,
        mask=mask,
        background=background,
        background_weight=1.0,  # Full weight
    )
    
    # Expected: (100 - 50) * 100 pixels = 50 * 100 = 5000
    expected_intensity = 5000.0
    actual_intensity = extract_intensity_total(ctx)
    
    assert np.isclose(actual_intensity, expected_intensity)


def test_extract_intensity_total_with_mask():
    """Test intensity extraction with partial mask."""
    # Create test image
    image = np.ones((10, 10), dtype=np.float32) * 100.0
    
    # Background
    background = np.zeros((10, 10), dtype=np.float32)
    
    # Partial mask - only 25 pixels
    mask = np.zeros((10, 10), dtype=bool)
    mask[3:8, 3:8] = True  # 5x5 square
    
    ctx = ExtractionContext(
        image=image,
        mask=mask,
        background=background,
        background_weight=1.0,
    )
    
    # Expected: 100 * 25 pixels = 2500
    expected_intensity = 2500.0
    actual_intensity = extract_intensity_total(ctx)
    
    assert np.isclose(actual_intensity, expected_intensity)


def test_extract_intensity_total_background_weight():
    """Test intensity extraction with background weight less than 1."""
    # Create test image
    image = np.ones((10, 10), dtype=np.float32) * 100.0
    
    # Background
    background = np.ones((10, 10), dtype=np.float32) * 50.0
    
    # Full mask
    mask = np.ones((10, 10), dtype=bool)
    
    ctx = ExtractionContext(
        image=image,
        mask=mask,
        background=background,
        background_weight=0.5,  # Half weight
    )
    
    # Expected: (100 - 0.5*50) * 100 pixels = (100 - 25) * 100 = 75 * 100 = 7500
    expected_intensity = 7500.0
    actual_intensity = extract_intensity_total(ctx)
    
    assert np.isclose(actual_intensity, expected_intensity)


if __name__ == "__main__":
    test_extract_intensity_total_no_background()
    test_extract_intensity_total_with_background()
    test_extract_intensity_total_with_mask()
    test_extract_intensity_total_background_weight()
    print("All intensity_total tests passed!")