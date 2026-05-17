from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pyama.adapters.base import ImageInfo, ReaderSession
from pyama.aligner_viewmodel import AlignerViewModel
from pyama.annotations import load_annotation
from pyama.annotator_viewmodel import AnnotatorViewModel
from pyama.grid import BBox, GridSpec
from pyama.roi_io import read_roi_stack
from pyama.workspace import (
    RoiRecord,
    load_alignment,
    load_bbox,
    write_roi_index,
    write_roi_tiff,
)


def test_aligner_view_model_grid_auto_exclude_and_save(tmp_path: Path) -> None:
    closed = False

    def read_frame(pos: int, time: int, channel: int, z: int) -> np.ndarray:
        assert (pos, time, channel, z) in {(0, 0, 0, 0), (0, 0, 0, 0)}
        return np.zeros((20, 20), dtype=np.uint8)

    def close() -> None:
        nonlocal closed
        closed = True

    def open_fake(path: Path) -> ReaderSession:
        assert path.name == "source.nd2"
        return ReaderSession(ImageInfo(1, 1, 1, 1, size_y=20, size_x=20), read_frame, close)

    vm = AlignerViewModel(reader_factory=open_fake)
    emitted_grids: list[tuple[int, set[int]]] = []
    vm.grid_changed.connect(
        lambda cells, excluded, _hit_test: emitted_grids.append((len(cells), set(excluded)))
    )
    vm.set_workspace_path(tmp_path)
    vm.open_source(tmp_path / "source.nd2")
    vm.set_grid_spec(
        GridSpec(
            kind="hex",
            rows=2,
            cols=2,
            roi_width=10,
            roi_height=10,
            spacing_x=10,
            spacing_y=10,
        )
    )

    vm.auto_exclude()
    assert vm.excluded == {3}
    assert emitted_grids[-1] == (4, {3})

    vm.toggle_cell(0)
    assert vm.excluded == {0, 3}
    vm.save_alignment_files()

    alignment = load_alignment(tmp_path, 0)
    assert alignment is not None
    assert alignment.grid.rows == 2
    assert alignment.excluded == {0, 3}
    assert load_bbox(tmp_path, 0) == BBox(5, 0, 15, 20)

    vm.close()
    assert closed


def test_annotator_view_model_workspace_editing_labels_and_save(tmp_path: Path) -> None:
    roi_dir = tmp_path / "roi" / "Pos0"
    roi_dir.mkdir(parents=True)
    stack = np.zeros((2, 1, 1, 5, 5), dtype=np.uint8)
    stack[1, 0, 0] = 7
    write_roi_tiff(roi_dir / "Roi0.tif", stack)
    write_roi_index(
        tmp_path,
        0,
        "source",
        GridSpec(rows=1, cols=1),
        set(),
        [
            RoiRecord(
                pos=0,
                roi=0,
                path="Roi0.tif",
                bbox=BBox(0, 0, 5, 5),
                row=0,
                col=0,
                shape=stack.shape,
            )
        ],
    )

    vm = AnnotatorViewModel(tmp_path)
    masks: list[np.ndarray | None] = []
    vm.mask_changed.connect(lambda mask: masks.append(None if mask is None else mask.copy()))

    vm.load_workspace(tmp_path)
    assert len(vm.records) == 1
    assert vm.stack is not None
    assert vm.stack.shape == stack.shape

    vm.set_frame_indices(1, 0, 0)
    vm.add_label("Cell Body")
    assert vm.label_id == "cell_body"
    assert any(label.id == "cell_body" for label in vm.labels)

    vm.paint_at(2, 2, "brush", 1)
    assert vm.mask is not None
    assert int(vm.mask.sum()) == 5
    vm.undo()
    assert int(vm.mask.sum()) == 0
    vm.redo()
    assert int(vm.mask.sum()) == 5

    vm.discard()
    vm.add_lasso_point(0, 0)
    vm.add_lasso_point(4, 0)
    vm.add_lasso_point(0, 4)
    vm.fill_lasso()
    assert vm.mask is not None
    assert vm.mask.sum() > 0

    vm.save_current()
    annotation, saved_mask = load_annotation(tmp_path, pos=0, roi=0, channel=0, time=1, z=0)
    assert annotation is not None
    assert annotation.label_id == "cell_body"
    assert np.array_equal(saved_mask, vm.mask)

    vm.remove_label("cell_body")
    assert all(label.id != "cell_body" for label in vm.labels)
    assert masks


@pytest.mark.parametrize(
    ("stack", "shape"),
    [
        (np.zeros((3, 4), dtype=np.uint8), (1, 1, 1, 3, 4)),
        (np.zeros((2, 3, 4), dtype=np.uint8), (2, 1, 1, 3, 4)),
        (np.zeros((2, 3, 4, 5), dtype=np.uint8), (2, 3, 1, 4, 5)),
        (np.zeros((2, 3, 4, 5, 6), dtype=np.uint8), (2, 3, 4, 5, 6)),
    ],
)
def test_read_roi_stack_normalizes_tiff_shapes(
    monkeypatch: pytest.MonkeyPatch, stack, shape
) -> None:
    import tifffile

    monkeypatch.setattr(tifffile, "imread", lambda _path: stack)
    assert read_roi_stack(Path("roi.tif")).shape == shape
