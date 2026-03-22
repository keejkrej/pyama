from pathlib import Path

import numpy as np

from pyama.apps.processing.segment import run_segment_to_raw_zarr
from pyama.apps.processing.track import run_track_to_raw_zarr
from pyama.io.zarr import default_compressors, open_raw_zarr
from pyama.types.io import MicroscopyMetadata
from pyama.types.processing import Channels, ProcessingConfig, ProcessingParams


def _build_metadata(tmp_path: Path) -> MicroscopyMetadata:
    return MicroscopyMetadata(
        file_path=tmp_path / "fake.nd2",
        base_name="fake",
        file_type="nd2",
        height=4,
        width=4,
        n_frames=2,
        channel_names=("PC",),
        dtype="uint16",
        timepoints=(0.0, 1.0),
        position_list=(0,),
    )


def _build_config() -> ProcessingConfig:
    return ProcessingConfig(
        channels=Channels(pc={0: ["area"]}, fl={}),
        params=ProcessingParams(),
    )


def _seed_raw_dataset(output_dir: Path, frames: np.ndarray) -> None:
    store = open_raw_zarr(output_dir / "raw.zarr", mode="a")
    dataset = store.root.create_array(
        name="position/0/channel/0/raw",
        shape=frames.shape,
        chunks=(1, frames.shape[1], frames.shape[2]),
        dtype="uint16",
        compressors=default_compressors(),
    )
    dataset[:] = frames


def test_run_segment_to_raw_zarr_writes_labeled_dataset_without_method_metadata(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "results"
    output_dir.mkdir()
    frames = np.array(
        [
            [
                [0, 0, 0, 0],
                [0, 20, 120, 0],
                [0, 120, 20, 0],
                [0, 0, 0, 0],
            ],
            [
                [0, 0, 0, 0],
                [0, 30, 140, 0],
                [0, 140, 30, 0],
                [0, 0, 0, 0],
            ],
        ],
        dtype=np.uint16,
    )
    _seed_raw_dataset(output_dir, frames)

    summary = run_segment_to_raw_zarr(
        reader=None,
        metadata=_build_metadata(tmp_path),
        config=_build_config(),
        output_dir=output_dir,
    )

    store = open_raw_zarr(output_dir / "raw.zarr", mode="r")
    seg_path = store.seg_labeled_path(0, 0)
    seg_ds = store.get_required_array(seg_path)

    assert summary == {
        "segmented_datasets": 1,
        "segmentation_skipped_datasets": 0,
        "segmented_frames": 2,
        "segmentation_cancelled": False,
    }
    assert seg_ds.shape == (2, 4, 4)
    assert seg_ds.dtype == np.dtype("uint16")
    assert "segmentation_method" not in seg_ds.attrs
    assert store.read_uint16_3d(seg_path).shape == (2, 4, 4)


def test_run_track_to_raw_zarr_writes_tracked_dataset_without_method_metadata(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "results"
    output_dir.mkdir()
    store = open_raw_zarr(output_dir / "raw.zarr", mode="a")
    seg = np.zeros((2, 4, 4), dtype=np.uint16)
    seg[:, 1:3, 1:3] = 1
    dataset = store.root.create_array(
        name="position/0/channel/0/seg_labeled",
        shape=seg.shape,
        chunks=(1, seg.shape[1], seg.shape[2]),
        dtype="uint16",
        compressors=default_compressors(),
    )
    dataset[:] = seg

    summary = run_track_to_raw_zarr(
        reader=None,
        metadata=_build_metadata(tmp_path),
        config=_build_config(),
        output_dir=output_dir,
    )

    store = open_raw_zarr(output_dir / "raw.zarr", mode="r")
    tracked_path = store.seg_tracked_path(0, 0)
    tracked_ds = store.get_required_array(tracked_path)

    assert summary == {
        "tracked_datasets": 1,
        "tracking_skipped_datasets": 0,
        "tracked_frames": 1,
        "tracking_cancelled": False,
    }
    assert tracked_ds.shape == (2, 4, 4)
    assert tracked_ds.dtype == np.dtype("uint16")
    assert "tracking_method" not in tracked_ds.attrs
    tracked = store.read_uint16_3d(tracked_path)
    assert np.max(tracked[0]) >= 1
    assert np.max(tracked[1]) >= 1
