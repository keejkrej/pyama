"""Function-based service entrypoints for visualization."""

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CachedStack:
    """Metadata for a cached, normalized stack."""

    path: Path
    shape: tuple[int, ...]
    n_frames: int
    vmin: int = 0
    vmax: int = 255


def normalize_stack(stack: np.ndarray) -> np.ndarray:
    """Normalize an image stack with a consistent scale across all frames."""
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
    """Normalize a single frame to uint8 range using percentile stretching."""
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
    """Normalize segmentation data to uint8 range."""
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
    """Normalize raw data for visualization."""
    if data_type.startswith("seg"):
        return normalize_segmentation(data)
    if data.ndim == 3:
        return normalize_stack(data)
    return normalize_frame(data)


def _resolve_cache_path(
    source_path: Path,
    channel_id: str,
    cache_root: Path | None = None,
) -> Path:
    base_dir = cache_root if cache_root is not None else source_path.parent
    base_dir.mkdir(parents=True, exist_ok=True)
    stem = source_path.stem
    suffix = source_path.suffix or ".npy"
    return base_dir / f"{stem}_{channel_id}_uint8{suffix}"


def get_or_build_uint8(
    source_path: Path,
    channel_id: str,
    *,
    cache_root: Path | None = None,
    force_rebuild: bool = False,
) -> CachedStack:
    """Return a cached normalized stack, building it if needed."""
    cache_path = _resolve_cache_path(source_path, channel_id, cache_root)
    if cache_path.exists() and not force_rebuild:
        logger.debug(
            "Cache hit: Loading cached uint8 stack from %s (channel=%s)",
            cache_path,
            channel_id,
        )
        stack = np.load(cache_path)
        return CachedStack(
            path=cache_path,
            shape=tuple(stack.shape),
            n_frames=stack.shape[0] if stack.ndim == 3 else 1,
        )

    logger.debug(
        "Cache miss: Building uint8 stack from %s (channel=%s, force_rebuild=%s)",
        source_path,
        channel_id,
        force_rebuild,
    )
    raw = np.load(source_path)
    processed = preprocess_visualization_data(raw, channel_id)
    np.save(cache_path, processed)
    logger.debug(
        "Cache created: Saved uint8 stack to %s (shape=%s, n_frames=%d)",
        cache_path,
        processed.shape,
        processed.shape[0] if processed.ndim == 3 else 1,
    )
    return CachedStack(
        path=cache_path,
        shape=tuple(processed.shape),
        n_frames=processed.shape[0] if processed.ndim == 3 else 1,
    )


def load_frame(cached_path: Path, frame: int) -> np.ndarray:
    """Load one frame from a cached stack."""
    stack = np.load(cached_path)
    if stack.ndim == 3:
        return stack[frame]
    return stack


def load_slice(cached_path: Path, start: int, end: int) -> np.ndarray:
    """Load a frame slice from a cached stack."""
    stack = np.load(cached_path)
    if stack.ndim == 3:
        return stack[start : end + 1]
    return stack


__all__ = [
    "CachedStack",
    "get_or_build_uint8",
    "load_frame",
    "load_slice",
    "normalize_frame",
    "normalize_segmentation",
    "normalize_stack",
    "preprocess_visualization_data",
]
