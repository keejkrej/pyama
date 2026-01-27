"""Processing-related data structures."""

# =============================================================================
# IMPORTS
# =============================================================================

from pathlib import Path

from pydantic import BaseModel

from pyama_core.types.processing import FeatureMaps


# =============================================================================
# DATA STRUCTURES
# =============================================================================


class ChannelSelectionPayload(BaseModel):
    """Lightweight payload describing selected channels."""

    model_config = {"frozen": True}

    phase: int | None
    fluorescence: list[int]


class MergeRequest(BaseModel):
    """Data structure for merge operation requests."""

    model_config = {"frozen": True}

    sample_yaml: Path
    input_dir: Path
    output_dir: Path


__all__ = [
    "ChannelSelectionPayload",
    "MergeRequest",
    "FeatureMaps",
]
