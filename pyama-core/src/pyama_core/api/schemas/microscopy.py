"""Pydantic schemas for microscopy file metadata."""

from pydantic import BaseModel, Field

from pyama_core.io.microscopy import MicroscopyMetadata


class MicroscopyLoadRequest(BaseModel):
    """Request to load a microscopy file."""

    file_path: str = Field(..., description="Path to the microscopy file (ND2, CZI, TIFF)")

    model_config = {
        "json_schema_extra": {
            "example": {"file_path": "/path/to/experiment.nd2"}
        }
    }


class MicroscopyMetadataSchema(BaseModel):
    """Metadata extracted from a microscopy file."""

    file_path: str = Field(..., description="Path to the microscopy file")
    base_name: str = Field(..., description="Base name of the file (without extension)")
    file_type: str = Field(..., description="File type (nd2, czi, tiff, etc.)")
    height: int = Field(..., description="Image height in pixels")
    width: int = Field(..., description="Image width in pixels")
    n_frames: int = Field(..., description="Number of time frames")
    n_fovs: int = Field(..., description="Number of fields of view")
    n_channels: int = Field(..., description="Number of channels")
    timepoints: list[float] = Field(..., description="Timepoint values")
    channel_names: list[str] = Field(..., description="Channel names")
    dtype: str = Field(..., description="Data type of the image array")

    model_config = {
        "json_schema_extra": {
            "example": {
                "file_path": "/path/to/experiment.nd2",
                "base_name": "experiment",
                "file_type": "nd2",
                "height": 2048,
                "width": 2048,
                "n_frames": 100,
                "n_fovs": 10,
                "n_channels": 3,
                "timepoints": [0.0, 60.0, 120.0],
                "channel_names": ["Phase", "GFP", "RFP"],
                "dtype": "uint16",
            }
        }
    }


def metadata_to_schema(meta: MicroscopyMetadata) -> MicroscopyMetadataSchema:
    """Convert a MicroscopyMetadata dataclass to a Pydantic schema."""
    return MicroscopyMetadataSchema(
        file_path=str(meta.file_path),
        base_name=meta.base_name,
        file_type=meta.file_type,
        height=meta.height,
        width=meta.width,
        n_frames=meta.n_frames,
        n_fovs=meta.n_fovs,
        n_channels=meta.n_channels,
        timepoints=meta.timepoints,
        channel_names=meta.channel_names,
        dtype=meta.dtype,
    )
