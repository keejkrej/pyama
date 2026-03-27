"""Cache I/O for visualization stacks."""

import logging
from pathlib import Path
import re

import numpy as np

from pyama.io.visualization_source import (
    load_visualization_source,
    parse_visualization_source,
    resolve_visualization_source_path,
)
from pyama.types.visualization import CachedStack
from pyama.utils.visualization import preprocess_visualization_data

logger = logging.getLogger(__name__)


def _sanitize_cache_token(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")


def resolve_cache_path(
    source_path: str | Path,
    channel_id: str,
    cache_root: Path | None = None,
) -> Path:
    _, dataset_path = parse_visualization_source(source_path)
    resolved_source_path = resolve_visualization_source_path(source_path)
    base_dir = cache_root if cache_root is not None else resolved_source_path.parent
    base_dir.mkdir(parents=True, exist_ok=True)
    dataset_token = _sanitize_cache_token(dataset_path)
    channel_token = _sanitize_cache_token(channel_id)
    stem = _sanitize_cache_token(resolved_source_path.stem)
    return base_dir / f"{stem}_{dataset_token}_{channel_token}_uint8.npy"


def build_uint8_cache(
    source_path: str | Path,
    channel_id: str,
    cache_root: Path | None = None,
    force_rebuild: bool = False,
) -> CachedStack:
    cache_path = resolve_cache_path(source_path, channel_id, cache_root)
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
    raw = load_visualization_source(source_path)
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


def load_cached_frame(cached_path: Path, frame: int) -> np.ndarray:
    stack = np.load(cached_path)
    if stack.ndim == 3:
        return stack[frame]
    return stack


def load_cached_slice(cached_path: Path, start: int, end: int) -> np.ndarray:
    stack = np.load(cached_path)
    if stack.ndim == 3:
        return stack[start : end + 1]
    return stack


__all__ = [
    "build_uint8_cache",
    "load_cached_frame",
    "load_cached_slice",
    "resolve_cache_path",
]
