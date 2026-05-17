"""Contrast scaling helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ContrastLimits:
    low: float
    high: float


def percentile_limits(
    frame: np.ndarray, low_pct: float = 1.0, high_pct: float = 99.5
) -> ContrastLimits:
    finite = np.asarray(frame, dtype=np.float32)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return ContrastLimits(0.0, 1.0)
    low, high = np.percentile(finite, [low_pct, high_pct])
    if high <= low:
        high = low + 1.0
    return ContrastLimits(float(low), float(high))


def scale_to_uint8(frame: np.ndarray, limits: ContrastLimits | None = None) -> np.ndarray:
    limits = limits or percentile_limits(frame)
    scaled = (np.asarray(frame, dtype=np.float32) - limits.low) / (limits.high - limits.low)
    return (np.clip(scaled, 0.0, 1.0) * 255).astype(np.uint8)
