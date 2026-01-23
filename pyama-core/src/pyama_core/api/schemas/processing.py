"""Pydantic schemas for processing configuration."""

from typing import Any

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
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Processing parameters (segmentation_method, tracking_method, background_weight, etc.)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "channels": {
                    "pc": {"channel": 0, "features": ["area"]},
                    "fl": [{"channel": 1, "features": ["intensity_total"]}],
                },
                "params": {
                    "segmentation_method": "cellpose",
                    "tracking_method": "iou",
                    "background_weight": 1.0,
                    "mask_margin": 5,
                },
            }
        }
    }
