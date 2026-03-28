"""I/O-related value objects."""

from dataclasses import dataclass
from pathlib import Path

from pyama.types.processing import Channels


@dataclass(frozen=True, slots=True)
class MicroscopyMetadata:
    file_path: Path
    base_name: str
    file_type: str
    height: int
    width: int
    n_frames: int
    channel_names: tuple[str, ...]
    dtype: str
    timepoints: tuple[float, ...] = ()
    position_list: tuple[int, ...] = (0,)
    z_slices: tuple[int, ...] = (0,)

    def __post_init__(self) -> None:
        object.__setattr__(self, "channel_names", tuple(self.channel_names))
        object.__setattr__(self, "timepoints", tuple(float(value) for value in self.timepoints))
        object.__setattr__(self, "position_list", tuple(int(value) for value in self.position_list))
        object.__setattr__(self, "z_slices", tuple(int(value) for value in self.z_slices))
        if self.height < 0 or self.width < 0 or self.n_frames < 0:
            raise ValueError("MicroscopyMetadata dimensions must be >= 0")

    @property
    def n_positions(self) -> int:
        return len(self.position_list)

    @property
    def n_channels(self) -> int:
        return len(self.channel_names)

    @property
    def n_z(self) -> int:
        return len(self.z_slices)

type PositionArtifacts = dict[str, Path | str]


@dataclass(slots=True)
class ProcessingResults:
    project_path: Path
    n_positions: int
    position_data: dict[int, PositionArtifacts]
    channels: Channels | None = None
    config_path: Path | None = None
    raw_zarr_path: Path | None = None
    rois_zarr_path: Path | None = None
    traces_dir: Path | None = None
    traces_merged_dir: Path | None = None


__all__ = [
    "MicroscopyMetadata",
    "PositionArtifacts",
    "ProcessingResults",
]
