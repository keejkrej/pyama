from pathlib import Path

import pytest

import numpy as np

from pyama.io.zarr import default_compressors, open_raw_zarr, open_rois_zarr
from pyama.io.results import get_trace_csv_path, scan_processing_results
from pyama.types.processing import Channels, ProcessingConfig
from pyama.io.config import save_config


def _write_traces_csv(path: Path, header: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")


def test_scan_processing_results_infers_no_channels_without_phase_contrast(
    tmp_path: Path,
) -> None:
    traces_dir = tmp_path / "traces"
    _write_traces_csv(
        traces_dir / "position_0.csv",
        "position,roi,frame,is_good,x,y,w,h,mean_c1",
        ["0,1,0,True,0,0,1,1,10"],
    )

    results = scan_processing_results(tmp_path)

    assert results.channels is None


def test_scan_processing_results_prefers_config_channels(tmp_path: Path) -> None:
    save_config(
        ProcessingConfig(
            channels=Channels(pc={0: ["area"]}, fl={2: ["mean"]}),
        ),
        tmp_path / "processing_config.yaml",
    )
    traces_dir = tmp_path / "traces"
    _write_traces_csv(
        traces_dir / "position_0.csv",
        "position,roi,frame,is_good,x,y,w,h,area_c0,variance_c3",
        ["0,1,0,True,0,0,1,1,10,5"],
    )

    results = scan_processing_results(tmp_path)

    assert results.channels == Channels(pc={0: ["area"]}, fl={2: ["mean"]})
    assert results.config_path == tmp_path / "processing_config.yaml"
    assert results.traces_dir == traces_dir


def test_scan_processing_results_raises_when_no_outputs_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        scan_processing_results(tmp_path)


def test_get_trace_csv_path_returns_none_for_missing_position(tmp_path: Path) -> None:
    traces_dir = tmp_path / "traces"
    _write_traces_csv(
        traces_dir / "position_0.csv",
        "position,roi,frame,is_good,x,y,w,h,area_c0",
        ["0,1,0,True,0,0,1,1,10"],
    )

    results = scan_processing_results(tmp_path)

    assert get_trace_csv_path(results, 1) is None


def test_scan_processing_results_handles_raw_zarr_without_segmentation_datasets(
    tmp_path: Path,
) -> None:
    store = open_raw_zarr(tmp_path / "raw.zarr", mode="a")
    dataset = store.root.create_array(
        name="position/0/channel/0/raw",
        shape=(1, 2, 2),
        chunks=(1, 2, 2),
        dtype="uint16",
        compressors=default_compressors(),
    )
    dataset[:] = [[[1, 2], [3, 4]]]

    results = scan_processing_results(tmp_path)

    assert results.raw_zarr_path == tmp_path / "raw.zarr"
    assert str(results.position_data[0]["raw_ch_0"]).endswith(
        "::position/0/channel/0/raw"
    )


def test_scan_processing_results_handles_rois_zarr_only_workspace(
    tmp_path: Path,
) -> None:
    store = open_rois_zarr(tmp_path / "rois.zarr", mode="a")
    store.write_roi_ids(0, np.array([7], dtype=np.int32))
    store.write_roi_bboxes(0, np.array([[1, 2, 3, 4]], dtype=np.int32))
    store.write_roi_raw_frame(
        position_id=0,
        channel_id=1,
        roi_id=7,
        frame_idx=0,
        data=np.ones((2, 3), dtype=np.uint16),
    )

    results = scan_processing_results(tmp_path)

    assert results.rois_zarr_path == tmp_path / "rois.zarr"
    assert results.raw_zarr_path is None
    assert str(results.position_data[0]["roi_raw_ch_1"]).endswith(
        "::position/0/channel/1/roi/{roi_id}/raw"
    )
