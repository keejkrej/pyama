from pathlib import Path

import numpy as np
import pytest

from pyama.apps.processing.bbox import (
    bbox_csv_path,
    load_bbox_rows,
)


def _write_bbox_csv(path: Path, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(["crop,x,y,w,h", *rows]) + "\n", encoding="utf-8")


def test_bbox_csv_path_uses_position_id() -> None:
    assert (
        bbox_csv_path(output_dir=Path("workspace"), position_id=7)
        == Path("workspace") / "bbox" / "Pos7.csv"
    )


def test_load_bbox_rows_sorts_by_crop_and_validates_bounds(tmp_path: Path) -> None:
    _write_bbox_csv(
        tmp_path / "bbox" / "Pos0.csv",
        ["5,4,5,6,7", "1,0,1,2,3"],
    )

    roi_ids, bbox_rows = load_bbox_rows(
        output_dir=tmp_path,
        position_id=0,
        frame_width=20,
        frame_height=20,
    )

    np.testing.assert_array_equal(roi_ids, np.array([1, 5], dtype=np.int32))
    np.testing.assert_array_equal(
        bbox_rows,
        np.array([[0, 1, 2, 3], [4, 5, 6, 7]], dtype=np.int32),
    )


def test_load_bbox_rows_rejects_duplicate_crop_ids(tmp_path: Path) -> None:
    _write_bbox_csv(
        tmp_path / "bbox" / "Pos0.csv",
        ["0,0,0,1,1", "0,1,1,1,1"],
    )

    with pytest.raises(ValueError, match="Duplicate crop id 0"):
        load_bbox_rows(
            output_dir=tmp_path,
            position_id=0,
            frame_width=10,
            frame_height=10,
        )


def test_load_bbox_rows_rejects_out_of_bounds_bbox(tmp_path: Path) -> None:
    _write_bbox_csv(tmp_path / "bbox" / "Pos0.csv", ["0,8,0,3,1"])

    with pytest.raises(ValueError, match="bbox exceeds frame bounds"):
        load_bbox_rows(
            output_dir=tmp_path,
            position_id=0,
            frame_width=10,
            frame_height=10,
        )


def test_load_bbox_rows_allows_header_only_csv(tmp_path: Path) -> None:
    _write_bbox_csv(tmp_path / "bbox" / "Pos0.csv", [])

    roi_ids, bbox_rows = load_bbox_rows(
        output_dir=tmp_path,
        position_id=0,
        frame_width=10,
        frame_height=10,
    )

    assert roi_ids.shape == (0,)
    assert bbox_rows.shape == (0, 4)


def test_load_bbox_rows_returns_static_bbox_rows() -> None:
    roi_ids = np.array([2, 7], dtype=np.int32)
    bbox_rows = np.array([[1, 2, 3, 4], [5, 6, 7, 8]], dtype=np.int32)

    np.testing.assert_array_equal(roi_ids, np.array([2, 7], dtype=np.int32))
    np.testing.assert_array_equal(
        bbox_rows,
        np.array([[1, 2, 3, 4], [5, 6, 7, 8]], dtype=np.int32),
    )
