"""Processing configuration routes - schema discovery."""

from typing import Any

from fastapi import APIRouter

from pyama_core.processing.extraction.features import (
    list_fluorescence_features,
    list_phase_features,
)
from pyama_core.types.processing import ProcessingConfig

router = APIRouter(prefix="/config", tags=["processing"])


@router.get("", response_model=dict[str, Any])
async def get_config_schema() -> dict[str, Any]:
    """Get the JSON schema for ProcessingConfig.

    This endpoint returns the JSON Schema for the ProcessingConfig model,
    which can be used by the frontend to dynamically generate forms for
    configuring processing tasks.

    The schema includes:
    - channels: PC and FL channel configuration with features
    - params: Processing parameters (segmentation_method, tracking_method, etc.)
    """
    return ProcessingConfig.model_json_schema()


@router.get("/features", response_model=dict[str, list[str]])
async def get_available_features() -> dict[str, list[str]]:
    """Get available feature extractors for each channel type.

    Returns:
        Dictionary with 'phase' and 'fluorescence' keys, each containing
        a list of available feature names that can be extracted.
    """
    return {
        "phase": list_phase_features(),
        "fluorescence": list_fluorescence_features(),
    }
