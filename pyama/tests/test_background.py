from pathlib import Path

import numpy as np

from pyama.apps.processing.background import _estimate_bbox_background_value, run_background_to_raw_zarr
from pyama.apps.processing.extract import _fl_intensity_total
from pyama.io.zarr import default_compressors, open_raw_zarr
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


def test_background_estimator_expands_sampling_box_from_background_min_samples() -> None:
    frame = np.array(
        [
            [20, 20, 20, 20, 20],
            [20, 10, 10, 10, 20],
            [20, 10, 99, 10, 20],
            [20, 10, 10, 10, 20],
            [20, 20, 20, 20, 20],
        ],
        dtype=np.uint16,
    )
    seg_frame = np.zeros((5, 5), dtype=np.uint16)
    seg_frame[2, 2] = 1

    background = _estimate_bbox_background_value(
        raw_frame=frame,
        seg_frame=seg_frame,
        roi_id=1,
        y0=2,
        x0=2,
        y1=3,
        x1=3,
        background_min_samples=8,
    )

    assert background == 10


def test_run_background_to_raw_zarr_does_not_apply_background_weight(tmp_path: Path) -> None:
    output_dir = tmp_path / "results"
    output_dir.mkdir()
    store = open_raw_zarr(output_dir / "raw.zarr", mode="a")

    seg = np.zeros((1, 5, 5), dtype=np.uint16)
    seg[0, 2, 2] = 1
    seg_ds = store.root.create_array(
        name="position/0/channel/0/seg_tracked",
        shape=seg.shape,
        chunks=(1, 5, 5),
        dtype="uint16",
        compressors=default_compressors(),
    )
    seg_ds[:] = seg

    raw = np.array(
        [[
            [20, 20, 20, 20, 20],
            [20, 10, 10, 10, 20],
            [20, 10, 99, 10, 20],
            [20, 10, 10, 10, 20],
            [20, 20, 20, 20, 20],
        ]],
        dtype=np.uint16,
    )
    raw_ds = store.root.create_array(
        name="position/0/channel/1/raw",
        shape=raw.shape,
        chunks=(1, 5, 5),
        dtype="uint16",
        compressors=default_compressors(),
    )
    raw_ds[:] = raw

    summary = run_background_to_raw_zarr(
        reader=None,
        metadata=_build_metadata(tmp_path),
        config=ProcessingConfig(
            channels=Channels(pc={0: ["area"]}, fl={1: ["intensity_total"]}),
            params=ProcessingParams(background_weight=0.5, background_min_samples=8),
        ),
        output_dir=output_dir,
    )

    store = open_raw_zarr(output_dir / "raw.zarr", mode="r")
    bg_path = store.fl_background_path(0, 1)
    bg_ds = store.get_required_array(bg_path)

    assert summary == {
        "background_method": "mvp",
        "background_datasets": 1,
        "background_skipped_datasets": 0,
        "background_frames": 1,
        "background_cancelled": False,
    }
    assert "background_weight" not in bg_ds.attrs
    expected = np.zeros((5, 5), dtype=np.uint16)
    expected[2, 2] = 10
    np.testing.assert_array_equal(store.read_uint16_frame(bg_path, 0), expected)


def test_extract_background_weight_is_applied_once() -> None:
    raw_roi = np.array([[30]], dtype=np.float32)
    bg_roi = np.array([[10]], dtype=np.float32)
    seg_mask = np.array([[True]])

    assert _fl_intensity_total(
        raw_roi,
        bg_roi,
        seg_mask,
        background_weight=0.5,
    ) == 25.0
