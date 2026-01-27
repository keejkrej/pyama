"""Microscopy metadata types."""

from pathlib import Path

from pydantic import BaseModel


class MicroscopyMetadata(BaseModel):
    """Metadata for microscopy files (ND2, CZI, etc.)."""

    file_path: Path
    base_name: str
    file_type: str  # 'nd2', 'czi', etc.
    height: int
    width: int
    n_frames: int
    n_fovs: int
    n_channels: int
    timepoints: list[float]
    channel_names: list[str]
    dtype: str


__all__ = ["MicroscopyMetadata"]
