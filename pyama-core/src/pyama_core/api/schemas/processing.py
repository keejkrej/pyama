"""Pydantic schemas for processing configuration."""

from pydantic import BaseModel, Field


class ChannelSelectionSchema(BaseModel):
    """Configuration for a single channel selection."""

    channel: int = Field(..., description="Channel index (0-based)")
    features: list[str] = Field(
        default_factory=list,
        description="List of features to extract from this channel",
    )

    model_config = {
        "json_schema_extra": {
            "example": {"channel": 0, "features": ["area", "intensity_total"]}
        }
    }


class ProcessingParamsSchema(BaseModel):
    """Processing parameters for the pipeline."""

    fovs: str = Field(
        default="",
        description="FOV selection string (e.g., '1-4,6'). Empty means all FOVs.",
    )
    batch_size: int = Field(
        default=2,
        ge=1,
        description="Number of FOVs to process in parallel",
    )
    n_workers: int = Field(
        default=2,
        ge=1,
        description="Number of worker threads",
    )
    background_weight: float = Field(
        default=1.0,
        ge=0,
        description="Weight for background subtraction",
    )


class ChannelsSchema(BaseModel):
    """Configuration for all channels (phase contrast and fluorescence)."""

    pc: ChannelSelectionSchema = Field(..., description="Phase contrast channel configuration")
    fl: list[ChannelSelectionSchema] = Field(
        default_factory=list,
        description="Fluorescence channel configurations",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "pc": {"channel": 0, "features": ["area", "aspect_ratio"]},
                "fl": [
                    {"channel": 1, "features": ["intensity_total", "particle_num"]},
                    {"channel": 2, "features": ["intensity_total"]},
                ],
            }
        }
    }


class ProcessingConfigSchema(BaseModel):
    """Configuration for the processing pipeline.

    This schema is used for:
    1. Creating new processing tasks (POST /processing/tasks)
    2. Schema discovery (GET /processing/config) - frontend can build forms from this
    """

    channels: ChannelsSchema | None = Field(
        None,
        description="Channel configuration (PC and FL channels with features)",
    )
    params: ProcessingParamsSchema = Field(
        default_factory=ProcessingParamsSchema,
        description="Processing parameters",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "channels": {
                    "pc": {"channel": 0, "features": ["area"]},
                    "fl": [{"channel": 1, "features": ["intensity_total"]}],
                },
                "params": {
                    "fovs": "1-4,6",
                    "batch_size": 2,
                    "n_workers": 2,
                    "background_weight": 1.0,
                },
            }
        }
    }
