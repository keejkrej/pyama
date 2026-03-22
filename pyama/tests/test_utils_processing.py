from pathlib import Path

import pytest

from pyama.types import MicroscopyMetadata
from pyama.types.processing import ProcessingConfig, ProcessingParams
from pyama.utils.processing import resolve_processing_positions


def _metadata() -> MicroscopyMetadata:
    return MicroscopyMetadata(
        file_path=Path("fake.nd2"),
        base_name="fake",
        file_type="nd2",
        height=1,
        width=1,
        n_frames=1,
        channel_names=(),
        dtype="uint16",
        position_list=(10, 11, 12, 13),
    )


def test_resolve_processing_positions_all() -> None:
    positions = resolve_processing_positions(
        _metadata(),
        ProcessingConfig(params=ProcessingParams(positions="all")),
    )

    assert positions == [0, 1, 2, 3]


def test_resolve_processing_positions_slice() -> None:
    positions = resolve_processing_positions(
        _metadata(),
        ProcessingConfig(params=ProcessingParams(positions="1:4:2")),
    )

    assert positions == [1, 3]


def test_resolve_processing_positions_rejects_invalid_indices() -> None:
    with pytest.raises(ValueError):
        resolve_processing_positions(
            _metadata(),
            ProcessingConfig(params=ProcessingParams(positions="5")),
        )
