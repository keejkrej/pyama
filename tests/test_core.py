from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from pyama.adapters.base import ImageInfo, ReaderSession
from pyama.adapters.czi import CZIReaderAdapter
from pyama.adapters.folder import parse_frame_path, scan_image_folder
from pyama.adapters.nd2 import FrameLookup, ND2ReaderAdapter
from pyama.annotations import load_annotation, save_annotation
from pyama.contrast import percentile_limits, scale_to_uint8
from pyama.grid import GridSpec, auto_excluded_cells, enumerate_grid
from pyama.workspace import (
    Alignment,
    BBox,
    crop_rois,
    load_alignment,
    load_bbox,
    save_alignment,
    save_bbox,
    scan_roi_workspace,
)


def test_parse_lisca_frame_name() -> None:
    path = Path("Pos0/img_channel002_position003_time000000004_z005.tif")
    parsed = parse_frame_path(path)
    assert parsed is not None
    assert (parsed.p, parsed.t, parsed.c, parsed.z) == (3, 4, 2, 5)


def test_scan_image_folder_fallback(tmp_path: Path) -> None:
    from PIL import Image

    pos = tmp_path / "Pos1"
    pos.mkdir()
    Image.fromarray(np.zeros((3, 4), dtype=np.uint8)).save(pos / "frame0.png")
    Image.fromarray(np.ones((3, 4), dtype=np.uint8)).save(pos / "frame1.png")

    frames = scan_image_folder(tmp_path)
    assert set(frames) == {(1, 0, 0, 0), (1, 1, 0, 0)}


def test_nd2_in_pixel_channel_first_axis() -> None:
    class FakeHandle:
        sizes = {"C": 2}

        def read_frame(self, index: int) -> np.ndarray:
            assert index == 7
            return np.stack([np.full((2, 3), 11), np.full((2, 3), 22)])

    lookup = FrameLookup(sequence_axes=("P", "T", "Z"), index_by_coords={(0, 1, 2): 7})
    frame = ND2ReaderAdapter.read_frame_2d(FakeHandle(), lookup, 0, 1, 1, 2)
    assert frame.shape == (2, 3)
    assert np.all(frame == 22)


def test_nd2_in_pixel_channel_last_axis() -> None:
    class FakeHandle:
        sizes = {"C": 2}

        def read_frame(self, index: int) -> np.ndarray:
            assert index == 0
            frame = np.zeros((3, 4, 2), dtype=np.uint8)
            frame[..., 1] = 9
            return frame

    lookup = FrameLookup(sequence_axes=(), index_by_coords={(): 0})
    frame = ND2ReaderAdapter.read_frame_2d(FakeHandle(), lookup, 0, 0, 1, 0)
    assert np.all(frame == 9)


def test_czi_axis_size_validation() -> None:
    assert CZIReaderAdapter.axis_size({"T": (2, 5)}, "T") == 3
    with pytest.raises(ValueError):
        CZIReaderAdapter.axis_size({"T": (4, 3)}, "T")


def test_contrast_scaling() -> None:
    frame = np.array([0, 1, 2, 100], dtype=np.float32)
    limits = percentile_limits(frame, 0, 100)
    assert limits.low == 0
    assert limits.high == 100
    assert scale_to_uint8(frame, limits).tolist() == [0, 2, 5, 255]


def test_grid_enumeration_and_auto_exclude() -> None:
    spec = GridSpec(
        kind="hex", rows=2, cols=2, roi_width=10, roi_height=10, spacing_x=10, spacing_y=10
    )
    cells = enumerate_grid(spec)
    assert [(cell.bbox.x, cell.bbox.y) for cell in cells] == [(0, 0), (10, 0), (5, 10), (15, 10)]
    assert auto_excluded_cells(spec, image_width=20, image_height=20) == {3}


def test_bbox_and_alignment_roundtrip(tmp_path: Path) -> None:
    bbox = BBox(1, 2, 3, 4)
    save_bbox(tmp_path, 0, bbox)
    assert load_bbox(tmp_path, 0) == bbox

    alignment = Alignment(
        pos=0, source="source.nd2", grid=GridSpec(rows=1, cols=1), excluded={2, 3}
    )
    save_alignment(tmp_path, alignment)
    loaded = load_alignment(tmp_path, 0)
    assert loaded == alignment


def test_roi_crop_index_generation(tmp_path: Path) -> None:
    data = np.arange(2 * 1 * 1 * 5 * 6, dtype=np.uint16).reshape(2, 1, 1, 5, 6)

    def read_frame(p: int, t: int, c: int, z: int) -> np.ndarray:
        assert p == 0
        return data[t, c, z]

    session = ReaderSession(ImageInfo(1, 2, 1, 1, 5, 6), read_frame, lambda: None)
    records = crop_rois(
        session,
        tmp_path,
        source="source",
        pos=0,
        grid=GridSpec(rows=1, cols=2, roi_width=2, roi_height=2, spacing_x=2, spacing_y=2),
        excluded={1},
    )
    assert len(records) == 1
    index = json.loads((tmp_path / "roi" / "Pos0" / "index.json").read_text())
    assert index["rois"][0]["bbox"] == {"x": 0, "y": 0, "width": 2, "height": 2}
    workspace = scan_roi_workspace(tmp_path)
    assert len(workspace.records) == 1


def test_annotation_save_load(tmp_path: Path) -> None:
    mask = np.array([[True, False], [False, True]])
    annotation = save_annotation(
        tmp_path,
        pos=1,
        roi=2,
        channel=3,
        time=4,
        z=5,
        label_id="positive",
        mask=mask,
    )
    loaded, loaded_mask = load_annotation(tmp_path, pos=1, roi=2, channel=3, time=4, z=5)
    assert loaded == annotation
    assert np.array_equal(loaded_mask, mask)
