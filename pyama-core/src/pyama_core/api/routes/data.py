"""Data routes - microscopy file loading and metadata."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from pyama_core.api.schemas.microscopy import (
    MicroscopyLoadRequest,
    MicroscopyMetadataSchema,
    metadata_to_schema,
)
from pyama_core.io.microscopy import load_microscopy_file

logger = logging.getLogger(__name__)

router = APIRouter(tags=["data"])


@router.post("/microscopy", response_model=MicroscopyMetadataSchema)
async def load_microscopy(
    request: MicroscopyLoadRequest,
) -> MicroscopyMetadataSchema:
    """Load and parse a microscopy file to extract metadata.

    Supports ND2, CZI, and TIFF formats.
    Returns metadata including dimensions, channels, and timepoints.
    """
    file_path = Path(request.file_path)

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {request.file_path}",
        )

    try:
        _, metadata = load_microscopy_file(file_path)
        logger.info("Loaded microscopy file: %s", file_path)
        return metadata_to_schema(metadata)
    except Exception as e:
        logger.exception("Failed to load microscopy file: %s", file_path)
        raise HTTPException(
            status_code=400,
            detail=f"Failed to load microscopy file: {e}",
        ) from e


microscopy_router = router
