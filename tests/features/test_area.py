"""Tests for area feature extraction."""

import numpy as np
import pytest

from pyama_core.processing.extraction.features.phase_contrast.area import extract_area
from pyama_core.types.processing import ExtractionContext


def create_test_context():
    """Create a test context with a simple mask."""
    # Create a 10x10 mask with 25 pixels set to True
    mask = np.zeros((10, 10), dtype=bool)
    mask[3:8, 3:8] = True  # 5x5 square = 25 pixels
    
    return ExtractionContext(
        image=np.zeros((10, 10)),  # Not used for area feature
        mask=mask,
        background=np.zeros((10, 10)),  # Not used for area feature
        background_weight=1.0,  # Not used for area feature
    )


def test_extract_area():
    """Test area extraction returns correct count."""
    ctx = create_test_context()
    
    # Expected area is 25 pixels
    expected_area = 25
    actual_area = extract_area(ctx)
    
    assert actual_area == expected_area


def test_extract_area_empty_mask():
    """Test area extraction with empty mask."""
    mask = np.zeros((10, 10), dtype=bool)
    ctx = ExtractionContext(
        image=np.zeros((10, 10)),
        mask=mask,
        background=np.zeros((10, 10)),
        background_weight=1.0,
    )
    
    # Expected area is 0 for empty mask
    actual_area = extract_area(ctx)
    assert actual_area == 0


def test_extract_area_full_mask():
    """Test area extraction with full mask."""
    mask = np.ones((5, 5), dtype=bool)
    ctx = ExtractionContext(
        image=np.zeros((5, 5)),
        mask=mask,
        background=np.zeros((5, 5)),
        background_weight=1.0,
    )
    
    # Expected area is 25 for 5x5 mask
    actual_area = extract_area(ctx)
    assert actual_area == 25


if __name__ == "__main__":
    test_extract_area()
    test_extract_area_empty_mask()
    test_extract_area_full_mask()
    print("All area tests passed!")