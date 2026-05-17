"""Reader registry."""

from __future__ import annotations

from pathlib import Path

from .base import ReaderAdapter, ReaderSession
from .czi import CZIReaderAdapter
from .folder import ImageFolderReaderAdapter
from .nd2 import ND2ReaderAdapter

ADAPTERS: tuple[ReaderAdapter, ...] = (
    ND2ReaderAdapter(),
    CZIReaderAdapter(),
    ImageFolderReaderAdapter(),
)


def resolve_reader_adapter(input_path: Path) -> ReaderAdapter:
    for adapter in ADAPTERS:
        if adapter.supports(input_path):
            return adapter
    raise ValueError(f"Unsupported source: {input_path}")


def open_reader(input_path: Path) -> ReaderSession:
    return resolve_reader_adapter(input_path).open(input_path)
