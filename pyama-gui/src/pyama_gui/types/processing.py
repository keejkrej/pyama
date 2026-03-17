"""Processing-related data structures."""

# =============================================================================
# IMPORTS
# =============================================================================

from dataclasses import dataclass
from pathlib import Path

from pyama.types import FeatureMaps


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass(frozen=True)
class ChannelSelectionPayload:
    """Lightweight payload describing selected channels."""

    phase: int | None
    fluorescence: list[int]


@dataclass(frozen=True)
class MergeRequest:
    """Data structure for merge operation requests."""

    samples: list[dict[str, str]]
    processing_results_dir: Path


__all__ = [
    "ChannelSelectionPayload",
    "MergeRequest",
    "FeatureMaps",
]
