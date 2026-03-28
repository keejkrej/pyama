from pathlib import Path
from typing import Literal

import numpy as np
import zarr
from zarr.codecs import BloscCodec

from pyama.types.io import MicroscopyMetadata


class RawZarrSchema:
    def raw_path(self, position_id: int, channel_id: int) -> str:
        return f"position/{int(position_id)}/channel/{int(channel_id)}/raw"

    def seg_labeled_path(self, position_id: int, channel_id: int) -> str:
        return f"position/{int(position_id)}/channel/{int(channel_id)}/seg_labeled"

    def seg_tracked_path(self, position_id: int, channel_id: int) -> str:
        return f"position/{int(position_id)}/channel/{int(channel_id)}/seg_tracked"

    def fl_background_path(self, position_id: int, channel_id: int) -> str:
        return f"position/{int(position_id)}/channel/{int(channel_id)}/fl_background"

    def channel_group_path(self, position_id: int) -> str:
        return f"position/{int(position_id)}/channel"


class RoisZarrSchema:
    def roi_ids_path(self, position_id: int) -> str:
        return f"position/{int(position_id)}/metadata/roi_ids"

    def roi_bboxes_path(self, position_id: int) -> str:
        return f"position/{int(position_id)}/metadata/roi_bboxes"

    def channel_group_path(self, position_id: int) -> str:
        return f"position/{int(position_id)}/channel"

    def roi_group_path(
        self,
        position_id: int,
        channel_id: int,
    ) -> str:
        return f"{self.channel_group_path(position_id)}/{int(channel_id)}/roi"

    def roi_raw_path(
        self,
        position_id: int,
        channel_id: int,
        roi_id: int,
    ) -> str:
        return f"{self.roi_group_path(position_id, channel_id)}/{int(roi_id)}/raw"

    def roi_raw_frame_group_path(
        self,
        position_id: int,
        channel_id: int,
        roi_id: int,
    ) -> str:
        return f"{self.roi_raw_path(position_id, channel_id, roi_id)}/frame"

    def roi_raw_frame_path(
        self,
        position_id: int,
        channel_id: int,
        roi_id: int,
        frame_idx: int,
    ) -> str:
        return (
            f"position/{int(position_id)}/channel/{int(channel_id)}/roi/"
            f"{int(roi_id)}/raw/frame/{int(frame_idx)}"
        )

    def roi_background_frame_path(
        self,
        position_id: int,
        channel_id: int,
        roi_id: int,
        frame_idx: int,
    ) -> str:
        return (
            f"position/{int(position_id)}/channel/{int(channel_id)}/roi/"
            f"{int(roi_id)}/fl_background/frame/{int(frame_idx)}"
        )

_DEFAULT_CNAME = "zstd"
_DEFAULT_CLEVEL = 5
_DEFAULT_SHUFFLE = "shuffle"
ZarrOpenMode = Literal["r", "r+", "a", "w", "w-"]


def default_compressors() -> list[BloscCodec]:
    return [
        BloscCodec(
            cname=_DEFAULT_CNAME,
            clevel=_DEFAULT_CLEVEL,
            shuffle=_DEFAULT_SHUFFLE,
        )
    ]


def require_group(
    node: zarr.Array | zarr.Group | None,
    *,
    path: str,
) -> zarr.Group:
    if node is None:
        raise KeyError(path)
    if isinstance(node, zarr.Group):
        return node
    raise TypeError(f"Expected Zarr group at {path}, found array")


def require_array(
    node: zarr.Array | zarr.Group | None,
    *,
    path: str,
) -> zarr.Array:
    if node is None:
        raise KeyError(path)
    if isinstance(node, zarr.Array):
        return node
    raise TypeError(f"Expected Zarr array at {path}, found group")


def get_required_array(root: zarr.Group, path: str) -> zarr.Array:
    return require_array(root.get(path), path=path)


def get_optional_array(root: zarr.Group, path: str) -> zarr.Array | None:
    node = root.get(path)
    if node is None:
        return None
    return require_array(node, path=path)


def has_array(root: zarr.Group, path: str) -> bool:
    return get_optional_array(root, path) is not None


def _raw_dataset_attrs(
    *,
    metadata: MicroscopyMetadata,
    position_id: int,
    position_index: int,
    channel_id: int,
) -> dict[str, int | str]:
    return {
        "source_file_path": str(metadata.file_path),
        "source_file_type": metadata.file_type,
        "position_id": int(position_id),
        "position_index": int(position_index),
        "channel_id": int(channel_id),
        "n_frames": int(metadata.n_frames),
        "height": int(metadata.height),
        "width": int(metadata.width),
    }


def _segmentation_dataset_attrs(
    *,
    metadata: MicroscopyMetadata,
    position_id: int,
    position_index: int,
    channel_id: int,
) -> dict[str, int | str]:
    return _raw_dataset_attrs(
        metadata=metadata,
        position_id=position_id,
        position_index=position_index,
        channel_id=channel_id,
    )


def _tracking_dataset_attrs(
    *,
    metadata: MicroscopyMetadata,
    position_id: int,
    position_index: int,
    channel_id: int,
) -> dict[str, int | str]:
    return _raw_dataset_attrs(
        metadata=metadata,
        position_id=position_id,
        position_index=position_index,
        channel_id=channel_id,
    )


def _background_dataset_attrs(
    *,
    metadata: MicroscopyMetadata,
    position_id: int,
    position_index: int,
    channel_id: int,
    method: str,
) -> dict[str, int | float | str]:
    attrs: dict[str, int | float | str] = {
        **_raw_dataset_attrs(
            metadata=metadata,
            position_id=position_id,
            position_index=position_index,
            channel_id=channel_id,
        )
    }
    attrs["background_method"] = method
    return attrs


class RawZarrStore(RawZarrSchema):
    __slots__ = ("root",)

    def __init__(self, root: zarr.Group) -> None:
        self.root = root

    root: zarr.Group

    def dataset_exists(self, path: str) -> bool:
        return has_array(self.root, path)

    def get_required_array(self, path: str) -> zarr.Array:
        return get_required_array(self.root, path)

    def get_optional_array(self, path: str) -> zarr.Array | None:
        return get_optional_array(self.root, path)

    def read_uint16_3d(self, path: str) -> np.ndarray:
        return np.asarray(self.get_required_array(path)[:], dtype=np.uint16)

    def read_uint16_frame(self, path: str, frame_idx: int) -> np.ndarray:
        return np.asarray(self.get_required_array(path)[int(frame_idx)], dtype=np.uint16)

    def _write_uint16_frame(self, path: str, frame_idx: int, data: np.ndarray) -> None:
        self.get_required_array(path)[int(frame_idx)] = np.asarray(data, dtype=np.uint16)

    def create_uint16_timeseries(
        self,
        path: str,
        *,
        n_frames: int,
        height: int,
        width: int,
    ) -> zarr.Array:
        return self.root.create_array(
            name=path,
            shape=(int(n_frames), int(height), int(width)),
            chunks=(1, int(height), int(width)),
            dtype="uint16",
            compressors=default_compressors(),
        )

    def create_raw_dataset(
        self,
        *,
        metadata: MicroscopyMetadata,
        position_id: int,
        position_index: int,
        channel_id: int,
    ) -> zarr.Array:
        dataset = self.create_uint16_timeseries(
            self.raw_path(position_id, channel_id),
            n_frames=metadata.n_frames,
            height=metadata.height,
            width=metadata.width,
        )
        dataset.attrs.update(
            _raw_dataset_attrs(
                metadata=metadata,
                position_id=position_id,
                position_index=position_index,
                channel_id=channel_id,
            )
        )
        return dataset

    def create_seg_labeled_dataset(
        self,
        *,
        metadata: MicroscopyMetadata,
        position_id: int,
        position_index: int,
        channel_id: int,
    ) -> zarr.Array:
        dataset = self.create_uint16_timeseries(
            self.seg_labeled_path(position_id, channel_id),
            n_frames=metadata.n_frames,
            height=metadata.height,
            width=metadata.width,
        )
        dataset.attrs.update(
            _segmentation_dataset_attrs(
                metadata=metadata,
                position_id=position_id,
                position_index=position_index,
                channel_id=channel_id,
            )
        )
        return dataset

    def create_seg_tracked_dataset(
        self,
        *,
        metadata: MicroscopyMetadata,
        position_id: int,
        position_index: int,
        channel_id: int,
    ) -> zarr.Array:
        dataset = self.create_uint16_timeseries(
            self.seg_tracked_path(position_id, channel_id),
            n_frames=metadata.n_frames,
            height=metadata.height,
            width=metadata.width,
        )
        dataset.attrs.update(
            _tracking_dataset_attrs(
                metadata=metadata,
                position_id=position_id,
                position_index=position_index,
                channel_id=channel_id,
            )
        )
        return dataset

    def create_fl_background_dataset(
        self,
        *,
        metadata: MicroscopyMetadata,
        position_id: int,
        position_index: int,
        channel_id: int,
        method: str,
    ) -> zarr.Array:
        dataset = self.create_uint16_timeseries(
            self.fl_background_path(position_id, channel_id),
            n_frames=metadata.n_frames,
            height=metadata.height,
            width=metadata.width,
        )
        dataset.attrs.update(
            _background_dataset_attrs(
                metadata=metadata,
                position_id=position_id,
                position_index=position_index,
                channel_id=channel_id,
                method=method,
            )
        )
        return dataset

    def read_raw_frame(self, position_id: int, channel_id: int, frame_idx: int) -> np.ndarray:
        return self.read_uint16_frame(self.raw_path(position_id, channel_id), frame_idx)

    def read_seg_labeled_3d(self, position_id: int, channel_id: int) -> np.ndarray:
        return self.read_uint16_3d(self.seg_labeled_path(position_id, channel_id))

    def read_fl_background_frame(self, position_id: int, channel_id: int, frame_idx: int) -> np.ndarray:
        return self.read_uint16_frame(self.fl_background_path(position_id, channel_id), frame_idx)

    def write_raw_frame(self, position_id: int, channel_id: int, frame_idx: int, data: np.ndarray) -> None:
        self._write_uint16_frame(self.raw_path(position_id, channel_id), frame_idx, data)

    def write_seg_labeled_frame(
        self,
        position_id: int,
        channel_id: int,
        frame_idx: int,
        data: np.ndarray,
    ) -> None:
        self._write_uint16_frame(self.seg_labeled_path(position_id, channel_id), frame_idx, data)

    def write_seg_tracked_3d(self, position_id: int, channel_id: int, data: np.ndarray) -> None:
        self.get_required_array(self.seg_tracked_path(position_id, channel_id))[:] = np.asarray(
            data,
            dtype=np.uint16,
        )

    def write_fl_background_frame(
        self,
        position_id: int,
        channel_id: int,
        frame_idx: int,
        data: np.ndarray,
    ) -> None:
        self._write_uint16_frame(self.fl_background_path(position_id, channel_id), frame_idx, data)

    def list_position_ids(self) -> list[int]:
        node = self.root.get("position")
        if node is None:
            return []
        group = require_group(node, path="position")
        return sorted(int(value) for value in group.group_keys())

    def list_channel_ids(self, position_id: int) -> list[int]:
        path = self.channel_group_path(position_id)
        node = self.root.get(path)
        if node is None:
            return []
        group = require_group(node, path=path)
        return sorted(int(value) for value in group.group_keys())


class RoisZarrStore(RoisZarrSchema):
    __slots__ = ("root",)

    def __init__(self, root: zarr.Group) -> None:
        self.root = root

    root: zarr.Group

    def dataset_exists(self, path: str) -> bool:
        return has_array(self.root, path)

    def get_required_array(self, path: str) -> zarr.Array:
        return get_required_array(self.root, path)

    def get_optional_array(self, path: str) -> zarr.Array | None:
        return get_optional_array(self.root, path)

    def read_bool_2d(self, path: str) -> np.ndarray:
        return np.asarray(self.get_required_array(path)[:], dtype=bool)

    def read_uint16_2d(self, path: str) -> np.ndarray:
        return np.asarray(self.get_required_array(path)[:], dtype=np.uint16)

    def read_int32_1d(self, path: str) -> np.ndarray:
        return np.asarray(self.get_required_array(path)[:], dtype=np.int32)

    def read_int32_2d(self, path: str) -> np.ndarray:
        return np.asarray(self.get_required_array(path)[:], dtype=np.int32)

    def write_array(self, path: str, data: np.ndarray) -> zarr.Array:
        if data.ndim == 0:
            return self.root.create_array(
                name=path,
                data=data,
                compressors=default_compressors(),
            )
        chunks = tuple(int(size) for size in data.shape)
        return self.root.create_array(
            name=path,
            data=data,
            chunks=chunks,
            compressors=default_compressors(),
        )

    def write_roi_ids(self, position_id: int, roi_ids: np.ndarray) -> zarr.Array:
        return self.write_array(self.roi_ids_path(position_id), np.asarray(roi_ids, dtype=np.int32))

    def write_roi_bboxes(self, position_id: int, roi_bboxes: np.ndarray) -> zarr.Array:
        return self.write_array(self.roi_bboxes_path(position_id), np.asarray(roi_bboxes, dtype=np.int32))

    def read_roi_ids(self, position_id: int) -> np.ndarray:
        return self.read_int32_1d(self.roi_ids_path(position_id))

    def read_roi_bboxes(self, position_id: int) -> np.ndarray:
        return self.read_int32_2d(self.roi_bboxes_path(position_id))

    def write_roi_raw_frame(
        self,
        position_id: int,
        channel_id: int,
        roi_id: int,
        frame_idx: int,
        data: np.ndarray,
    ) -> zarr.Array:
        return self.write_array(
            self.roi_raw_frame_path(position_id, channel_id, roi_id, frame_idx),
            np.asarray(data, dtype=np.uint16),
        )

    def write_roi_background_frame(
        self,
        position_id: int,
        channel_id: int,
        roi_id: int,
        frame_idx: int,
        data: np.ndarray,
    ) -> zarr.Array:
        return self.write_array(
            self.roi_background_frame_path(position_id, channel_id, roi_id, frame_idx),
            np.asarray(data, dtype=np.uint16),
        )

    def read_roi_raw_frame(
        self,
        position_id: int,
        channel_id: int,
        roi_id: int,
        frame_idx: int,
    ) -> np.ndarray:
        return self.read_uint16_2d(self.roi_raw_frame_path(position_id, channel_id, roi_id, frame_idx))

    def read_roi_background_frame(
        self,
        position_id: int,
        channel_id: int,
        roi_id: int,
        frame_idx: int,
    ) -> np.ndarray:
        return self.read_uint16_2d(self.roi_background_frame_path(position_id, channel_id, roi_id, frame_idx))

    def list_position_ids(self) -> list[int]:
        node = self.root.get("position")
        if node is None:
            return []
        group = require_group(node, path="position")
        return sorted(int(value) for value in group.group_keys())

    def list_channel_ids(self, position_id: int) -> list[int]:
        path = self.channel_group_path(position_id)
        node = self.root.get(path)
        if node is None:
            return []
        group = require_group(node, path=path)
        return sorted(int(value) for value in group.group_keys())

    def list_channel_roi_ids(self, position_id: int, channel_id: int) -> list[int]:
        path = self.roi_group_path(position_id, channel_id)
        node = self.root.get(path)
        if node is None:
            return []
        group = require_group(node, path=path)
        return sorted(int(value) for value in group.group_keys())

    def list_roi_raw_frame_indices(
        self,
        position_id: int,
        channel_id: int,
        roi_id: int,
    ) -> list[int]:
        path = self.roi_raw_frame_group_path(position_id, channel_id, roi_id)
        node = self.root.get(path)
        if node is None:
            return []
        group = require_group(node, path=path)
        return sorted(int(value) for value in group.array_keys())


def open_raw_zarr(path: Path, mode: ZarrOpenMode) -> RawZarrStore:
    return RawZarrStore(root=zarr.open_group(path, mode=mode))


def open_rois_zarr(path: Path, mode: ZarrOpenMode) -> RoisZarrStore:
    return RoisZarrStore(root=zarr.open_group(path, mode=mode))


__all__ = [
    "RawZarrStore",
    "RawZarrSchema",
    "RoisZarrStore",
    "RoisZarrSchema",
    "ZarrOpenMode",
    "default_compressors",
    "get_optional_array",
    "get_required_array",
    "has_array",
    "open_raw_zarr",
    "open_rois_zarr",
    "require_array",
    "require_group",
]
