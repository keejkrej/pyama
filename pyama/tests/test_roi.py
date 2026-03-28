from pathlib import Path

import numpy as np
import pytest

from pyama.apps.processing.roi import run_roi_to_rois_zarr
from pyama.io.zarr import open_rois_zarr
from pyama.types.io import MicroscopyMetadata
from pyama.types.processing import Channels, ProcessingConfig, ProcessingParams


def _build_metadata(tmp_path: Path) -> MicroscopyMetadata:
    return MicroscopyMetadata(
        file_path=tmp_path / "fake.nd2",
        base_name="fake",
        file_type="nd2",
        height=4,
        width=5,
        n_frames=2,
        channel_names=("PC", "FL"),
        dtype="uint16",
        timepoints=(0.0, 1.0),
        position_list=(0,),
    )


def _write_bbox_csv(path: Path, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(["crop,x,y,w,h", *rows]) + "\n", encoding="utf-8")


class _FakeReader:
    def __init__(self, frames: dict[tuple[int, int, int], np.ndarray]) -> None:
        self.frames = frames


def test_run_roi_to_rois_zarr_uses_fixed_bbox_metadata_and_raw_tiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "results"
    output_dir.mkdir()
    _write_bbox_csv(output_dir / "bbox" / "Pos0.csv", ["5,2,1,2,2", "2,0,0,2,2"])

    pc_frames = np.array(
        [
            [
                [1, 2, 3, 4, 5],
                [6, 7, 8, 9, 10],
                [11, 12, 13, 14, 15],
                [16, 17, 18, 19, 20],
            ],
            [
                [21, 22, 23, 24, 25],
                [26, 27, 28, 29, 30],
                [31, 32, 33, 34, 35],
                [36, 37, 38, 39, 40],
            ],
        ],
        dtype=np.uint16,
    )
    fl_frames = (pc_frames + 100).astype(np.uint16)
    fake_reader = _FakeReader(
        {
            (0, 0, 0): pc_frames[0],
            (0, 0, 1): pc_frames[1],
            (0, 1, 0): fl_frames[0],
            (0, 1, 1): fl_frames[1],
        }
    )

    monkeypatch.setattr(
        "pyama.apps.processing.roi.get_microscopy_frame",
        lambda *, img, position, channel, time, z: img.frames[(position, channel, time)],
    )

    summary = run_roi_to_rois_zarr(
        reader=fake_reader,
        metadata=_build_metadata(tmp_path),
        config=ProcessingConfig(
            channels=Channels(pc={0: ["area"]}, fl={1: ["intensity_total"]}),
            params=ProcessingParams(),
        ),
        output_dir=output_dir,
    )

    rois_store = open_rois_zarr(output_dir / "rois.zarr", mode="r")
    np.testing.assert_array_equal(
        rois_store.read_roi_ids(0), np.array([2, 5], dtype=np.int32)
    )
    np.testing.assert_array_equal(
        rois_store.read_roi_bboxes(0),
        np.array(
            [
                [0, 0, 2, 2],
                [2, 1, 2, 2],
            ],
            dtype=np.int32,
        ),
    )
    np.testing.assert_array_equal(
        rois_store.read_roi_raw_frame(0, 1, 5, 1),
        fl_frames[1, 1:3, 2:4],
    )
    with pytest.raises(KeyError):
        rois_store.read_roi_background_frame(0, 1, 2, 0)
    assert summary == {
        "roi_method": "mvp",
        "roi_positions": 1,
        "roi_skipped_positions": 0,
        "roi_count": 2,
        "roi_frames": 8,
        "roi_cancelled": False,
    }


def test_run_roi_to_rois_zarr_handles_empty_bbox_csv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "results"
    output_dir.mkdir()
    _write_bbox_csv(output_dir / "bbox" / "Pos0.csv", [])

    fake_reader = _FakeReader(
        {
            (0, 0, 0): np.zeros((4, 5), dtype=np.uint16),
            (0, 0, 1): np.zeros((4, 5), dtype=np.uint16),
        }
    )
    monkeypatch.setattr(
        "pyama.apps.processing.roi.get_microscopy_frame",
        lambda *, img, position, channel, time, z: img.frames[(position, channel, time)],
    )

    summary = run_roi_to_rois_zarr(
        reader=fake_reader,
        metadata=_build_metadata(tmp_path),
        config=ProcessingConfig(
            channels=Channels(pc={0: ["area"]}, fl={}),
            params=ProcessingParams(),
        ),
        output_dir=output_dir,
    )

    rois_store = open_rois_zarr(output_dir / "rois.zarr", mode="r")
    assert rois_store.read_roi_ids(0).shape == (0,)
    assert rois_store.read_roi_bboxes(0).shape == (0, 4)
    assert summary["roi_count"] == 0
