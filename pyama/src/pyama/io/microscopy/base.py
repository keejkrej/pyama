"""Microscopy file loading utilities for ND2 and CZI data."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import nd2
import numpy as np
from pylibCZIrw import czi as czi_api

logger = logging.getLogger(__name__)


def _range_size(bounds: tuple[int, int] | None) -> int:
    if bounds is None:
        return 1
    start, end = bounds
    return max(int(end) - int(start), 1)


def _ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_channel_names(channel_names: list[str], n_channels: int) -> list[str]:
    normalized = [str(name) for name in channel_names if str(name).strip()]
    if len(normalized) >= n_channels:
        return normalized[:n_channels]
    return normalized + [f"C{i}" for i in range(len(normalized), n_channels)]


def _normalize_timepoints(timepoints: list[float], n_frames: int) -> list[float]:
    normalized = [float(value) for value in timepoints[:n_frames]]
    if len(normalized) >= n_frames:
        return normalized
    return normalized + [float(i) for i in range(len(normalized), n_frames)]


def _iter_nested_dicts(node: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        found.append(node)
        for value in node.values():
            found.extend(_iter_nested_dicts(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_iter_nested_dicts(item))
    return found


def _extract_czi_channel_names(metadata: dict[str, Any], n_channels: int) -> list[str]:
    image_info = (
        metadata.get("ImageDocument", {})
        .get("Metadata", {})
        .get("Information", {})
        .get("Image", {})
    )
    channel_nodes = (
        image_info.get("Dimensions", {}).get("Channels", {}).get("Channel", [])
    )
    channel_names: list[str] = []
    for node in _ensure_list(channel_nodes):
        if not isinstance(node, dict):
            continue
        name = (
            node.get("@Name")
            or node.get("Name")
            or node.get("@ShortName")
            or node.get("ShortName")
            or node.get("@Id")
            or node.get("Id")
        )
        if name is not None:
            channel_names.append(str(name))
    return _normalize_channel_names(channel_names, n_channels)


def _extract_czi_timepoints(metadata: dict[str, Any], n_frames: int) -> list[float]:
    if n_frames <= 0:
        return []
    timepoints: list[float] = []
    for node in _iter_nested_dicts(metadata):
        for key in ("@DeltaT", "DeltaT", "@Time", "Time", "@Timestamp", "Timestamp"):
            if key not in node:
                continue
            value = _to_float(node[key])
            if value is not None:
                timepoints.append(value)
    if len(timepoints) >= n_frames:
        return _normalize_timepoints(timepoints, n_frames)
    return [float(i) for i in range(n_frames)]


@dataclass
class MicroscopyMetadata:
    """Metadata for microscopy files."""

    file_path: Path
    base_name: str
    file_type: str
    height: int
    width: int
    n_frames: int
    channel_names: list[str]
    dtype: str
    timepoints: list[float] = field(default_factory=list)
    fov_list: list[int] = field(default_factory=lambda: [0])

    @property
    def n_fovs(self) -> int:
        return len(self.fov_list)

    @property
    def n_channels(self) -> int:
        return len(self.channel_names)


class NikonImage:
    """Direct ND2 reader wrapper."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self._reader = nd2.ND2File(str(file_path))
        self.sizes = dict(self._reader.sizes)
        self._dim_order = [dim for dim in self.sizes.keys() if dim not in ("Y", "X")]
        self._dask_array = self._reader.to_dask()
        self._dims = SimpleNamespace(
            T=int(self.sizes.get("T", 1)),
            C=int(self.sizes.get("C", 1)),
            Y=int(self.sizes.get("Y", 0)),
            X=int(self.sizes.get("X", 0)),
        )
        self._channel_names = self._load_channel_names()
        self._timepoints = self._load_timepoints()
        self._shape = tuple(int(value) for value in self._reader.shape)

    @property
    def dims(self) -> SimpleNamespace:
        return self._dims

    @property
    def shape(self) -> tuple[int, ...]:
        return self._shape

    @property
    def channel_names(self) -> list[str]:
        return list(self._channel_names)

    @property
    def timepoints(self) -> list[float]:
        return list(self._timepoints)

    @property
    def dtype(self) -> str:
        return str(self._reader.dtype)

    @property
    def fov_list(self) -> list[int]:
        return list(range(int(self.sizes.get("P", 1))))

    @property
    def closed(self) -> bool:
        return bool(getattr(self._reader, "closed", False))

    def close(self) -> None:
        self._reader.close()

    def get_frame(
        self,
        fov_idx: int,
        channel_idx: int,
        time_idx: int,
        z_idx: int = 0,
    ) -> np.ndarray:
        coords = {"P": fov_idx, "T": time_idx, "C": channel_idx, "Z": z_idx}
        index = tuple(coords.get(dim, 0) for dim in self._dim_order)
        return np.asarray(self._dask_array[index].compute())

    def _load_channel_names(self) -> list[str]:
        try:
            metadata = self._reader.metadata
            if metadata and hasattr(metadata, "channels"):
                return _normalize_channel_names(
                    [ch.channel.name for ch in metadata.channels],
                    self._dims.C,
                )
        except Exception:
            logger.debug("Falling back to default ND2 channel names", exc_info=True)
        return [f"C{i}" for i in range(self._dims.C)]

    def _load_timepoints(self) -> list[float]:
        try:
            events = self._reader.events()
            if hasattr(events, "to_dict"):
                records = events.to_dict("records")
            else:
                records = list(events) if events is not None else []
            timepoints: list[float] = []
            for index, event in enumerate(records):
                value = event.get("Time", index) if isinstance(event, dict) else index
                numeric = _to_float(value)
                timepoints.append(float(index) if numeric is None else numeric)
            if timepoints:
                return _normalize_timepoints(timepoints, self._dims.T)
        except Exception:
            logger.debug("Falling back to default ND2 timepoints", exc_info=True)
        return [float(i) for i in range(self._dims.T)]


class ZeissImage:
    """Direct CZI reader wrapper."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self._reader = czi_api.CziReader(str(file_path))
        self._closed = False
        self._metadata = self._load_metadata()
        self._scene_ids, self._height, self._width = self._load_scene_info()
        total_bounds = self._reader.total_bounding_box_no_pyramid
        self._dims = SimpleNamespace(
            T=_range_size(total_bounds.get("T")),
            C=_range_size(total_bounds.get("C")),
            Y=self._height,
            X=self._width,
        )
        self._channel_names = _extract_czi_channel_names(self._metadata, self._dims.C)
        self._timepoints = _extract_czi_timepoints(self._metadata, self._dims.T)
        self._shape = (
            len(self._scene_ids),
            self._dims.T,
            self._dims.C,
            self._dims.Y,
            self._dims.X,
        )

    @property
    def dims(self) -> SimpleNamespace:
        return self._dims

    @property
    def shape(self) -> tuple[int, ...]:
        return self._shape

    @property
    def channel_names(self) -> list[str]:
        return list(self._channel_names)

    @property
    def timepoints(self) -> list[float]:
        return list(self._timepoints)

    @property
    def dtype(self) -> str:
        try:
            sample = self.get_frame(0, 0, 0)
        except Exception:
            return "unknown"
        return str(sample.dtype)

    @property
    def fov_list(self) -> list[int]:
        return list(range(len(self._scene_ids)))

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._reader.close()
        self._closed = True

    def get_frame(
        self,
        fov_idx: int,
        channel_idx: int,
        time_idx: int,
        z_idx: int = 0,
    ) -> np.ndarray:
        scene_id = self._scene_ids[fov_idx]
        plane = {"T": time_idx, "C": channel_idx, "Z": z_idx}
        frame = np.asarray(self._reader.read(scene=scene_id, plane=plane))
        frame = np.squeeze(frame)
        if frame.ndim != 2:
            raise ValueError(
                f"Expected a 2D frame for scene {scene_id}, got shape {frame.shape}"
            )
        if frame.shape != (self._height, self._width):
            raise ValueError(
                f"CZI scene {scene_id} returned shape {frame.shape}, expected {(self._height, self._width)}"
            )
        return frame

    def _load_metadata(self) -> dict[str, Any]:
        try:
            metadata = self._reader.metadata
            return metadata if isinstance(metadata, dict) else {}
        except Exception:
            logger.debug("Falling back to empty CZI metadata", exc_info=True)
            return {}

    def _load_scene_info(self) -> tuple[list[int], int, int]:
        total_bounds = self._reader.total_bounding_box_no_pyramid
        default_height = _range_size(total_bounds.get("Y"))
        default_width = _range_size(total_bounds.get("X"))
        try:
            scene_rects = self._reader.scenes_bounding_rectangle_no_pyramid
        except Exception:
            logger.debug("Falling back to a single CZI FOV", exc_info=True)
            return [0], default_height, default_width

        if not scene_rects:
            return [0], default_height, default_width

        scene_ids = sorted(int(scene_id) for scene_id in scene_rects)
        scene_sizes = {
            scene_id: (int(scene_rects[scene_id].h), int(scene_rects[scene_id].w))
            for scene_id in scene_ids
        }
        unique_sizes = set(scene_sizes.values())
        if len(unique_sizes) != 1:
            raise ValueError(
                "CZI scenes must have identical layer-0 dimensions to be treated as FOVs"
            )
        height, width = next(iter(unique_sizes))
        return scene_ids, height, width


MicroscopyImage = NikonImage | ZeissImage


def load_microscopy_file(file_path: Path) -> tuple[MicroscopyImage, MicroscopyMetadata]:
    """Load a microscopy file and return the reader object and extracted metadata."""
    file_path = Path(file_path)
    file_type = file_path.suffix.lower().lstrip(".")
    if file_type not in {"nd2", "czi"}:
        raise ValueError(
            f"Unsupported microscopy file '{file_path.name}'. Only .nd2 and .czi are supported."
        )

    try:
        if file_type == "nd2":
            reader: MicroscopyImage = NikonImage(file_path)
        else:
            reader = ZeissImage(file_path)

        metadata = MicroscopyMetadata(
            file_path=file_path,
            base_name=file_path.stem,
            file_type=file_type,
            height=int(reader.dims.Y),
            width=int(reader.dims.X),
            n_frames=int(reader.dims.T),
            channel_names=reader.channel_names,
            dtype=reader.dtype,
            timepoints=reader.timepoints,
            fov_list=reader.fov_list,
        )
        return reader, metadata
    except Exception as exc:
        logger.exception("Failed to load microscopy file %s", file_path)
        raise RuntimeError(f"Failed to load {file_type.upper()} file: {exc}") from exc


def get_microscopy_frame(
    img: MicroscopyImage,
    fov: int,
    channel: int,
    time: int,
    z: int = 0,
) -> np.ndarray:
    """Return a single microscopy frame as a numpy array."""
    return img.get_frame(fov, channel, time, z)


def get_microscopy_channel_stack(
    img: MicroscopyImage, fov: int, time: int
) -> np.ndarray:
    """Return a channel stack with shape ``(C, H, W)``."""
    channel_frames = [
        get_microscopy_frame(img, fov, channel, time)
        for channel in range(int(img.dims.C))
    ]
    return np.stack(channel_frames, axis=0)


def get_microscopy_time_stack(
    img: MicroscopyImage, fov: int, channel: int
) -> np.ndarray:
    """Return a time stack with shape ``(T, H, W)``."""
    time_frames = [
        get_microscopy_frame(img, fov, channel, time) for time in range(int(img.dims.T))
    ]
    return np.stack(time_frames, axis=0)
