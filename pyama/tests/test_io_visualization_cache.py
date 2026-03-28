from pathlib import Path

import numpy as np

from pyama.io.visualization_cache import (
    build_uint8_cache,
    load_cached_frame,
    load_cached_slice,
    resolve_cache_path,
)
from pyama.io.zarr import open_raw_zarr, open_rois_zarr


def test_resolve_cache_path_uses_channel_suffix(tmp_path: Path) -> None:
    raw_zarr_path = tmp_path / "raw.zarr"
    source_ref = f"{raw_zarr_path}::position/0/channel/0/seg_tracked"

    cache_path = resolve_cache_path(source_ref, "seg_tracked")

    assert cache_path == tmp_path / "raw_position_0_channel_0_seg_tracked_seg_tracked_uint8.npy"


def test_build_uint8_cache_and_loaders(tmp_path: Path) -> None:
    raw_zarr_path = tmp_path / "raw.zarr"
    store = open_raw_zarr(raw_zarr_path, mode="a")
    dataset = store.create_uint16_timeseries(
        "position/0/channel/0/raw",
        n_frames=3,
        height=2,
        width=2,
    )
    dataset[:] = np.arange(12, dtype=np.uint16).reshape(3, 2, 2)
    source_ref = f"{raw_zarr_path}::position/0/channel/0/raw"

    cached = build_uint8_cache(source_ref, "raw")

    assert cached.path.exists()
    assert cached.n_frames == 3
    frame = load_cached_frame(cached.path, 1)
    slice_data = load_cached_slice(cached.path, 0, 1)
    assert frame.shape == (2, 2)
    assert slice_data.shape == (2, 2, 2)


def test_build_uint8_cache_reuses_existing_file(tmp_path: Path) -> None:
    raw_zarr_path = tmp_path / "raw.zarr"
    store = open_raw_zarr(raw_zarr_path, mode="a")
    dataset = store.create_uint16_timeseries(
        "position/0/channel/0/raw",
        n_frames=1,
        height=2,
        width=2,
    )
    dataset[:] = np.zeros((1, 2, 2), dtype=np.uint16)
    source_ref = f"{raw_zarr_path}::position/0/channel/0/raw"

    cached = build_uint8_cache(source_ref, "raw")
    np.save(cached.path, np.full((1, 2, 2), 123, dtype=np.uint8))

    reused = build_uint8_cache(source_ref, "raw", force_rebuild=False)
    reloaded = np.load(reused.path)

    assert int(reloaded[0, 0, 0]) == 123


def test_build_uint8_cache_accepts_raw_zarr_dataset_reference(tmp_path: Path) -> None:
    raw_zarr_path = tmp_path / "raw.zarr"
    store = open_raw_zarr(raw_zarr_path, mode="a")
    dataset = store.create_uint16_timeseries(
        "position/0/channel/0/raw",
        n_frames=2,
        height=2,
        width=3,
    )
    dataset[:] = np.arange(12, dtype=np.uint16).reshape(2, 2, 3)

    source_ref = f"{raw_zarr_path}::position/0/channel/0/raw"
    cached = build_uint8_cache(source_ref, "raw_ch_0")

    assert cached.path.exists()
    assert cached.path.suffix == ".npy"
    assert cached.n_frames == 2
    reloaded = np.load(cached.path)
    assert reloaded.shape == (2, 2, 3)


def test_build_uint8_cache_accepts_rois_zarr_roi_reference(tmp_path: Path) -> None:
    rois_zarr_path = tmp_path / "rois.zarr"
    store = open_rois_zarr(rois_zarr_path, mode="a")
    store.write_roi_raw_frame(
        position_id=0,
        channel_id=1,
        roi_id=7,
        frame_idx=0,
        data=np.arange(6, dtype=np.uint16).reshape(2, 3),
    )
    store.write_roi_raw_frame(
        position_id=0,
        channel_id=1,
        roi_id=7,
        frame_idx=1,
        data=np.arange(6, 12, dtype=np.uint16).reshape(2, 3),
    )

    source_ref = f"{rois_zarr_path}::position/0/channel/1/roi/7/raw"
    cached = build_uint8_cache(source_ref, "roi_raw_ch_1")

    assert cached.path.exists()
    assert cached.n_frames == 2
    reloaded = np.load(cached.path)
    assert reloaded.shape == (2, 2, 3)
