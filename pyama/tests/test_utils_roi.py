import numpy as np

from pyama.utils.roi import (
    build_frame_roi_metadata,
    build_union_roi_metadata,
    regions_from_labeled,
)


def test_regions_from_labeled_returns_bbox_by_label() -> None:
    labeled = np.array(
        [
            [0, 1, 1],
            [0, 1, 1],
            [2, 2, 0],
        ],
        dtype=np.uint16,
    )

    assert regions_from_labeled(labeled) == {
        1: (0, 1, 2, 3),
        2: (2, 0, 3, 2),
    }


def test_build_frame_roi_metadata_preserves_per_frame_boxes() -> None:
    seg = np.zeros((2, 4, 4), dtype=np.uint16)
    seg[0, 1:3, 1:3] = 1
    seg[1, 0:2, 0:2] = 1

    roi_ids, roi_bboxes, roi_present = build_frame_roi_metadata(seg)

    np.testing.assert_array_equal(roi_ids, np.array([1], dtype=np.int32))
    np.testing.assert_array_equal(roi_present, np.array([[True, True]]))
    np.testing.assert_array_equal(
        roi_bboxes[0],
        np.array([[1, 1, 2, 2], [0, 0, 2, 2]], dtype=np.int32),
    )


def test_build_union_roi_metadata_repeats_union_box() -> None:
    seg = np.zeros((2, 4, 4), dtype=np.uint16)
    seg[0, 1:3, 1:3] = 1
    seg[1, 0:2, 0:2] = 1

    roi_ids, roi_bboxes, roi_present = build_union_roi_metadata(seg)

    np.testing.assert_array_equal(roi_ids, np.array([1], dtype=np.int32))
    np.testing.assert_array_equal(roi_present, np.array([[True, True]]))
    np.testing.assert_array_equal(
        roi_bboxes[0],
        np.array([[0, 0, 3, 3], [0, 0, 3, 3]], dtype=np.int32),
    )


def test_build_roi_metadata_handles_empty_segmentation() -> None:
    seg = np.zeros((2, 3, 3), dtype=np.uint16)

    frame_roi_ids, frame_boxes, frame_present = build_frame_roi_metadata(seg)
    union_roi_ids, union_boxes, union_present = build_union_roi_metadata(seg)

    assert frame_roi_ids.shape == (0,)
    assert frame_boxes.shape == (0, 2, 4)
    assert frame_present.shape == (0, 2)
    assert union_roi_ids.shape == (0,)
    assert union_boxes.shape == (0, 2, 4)
    assert union_present.shape == (0, 2)
