"""Pure ndarray normalization helpers for visualization."""

import numpy as np


def normalize_stack(stack: np.ndarray) -> np.ndarray:
    if stack.dtype == np.uint8:
        return stack

    floats = stack.astype(np.float32)
    p1, p99 = np.percentile(floats, 1), np.percentile(floats, 99)
    if p99 <= p1:
        p1, p99 = float(floats.min()), float(floats.max())
    if p99 <= p1:
        return np.zeros_like(floats, dtype=np.uint8)
    normalized = np.clip((floats - p1) / (p99 - p1), 0, 1)
    return (normalized * 255).astype(np.uint8)


def normalize_frame(frame: np.ndarray) -> np.ndarray:
    if frame.dtype == np.uint8:
        return frame

    floats = frame.astype(np.float32)
    p1, p99 = np.percentile(floats, 1), np.percentile(floats, 99)
    if p99 <= p1:
        p1, p99 = float(floats.min()), float(floats.max())
    if p99 <= p1:
        return np.zeros_like(floats, dtype=np.uint8)
    normalized = np.clip((floats - p1) / (p99 - p1), 0, 1)
    return (normalized * 255).astype(np.uint8)


def normalize_segmentation(data: np.ndarray) -> np.ndarray:
    floats = data.astype(np.float32)
    data_min = float(floats.min())
    data_max = float(floats.max())
    if data_max <= data_min:
        return np.zeros_like(floats, dtype=np.uint8)
    if data.dtype == np.uint8 and data_max >= 250:
        return data
    if data_max <= 1:
        normalized = floats * 255
    else:
        normalized = (floats - data_min) / (data_max - data_min) * 255
    return np.clip(normalized, 0, 255).astype(np.uint8)


def preprocess_visualization_data(data: np.ndarray, data_type: str) -> np.ndarray:
    if data_type.startswith("seg"):
        return normalize_segmentation(data)
    if data.ndim == 3:
        return normalize_stack(data)
    return normalize_frame(data)


__all__ = [
    "normalize_frame",
    "normalize_segmentation",
    "normalize_stack",
    "preprocess_visualization_data",
]
