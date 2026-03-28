from pathlib import Path

import pandas as pd
import pytest

from pyama.apps.processing.service import run_complete_workflow
from pyama.io.zarr import open_rois_zarr
from pyama.types.io import MicroscopyMetadata
from pyama.types.processing import Channels, ProcessingConfig, ProcessingParams


class _FakeReader:
    def __init__(self, frames: dict[tuple[int, int, int], list[list[int]]]) -> None:
        self.frames = frames
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _build_metadata(tmp_path: Path) -> MicroscopyMetadata:
    return MicroscopyMetadata(
        file_path=tmp_path / "fake.nd2",
        base_name="fake",
        file_type="nd2",
        height=4,
        width=4,
        n_frames=2,
        channel_names=("PC", "FL"),
        dtype="uint16",
        timepoints=(0.0, 1.0),
        position_list=(0,),
    )


def _build_config() -> ProcessingConfig:
    return ProcessingConfig(
        channels=Channels(pc={0: ["area"]}, fl={1: ["intensity_total"]}),
        params=ProcessingParams(
            positions="0:1",
            n_workers=1,
            background_weight=1.0,
        ),
    )


def _write_bbox_csv(path: Path, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(["crop,x,y,w,h", *rows]) + "\n", encoding="utf-8")


def test_run_complete_workflow_uses_bbox_csv_without_segmentation_or_tracking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "results"
    output_dir.mkdir()
    _write_bbox_csv(output_dir / "bbox" / "Pos0.csv", ["0,1,1,2,2"])

    frames = {
        (0, 0, 0): [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]],
        (0, 0, 1): [[16, 15, 14, 13], [12, 11, 10, 9], [8, 7, 6, 5], [4, 3, 2, 1]],
        (0, 1, 0): [[0, 0, 0, 0], [0, 10, 10, 0], [0, 10, 50, 0], [0, 0, 0, 0]],
        (0, 1, 1): [[0, 0, 0, 0], [0, 20, 20, 0], [0, 20, 60, 0], [0, 0, 0, 0]],
    }
    fake_reader = _FakeReader(frames)

    monkeypatch.setattr(
        "pyama.apps.processing.service.load_microscopy_file",
        lambda _path: (fake_reader, _build_metadata(tmp_path)),
    )
    monkeypatch.setattr(
        "pyama.apps.processing.roi.get_microscopy_frame",
        lambda *, img, position, channel, time, z: img.frames[
            (position, channel, time)
        ],
    )

    success = run_complete_workflow(
        metadata=_build_metadata(tmp_path),
        config=_build_config(),
        output_dir=output_dir,
    )

    assert success is True
    assert fake_reader.closed is True

    assert (output_dir / "raw.zarr").exists() is False
    rois_store = open_rois_zarr(output_dir / "rois.zarr", mode="r")
    assert rois_store.read_roi_ids(0).tolist() == [0]
    assert rois_store.read_roi_bboxes(0).tolist() == [[1, 1, 2, 2]]

    traces = pd.read_csv(output_dir / "traces" / "position_0.csv")
    assert traces[["x", "y", "w", "h"]].drop_duplicates().to_dict("records") == [
        {"x": 1, "y": 1, "w": 2, "h": 2}
    ]
    assert traces["area_c0"].tolist() == [4.0, 4.0]
    assert traces["intensity_total_c1"].tolist() == [40.0, 40.0]


def test_run_complete_workflow_fails_before_loading_reader_when_bbox_csv_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pyama.apps.processing.service.load_microscopy_file",
        lambda _path: (_ for _ in ()).throw(
            AssertionError("reader should not be loaded")
        ),
    )

    with pytest.raises(FileNotFoundError, match="Missing bbox CSV for position 0"):
        run_complete_workflow(
            metadata=_build_metadata(tmp_path),
            config=_build_config(),
            output_dir=tmp_path / "results",
        )
