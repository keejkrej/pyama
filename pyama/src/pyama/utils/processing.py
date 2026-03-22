"""Shared processing helpers."""

from pyama.types.io import MicroscopyMetadata
from pyama.types.processing import ProcessingConfig
from pyama.utils.position import parse_position_range


def resolve_processing_positions(
    metadata: MicroscopyMetadata,
    config: ProcessingConfig,
) -> list[int]:
    if config.params.positions.strip().lower() == "all":
        return list(range(metadata.n_positions))
    return parse_position_range(config.params.positions, length=metadata.n_positions)


__all__ = ["resolve_processing_positions"]
