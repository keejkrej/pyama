"""Processing configuration routes - schema discovery."""

from typing import Any

from fastapi import APIRouter

from pyama_core.api.schemas.processing import ProcessingConfigSchema

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
    return ProcessingConfigSchema.model_json_schema()
