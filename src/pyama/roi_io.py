"""ROI stack loading helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def read_roi_stack(path: Path) -> np.ndarray:
    import tifffile

    stack = np.asarray(tifffile.imread(str(path)))
    if stack.ndim == 2:
        return stack[None, None, None, :, :]
    if stack.ndim == 3:
        return stack[:, None, None, :, :]
    if stack.ndim == 4:
        return stack[:, :, None, :, :]
    if stack.ndim == 5:
        return stack
    raise ValueError(f"Unsupported ROI TIFF shape: {stack.shape}")
