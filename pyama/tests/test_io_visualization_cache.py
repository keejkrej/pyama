from pathlib import Path

import numpy as np

from pyama.io.visualization_cache import (
    build_uint8_cache,
    load_cached_frame,
    load_cached_slice,
    resolve_cache_path,
)


def test_resolve_cache_path_uses_channel_suffix(tmp_path: Path) -> None:
    source_path = tmp_path / "source.npy"

    cache_path = resolve_cache_path(source_path, "seg_tracked")

    assert cache_path == tmp_path / "source_seg_tracked_uint8.npy"


def test_build_uint8_cache_and_loaders(tmp_path: Path) -> None:
    source_path = tmp_path / "source.npy"
    np.save(source_path, np.arange(12, dtype=np.uint16).reshape(3, 2, 2))

    cached = build_uint8_cache(source_path, "raw")

    assert cached.path.exists()
    assert cached.n_frames == 3
    frame = load_cached_frame(cached.path, 1)
    slice_data = load_cached_slice(cached.path, 0, 1)
    assert frame.shape == (2, 2)
    assert slice_data.shape == (2, 2, 2)


def test_build_uint8_cache_reuses_existing_file(tmp_path: Path) -> None:
    source_path = tmp_path / "source.npy"
    np.save(source_path, np.zeros((1, 2, 2), dtype=np.uint16))

    cached = build_uint8_cache(source_path, "raw")
    np.save(cached.path, np.full((1, 2, 2), 123, dtype=np.uint8))

    reused = build_uint8_cache(source_path, "raw", force_rebuild=False)
    reloaded = np.load(reused.path)

    assert int(reloaded[0, 0, 0]) == 123
