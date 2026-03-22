"""Shared ROI and labeled-region helpers."""

import numpy as np
from skimage.measure import regionprops


def regions_from_labeled(labeled: np.ndarray) -> dict[int, tuple[int, int, int, int]]:
    regions: dict[int, tuple[int, int, int, int]] = {}
    for prop in regionprops(labeled):
        regions[int(prop.label)] = (
            int(prop.bbox[0]),
            int(prop.bbox[1]),
            int(prop.bbox[2]),
            int(prop.bbox[3]),
        )
    return regions


def build_frame_roi_metadata(seg_tracked: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n_frames = seg_tracked.shape[0]
    regions_all = [regions_from_labeled(seg_tracked[t]) for t in range(n_frames)]
    roi_ids = np.array(
        sorted({roi_id for regions in regions_all for roi_id in regions.keys()}),
        dtype=np.int32,
    )
    n_rois = int(roi_ids.size)

    roi_bboxes = np.zeros((n_rois, n_frames, 4), dtype=np.int32)
    roi_is_present = np.zeros((n_rois, n_frames), dtype=bool)
    if n_rois == 0:
        return roi_ids, roi_bboxes, roi_is_present

    for roi_idx, roi_id in enumerate(roi_ids):
        for frame_idx, regions in enumerate(regions_all):
            bbox = regions.get(int(roi_id))
            if bbox is None:
                continue
            roi_is_present[roi_idx, frame_idx] = True
            roi_bboxes[roi_idx, frame_idx] = np.array(
                [bbox[1], bbox[0], bbox[3] - bbox[1], bbox[2] - bbox[0]],
                dtype=np.int32,
            )

    return roi_ids, roi_bboxes, roi_is_present


def build_union_roi_metadata(seg_tracked: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n_frames = seg_tracked.shape[0]
    regions_all = [regions_from_labeled(seg_tracked[t]) for t in range(n_frames)]
    roi_ids = np.array(
        sorted({roi_id for regions in regions_all for roi_id in regions.keys()}),
        dtype=np.int32,
    )
    n_rois = int(roi_ids.size)

    roi_bboxes = np.zeros((n_rois, n_frames, 4), dtype=np.int32)
    roi_is_present = np.zeros((n_rois, n_frames), dtype=bool)
    if n_rois == 0:
        return roi_ids, roi_bboxes, roi_is_present

    roi_union_bboxes = np.zeros((n_rois, 4), dtype=np.int32)
    for roi_idx, roi_id in enumerate(roi_ids):
        y0s: list[int] = []
        x0s: list[int] = []
        y1s: list[int] = []
        x1s: list[int] = []
        for frame_idx, regions in enumerate(regions_all):
            bbox = regions.get(int(roi_id))
            if bbox is None:
                continue
            roi_is_present[roi_idx, frame_idx] = True
            y0s.append(bbox[0])
            x0s.append(bbox[1])
            y1s.append(bbox[2])
            x1s.append(bbox[3])
        if y0s:
            x0 = min(x0s)
            y0 = min(y0s)
            x1 = max(x1s)
            y1 = max(y1s)
            roi_union_bboxes[roi_idx] = np.array([x0, y0, x1 - x0, y1 - y0], dtype=np.int32)

    for roi_idx in range(n_rois):
        for frame_idx in range(n_frames):
            if roi_is_present[roi_idx, frame_idx]:
                roi_bboxes[roi_idx, frame_idx] = roi_union_bboxes[roi_idx]

    return roi_ids, roi_bboxes, roi_is_present


__all__ = [
    "build_frame_roi_metadata",
    "build_union_roi_metadata",
    "regions_from_labeled",
]
