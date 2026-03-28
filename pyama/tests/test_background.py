from pathlib import Path

import numpy as np

from pyama.apps.processing.background import (
    _estimate_roi_background_value,
    run_background_to_rois_zarr,
)
from pyama.apps.processing.extract import _fl_intensity_total
from pyama.io.zarr import open_rois_zarr
from pyama.types.io import MicroscopyMetadata
from pyama.types.processing import Channels, ProcessingConfig, ProcessingParams


def _build_metadata(tmp_path: Path) -> MicroscopyMetadata:
    return MicroscopyMetadata(
        file_path=tmp_path / "fake.nd2",
        base_name="fake",
        file_type="nd2",
        height=5,
        width=5,
        n_frames=1,
        channel_names=("PC", "FL"),
        dtype="uint16",
        timepoints=(0.0,),
        position_list=(0,),
    )


def test_background_estimator_uses_mean_of_pixels_up_to_first_quartile() -> None:
    raw_roi = np.array(
        [
            [10, 10, 10],
            [10, 99, 50],
            [20, 30, 40],
        ],
        dtype=np.uint16,
    )

    background = _estimate_roi_background_value(raw_roi)

    assert background == 10


def test_run_background_to_rois_zarr_does_not_apply_background_weight(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "results"
    output_dir.mkdir()

    rois_store = open_rois_zarr(output_dir / "rois.zarr", mode="a")
    rois_store.write_roi_ids(0, np.array([0], dtype=np.int32))
    rois_store.write_roi_bboxes(0, np.array([[1, 1, 3, 3]], dtype=np.int32))
    rois_store.write_roi_raw_frame(
        0,
        1,
        0,
        0,
        np.array(
            [
                [10, 10, 10],
                [10, 99, 50],
                [20, 30, 40],
            ],
            dtype=np.uint16,
        ),
    )

    summary = run_background_to_rois_zarr(
        reader=None,
        metadata=_build_metadata(tmp_path),
        config=ProcessingConfig(
            channels=Channels(pc={0: ["area"]}, fl={1: ["intensity_total"]}),
            params=ProcessingParams(background_weight=0.5, background_min_samples=8),
        ),
        output_dir=output_dir,
    )

    rois_store = open_rois_zarr(output_dir / "rois.zarr", mode="r")

    assert summary == {
        "background_method": "mvp",
        "background_datasets": 1,
        "background_skipped_datasets": 0,
        "background_frames": 1,
        "background_cancelled": False,
    }
    np.testing.assert_array_equal(
        rois_store.read_roi_background_frame(0, 1, 0, 0),
        np.full((3, 3), 10, dtype=np.uint16),
    )


def test_extract_background_weight_is_applied_once() -> None:
    raw_roi = np.array([[30]], dtype=np.float32)
    bg_roi = np.array([[10]], dtype=np.float32)
    seg_mask = np.array([[True]])

    assert (
        _fl_intensity_total(
            raw_roi,
            bg_roi,
            background_weight=0.5,
            seg_mask=seg_mask,
        )
        == 25.0
    )
